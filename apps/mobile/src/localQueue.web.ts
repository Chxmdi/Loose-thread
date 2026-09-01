import { persistBeforeSync, syncPending, type CaptureStore } from "./queueCore";
import type { LocalCapture } from "./types";

class WebCaptureStore implements CaptureStore {
  private readonly key = "loose-thread-capture-queue-v1";
  async initialize(): Promise<void> {}
  async upsert(capture: LocalCapture): Promise<void> {
    const records = (await this.list()).filter((item) => item.id !== capture.id);
    records.push(capture);
    localStorage.setItem(this.key, JSON.stringify(records));
  }
  async list(): Promise<LocalCapture[]> {
    const value = localStorage.getItem(this.key);
    return value ? (JSON.parse(value) as LocalCapture[]) : [];
  }
}

export function createCaptureStore(): CaptureStore {
  return new WebCaptureStore();
}
export { persistBeforeSync, syncPending, type CaptureStore } from "./queueCore";
