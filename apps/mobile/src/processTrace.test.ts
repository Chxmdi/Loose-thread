import { describe, expect, it } from "vitest";

import type { DebugSnapshot } from "./types";
import { buildProcessSteps } from "./processTrace";

const snapshot: DebugSnapshot = {
  jobs: [
    job("interpret", "interpret_capture", "capture-1", "capture-correlation"),
    job("embed", "embed_thought", "thought-1", "capture-correlation"),
    job("link", "link_thought", "thought-1", "capture-correlation"),
    job("calibrate", "apply_feedback_calibration", "feedback-complete", "feedback-correlation"),
  ],
  agentRuns: [
    run("interpreter", "thought_interpreter", ["capture-1"], ["thought-1"], "capture-correlation"),
    run("continuity", "continuity_agent", ["thought-1"], ["relationship-1"], "capture-correlation"),
    run("resumption", "resumption_agent", ["thought-1", "thought-2"], ["thought-2"], "resume-correlation"),
  ],
  feedback: [
    {
      id: "feedback-complete",
      session_id: "session-1",
      retrieval_id: "retrieval-1",
      thought_id: "thought-1",
      event_type: "session_completed",
      event_data: { outcome: "partial", fit: "right" },
      calibration_applied_at: "2026-09-02T12:00:00Z",
      calibration_version: "feedback-v1",
      created_at: "2026-09-02T11:59:00Z",
    },
    {
      id: "feedback-start",
      session_id: "session-1",
      retrieval_id: "retrieval-1",
      thought_id: "thought-1",
      event_type: "retrieval_action",
      event_data: { action: "start" },
      calibration_applied_at: "2026-09-02T12:00:00Z",
      calibration_version: "feedback-v1",
      created_at: "2026-09-02T11:58:00Z",
    },
  ],
  calibration: {
    observation_count: 2,
    kind_affinity: { task: 0.7 },
    duration_calibration: { snack: 0.1 },
    context_affinity: { home: 0.6 },
    updated_at: "2026-09-02T12:00:00Z",
  },
  retrieval: {
    retrieval: {
      id: "retrieval-1",
      ranking_version: "capacity-v1",
      candidate_count: 3,
      result_thought_ids: ["thought-1"],
      created_at: "2026-09-02T11:57:00Z",
    },
    impressions: [
      {
        thought_id: "thought-1",
        rank_position: 1,
        score: 0.8,
        score_components: { capacity_fit: 1 },
        selected: true,
        action: "start",
        created_at: "2026-09-02T11:57:00Z",
      },
    ],
  },
};

describe("buildProcessSteps", () => {
  it("builds a persisted, ordered trace across all three agents and calibration", () => {
    const steps = buildProcessSteps(snapshot);

    expect(steps.map((step) => step.actor)).toEqual([
      "Capture API",
      "Durable worker",
      "Thought Interpreter Agent",
      "Thought Interpreter Agent",
      "Thought Interpreter Agent",
      "Embedding service",
      "Durable worker",
      "Continuity Agent",
      "Continuity Agent",
      "Continuity Agent",
      "Retrieval engine",
      "Retrieval engine",
      "Retrieval engine",
      "Resumption Agent",
      "Resumption Agent",
      "Resumption Agent",
      "Session API",
      "Session API",
      "Calibration worker",
      "Retrieval model",
    ]);
    expect(steps[2]?.detail).toContain("capture-1");
    expect(steps[8]?.detail).toContain("continuity-v1");
    expect(steps[15]?.detail).toContain("thought-2");
    expect(steps[15]?.thoughtIds).toEqual(["thought-2"]);
    expect(steps[17]?.detail).toContain("partial | right");
    expect(steps.at(-1)?.detail).toContain("2 observations");
  });

  it("does not invent process evidence when the backend snapshot is absent", () => {
    expect(buildProcessSteps(null)).toEqual([]);
  });
});

function job(id: string, jobType: string, entityId: string, correlationId: string) {
  return {
    id,
    job_type: jobType,
    entity_type: "test",
    entity_id: entityId,
    status: "succeeded",
    attempts: 1,
    max_attempts: 5,
    correlation_id: correlationId,
    last_error_code: null,
    created_at: "2026-09-02T11:00:00Z",
    updated_at: "2026-09-02T11:01:00Z",
  };
}

function run(id: string, agentName: string, inputs: string[], outputs: string[], correlationId: string) {
  return {
    id,
    job_id: `${id}-job`,
    agent_name: agentName,
    model: "gpt-5-mini",
    schema_version: "1.0",
    prompt_version: `${agentName.replace("_agent", "")}-v1`,
    status: "succeeded",
    input_entity_ids: inputs,
    output_entity_ids: outputs,
    openai_trace_id: `${id}-trace-1234567890`,
    correlation_id: correlationId,
    latency_ms: 125,
    usage: {},
    error_code: null,
    created_at: "2026-09-02T11:00:00Z",
  };
}
