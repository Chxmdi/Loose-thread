import { describe, expect, it } from "vitest";

import { MemoryCaptureStore, persistBeforeSync, syncPending } from "./queueCore";
import type { LocalCapture } from "./types";

function input(): Omit<LocalCapture, "status" | "attempts" | "nextRetryAt" | "lastError"> {
  return {
    id: "capture-1",
    deviceId: "device-1",
    idempotencyKey: "device-1:capture-1",
    mode: "text",
    rawText: "A thought worth keeping",
    audioUri: null,
    timezone: "UTC",
    clientCreatedAt: "2026-09-01T12:00:00Z",
    parentSessionId: null,
    spawnedThoughtId: null,
  };
}

describe("local capture queue", () => {
  it("persists a capture before transport is attempted", async () => {
    const store = new MemoryCaptureStore();
    await persistBeforeSync(store, input());
    expect((await store.list())[0]).toMatchObject({ status: "local", rawText: input().rawText });
  });

  it("survives manager restart and syncs from the same persistent store", async () => {
    const records = new Map<string, LocalCapture>();
    await persistBeforeSync(new MemoryCaptureStore(records), input());
    await syncPending(new MemoryCaptureStore(records), async () => undefined);
    expect((await new MemoryCaptureStore(records).list())[0]?.status).toBe("synced");
  });

  it("keeps raw evidence and schedules retry when backend is unavailable", async () => {
    const store = new MemoryCaptureStore();
    await persistBeforeSync(store, input());
    await syncPending(store, async () => {
      throw new Error("Backend unavailable");
    });
    expect((await store.list())[0]).toMatchObject({
      status: "failed",
      rawText: "A thought worth keeping",
      attempts: 1,
      lastError: "Backend unavailable",
    });
    expect((await store.list())[0]?.nextRetryAt).not.toBeNull();
  });
});
