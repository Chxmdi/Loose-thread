export type CaptureMode = "text" | "audio";
export type SyncStatus = "local" | "syncing" | "synced" | "failed";

export type LocalCapture = {
  id: string;
  deviceId: string;
  idempotencyKey: string;
  mode: CaptureMode;
  rawText: string | null;
  audioUri: string | null;
  timezone: string;
  clientCreatedAt: string;
  status: SyncStatus;
  attempts: number;
  nextRetryAt: string | null;
  lastError: string | null;
  parentSessionId: string | null;
  spawnedThoughtId: string | null;
};

export type Thought = {
  id: string;
  raw_fragment: string;
  refined_text: string;
  kind: string;
  commitment_strength: string;
  duration_bucket: string;
  energy: string;
  open_loop: Record<string, unknown>;
};

export type CaptureResponse = {
  id: string;
  processing_status: "queued" | "processing" | "succeeded" | "failed";
  thoughts: Thought[];
};

export type RetrievalCard = {
  thought_id: string;
  rank: number;
  refined_text: string;
  kind: string;
  commitment_strength: string;
  duration_bucket: string;
  energy: string;
  contexts: string[];
  open_loop: Record<string, unknown>;
};

export type RetrievalResponse = { id: string; cards: RetrievalCard[]; window: string };

export type ResumptionResponse = {
  thought_id: string;
  refined_text: string;
  raw_fragment: string;
  where_you_got_to: string | null;
  supporting_thoughts: Array<{ id: string; refined_text: string; relation_type: string }>;
  unresolved_loop: string | null;
  suggested_prompt: string | null;
};

export type CalibrationDebug = {
  duration_calibration: Record<string, number>;
  kind_affinity: Record<string, number>;
  context_affinity: Record<string, number>;
  observation_count: number;
  updated_at: string | null;
};

export type JobDebug = {
  id: string;
  job_type: string;
  entity_type: string;
  entity_id: string;
  status: string;
  attempts: number;
  max_attempts: number;
  correlation_id: string;
  last_error_code: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentRunDebug = {
  id: string;
  job_id: string | null;
  agent_name: string;
  model: string;
  schema_version: string;
  prompt_version: string;
  status: string;
  input_entity_ids: string[];
  output_entity_ids: string[];
  openai_trace_id: string | null;
  correlation_id: string;
  latency_ms: number | null;
  usage: Record<string, unknown>;
  error_code: string | null;
  created_at: string;
};

export type FeedbackEventDebug = {
  id: string;
  session_id: string | null;
  retrieval_id: string | null;
  thought_id: string | null;
  event_type: string;
  event_data: Record<string, unknown>;
  calibration_applied_at: string | null;
  calibration_version: string | null;
  created_at: string;
};

export type RetrievalDebug = {
  retrieval: {
    id: string;
    ranking_version: string;
    candidate_count: number;
    result_thought_ids: string[];
    created_at: string;
  };
  impressions: Array<{
    thought_id: string;
    rank_position: number;
    score: number;
    score_components: Record<string, number>;
    selected: boolean;
    action: string | null;
    created_at: string;
  }>;
};

export type DebugSnapshot = {
  jobs: JobDebug[];
  agentRuns: AgentRunDebug[];
  feedback: FeedbackEventDebug[];
  calibration: CalibrationDebug;
  retrieval: RetrievalDebug | null;
};
