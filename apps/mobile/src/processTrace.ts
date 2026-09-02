import type { AgentRunDebug, DebugSnapshot, JobDebug } from "./types";

export type ProcessStep = {
  actor: string;
  title: string;
  detail: string;
  status: string;
};

export function buildProcessSteps(snapshot: DebugSnapshot | null): ProcessStep[] {
  if (!snapshot) return [];

  const steps: ProcessStep[] = [];
  const interpretationJob = snapshot.jobs.find((job) => job.job_type === "interpret_capture");
  const captureCorrelation = interpretationJob?.correlation_id;
  const interpreterRun = findAgentRun(snapshot, "thought_interpreter", captureCorrelation);
  const embedJob = findJob(snapshot, "embed_thought", captureCorrelation);
  const linkJob = findJob(snapshot, "link_thought", captureCorrelation);
  const continuityRun = findAgentRun(snapshot, "continuity_agent", captureCorrelation);

  if (interpretationJob) {
    steps.push({
      actor: "Capture API",
      title: "Raw capture committed and interpretation enqueued",
      detail: `capture ${shortId(interpretationJob.entity_id)} | correlation ${shortId(interpretationJob.correlation_id)}`,
      status: interpretationJob.status,
    });
    steps.push({
      actor: "Durable worker",
      title: "Interpretation job claimed with retry state",
      detail: `attempt ${interpretationJob.attempts}/${interpretationJob.max_attempts} | job ${shortId(interpretationJob.id)}`,
      status: interpretationJob.status,
    });
  }

  appendAgentSteps(steps, interpreterRun, {
    actor: "Thought Interpreter Agent",
    inputTitle: "Capture text and temporal context loaded",
    decisionTitle: "Thought structure generated under schema",
    outputTitle: "Structured thought records persisted",
  });

  if (embedJob) {
    steps.push({
      actor: "Embedding service",
      title: "Thought vector generated and stored",
      detail: `thought ${shortId(embedJob.entity_id)} | attempt ${embedJob.attempts}/${embedJob.max_attempts}`,
      status: embedJob.status,
    });
  }

  if (linkJob) {
    steps.push({
      actor: "Durable worker",
      title: "Continuity analysis enqueued after embedding",
      detail: `thought ${shortId(linkJob.entity_id)} | job ${shortId(linkJob.id)}`,
      status: linkJob.status,
    });
  }

  appendAgentSteps(steps, continuityRun, {
    actor: "Continuity Agent",
    inputTitle: "Source thought and nearest candidates loaded",
    decisionTitle: "Relationship types and confidence evaluated",
    outputTitle: "Validated relationship records persisted",
  });

  const retrieval = snapshot.retrieval;
  if (retrieval) {
    const selected = retrieval.impressions.filter((item) => item.selected);
    steps.push({
      actor: "Retrieval engine",
      title: "Eligible candidates assembled",
      detail: `${retrieval.retrieval.candidate_count} candidates | retrieval ${shortId(retrieval.retrieval.id)}`,
      status: "succeeded",
    });
    steps.push({
      actor: "Retrieval engine",
      title: "Deterministic features scored and persisted",
      detail: `${retrieval.impressions.length} impressions | ${retrieval.retrieval.ranking_version}`,
      status: "succeeded",
    });
    steps.push({
      actor: "Retrieval engine",
      title: "Bounded result set selected",
      detail: `${selected.length} selected | thoughts ${summarizeIds(selected.map((item) => item.thought_id))}`,
      status: "succeeded",
    });
  }

  const resumptionRun = findAgentRun(snapshot, "resumption_agent");
  appendAgentSteps(steps, resumptionRun, {
    actor: "Resumption Agent",
    inputTitle: "Selected thought and linked evidence loaded",
    decisionTitle: "Grounded resume context synthesized",
    outputTitle: "Supporting evidence selected and cited",
  });

  const retrievalId = retrieval?.retrieval.id;
  const startEvent = snapshot.feedback.find(
    (event) =>
      event.retrieval_id === retrievalId &&
      event.event_type === "retrieval_action" &&
      event.event_data.action === "start",
  );
  if (startEvent) {
    steps.push({
      actor: "Session API",
      title: "Recommendation start recorded",
      detail: `feedback ${shortId(startEvent.id)} | thought ${shortId(startEvent.thought_id)}`,
      status: feedbackStatus(startEvent.calibration_applied_at),
    });
  }

  const completionEvent = snapshot.feedback.find(
    (event) => event.retrieval_id === retrievalId && event.event_type === "session_completed",
  );
  if (completionEvent) {
    steps.push({
      actor: "Session API",
      title: "Outcome and fit feedback committed",
      detail: `${feedbackValues(completionEvent.event_data)} | feedback ${shortId(completionEvent.id)}`,
      status: feedbackStatus(completionEvent.calibration_applied_at),
    });
  }

  const calibrationEvent = completionEvent ?? startEvent ?? snapshot.feedback.find(
    (event) => event.calibration_applied_at !== null,
  );
  const calibrationJob = calibrationEvent
    ? snapshot.jobs.find(
        (job) => job.job_type === "apply_feedback_calibration" && job.entity_id === calibrationEvent.id,
      )
    : snapshot.jobs.find((job) => job.job_type === "apply_feedback_calibration");
  if (calibrationJob) {
    steps.push({
      actor: "Calibration worker",
      title: "Feedback applied exactly once",
      detail: `event ${shortId(calibrationJob.entity_id)} | attempt ${calibrationJob.attempts}/${calibrationJob.max_attempts}`,
      status: calibrationJob.status,
    });
  }

  if (snapshot.calibration.observation_count > 0) {
    steps.push({
      actor: "Retrieval model",
      title: "Learned preferences available to the next ranking",
      detail: `${snapshot.calibration.observation_count} observations | ${Object.keys(snapshot.calibration.kind_affinity).length} kinds | ${Object.keys(snapshot.calibration.context_affinity).length} contexts`,
      status: "succeeded",
    });
  }

  return steps;
}

