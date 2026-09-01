import type { LocalCapture } from "./types";

export interface CaptureStore {
  initialize(): Promise<void>;
  upsert(capture: LocalCapture): Promise<void>;
  list(): Promise<LocalCapture[]>;
}

export type CaptureTransport = (capture: LocalCapture) => Promise<void>;

export function retryDelayMs(attempts: number): number {
  return Math.min(5 * 60_000, 2 ** Math.max(0, attempts - 1) * 5_000);
}

export async function persistBeforeSync(
  store: CaptureStore,
  capture: Omit<LocalCapture, "status" | "attempts" | "nextRetryAt" | "lastError">,
): Promise<LocalCapture> {
  const local: LocalCapture = {
    ...capture,
    status: "local",
    attempts: 0,
    nextRetryAt: null,
    lastError: null,
  };
  await store.upsert(local);
  return local;
}

export async function syncPending(
  store: CaptureStore,
  transport: CaptureTransport,
  now = new Date(),
): Promise<LocalCapture[]> {
  const captures = await store.list();
  for (const capture of captures) {
    if (capture.status === "synced") continue;
    if (capture.nextRetryAt && new Date(capture.nextRetryAt) > now) continue;
    const syncing: LocalCapture = {
      ...capture,
      status: "syncing",
      attempts: capture.attempts + 1,
      lastError: null,
    };
    await store.upsert(syncing);
    try {
      await transport(syncing);
      await store.upsert({ ...syncing, status: "synced", nextRetryAt: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sync unavailable";
      await store.upsert({
        ...syncing,
        status: "failed",
        nextRetryAt: new Date(now.getTime() + retryDelayMs(syncing.attempts)).toISOString(),
        lastError: message,
      });
    }
  }
  return store.list();
}

export class MemoryCaptureStore implements CaptureStore {
  constructor(private readonly records = new Map<string, LocalCapture>()) {}
  async initialize(): Promise<void> {}
  async upsert(capture: LocalCapture): Promise<void> {
    this.records.set(capture.id, structuredClone(capture));
  }
  async list(): Promise<LocalCapture[]> {
    return [...this.records.values()].map((capture) => structuredClone(capture));
  }
}
