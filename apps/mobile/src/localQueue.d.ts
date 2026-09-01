export {
  persistBeforeSync,
  syncPending,
  type CaptureStore,
  type CaptureTransport,
} from "./queueCore";

import type { CaptureStore } from "./queueCore";

export function createCaptureStore(): CaptureStore;
