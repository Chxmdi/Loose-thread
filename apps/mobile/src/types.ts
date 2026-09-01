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