function appendAgentSteps(
  steps: ProcessStep[],
  run: AgentRunDebug | undefined,
  labels: {
    actor: string;
    inputTitle: string;
    decisionTitle: string;
    outputTitle: string;
  },
) {
  if (!run) return;

  steps.push({
    actor: labels.actor,
    title: labels.inputTitle,
    detail: `${run.input_entity_ids.length} inputs | ${summarizeIds(run.input_entity_ids)}`,
    status: run.status,
  });
  steps.push({
    actor: labels.actor,
    title: labels.decisionTitle,
    detail: `${run.model} | prompt ${run.prompt_version} | trace ${run.openai_trace_id ? shortId(run.openai_trace_id, 18) : "unavailable"}`,
    status: run.status,
  });
  steps.push({
    actor: labels.actor,
    title: labels.outputTitle,
    detail: `${run.output_entity_ids.length} outputs | ${summarizeIds(run.output_entity_ids)} | ${run.latency_ms ?? 0} ms`,
    status: run.status,
  });
}

function findJob(snapshot: DebugSnapshot, jobType: string, correlationId?: string): JobDebug | undefined {
  return snapshot.jobs.find(
    (job) => job.job_type === jobType && (!correlationId || job.correlation_id === correlationId),
  );
}

function findAgentRun(
  snapshot: DebugSnapshot,
  agentName: string,
  correlationId?: string,
): AgentRunDebug | undefined {
  return snapshot.agentRuns.find(
    (run) => run.agent_name === agentName && (!correlationId || run.correlation_id === correlationId),
  );
}

function feedbackStatus(appliedAt: string | null): string {
  return appliedAt ? "calibrated" : "persisted";
}

function feedbackValues(data: Record<string, unknown>): string {
  const values = [data.outcome, data.fit].filter((value): value is string => typeof value === "string");
  return values.length ? values.join(" | ") : "recorded";
}

function summarizeIds(ids: string[]): string {
  if (!ids.length) return "none";
  const visible = ids.slice(0, 3).map((id) => shortId(id));
  return ids.length > visible.length ? `${visible.join(", ")} +${ids.length - visible.length}` : visible.join(", ");
}

function shortId(value: string | null, length = 10): string {
  if (!value) return "none";
  return value.length <= length ? value : value.slice(0, length);
}
