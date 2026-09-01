import "react-native-url-polyfill/auto";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { authStorage } from "./authStorage";
import type {
  CaptureResponse,
  LocalCapture,
  ResumptionResponse,
  RetrievalResponse,
} from "./types";

const apiUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
let client: SupabaseClient | null = null;

function getSupabase(): SupabaseClient {
  if (!supabaseUrl || !supabaseKey) throw new Error("Cloud sync is not configured");
  client ??= createClient(supabaseUrl, supabaseKey, {
    auth: {
      storage: authStorage,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  });
  return client;
}

async function accessToken(): Promise<string> {
  const supabase = getSupabase();
  let session = (await supabase.auth.getSession()).data.session;
  if (!session) {
    const signedIn = await supabase.auth.signInAnonymously();
    if (signedIn.error) throw signedIn.error;
    session = signedIn.data.session;
  }
  if (!session) throw new Error("Anonymous session unavailable");
  return session.access_token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!apiUrl) throw new Error("Cloud sync is not configured");
  const token = await accessToken();
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function syncCapture(capture: LocalCapture): Promise<void> {
  if (capture.mode === "audio") throw new Error("Voice saved on device; upload is waiting");
  if (capture.parentSessionId && capture.spawnedThoughtId) {
    await request(`/v1/sessions/${capture.parentSessionId}/spawn`, {
      method: "POST",
      body: JSON.stringify({
        capture_id: capture.id,
        thought_id: capture.spawnedThoughtId,
        device_id: capture.deviceId,
        idempotency_key: capture.idempotencyKey,
        raw_text: capture.rawText,
        timezone: capture.timezone,
        client_created_at: capture.clientCreatedAt,
      }),
    });
    return;
  }
  await request("/v1/captures", {
    method: "POST",
    body: JSON.stringify({
      id: capture.id,
      device_id: capture.deviceId,
      idempotency_key: capture.idempotencyKey,
      capture_mode: "text",
      raw_text: capture.rawText,
      timezone: capture.timezone,
      client_created_at: capture.clientCreatedAt,
    }),
  });
}

export const api = {
  capture: (id: string) => request<CaptureResponse>(`/v1/captures/${id}`),
  retrieval: (body: object) =>
    request<RetrievalResponse>("/v1/retrievals", { method: "POST", body: JSON.stringify(body) }),
  resumption: (thoughtId: string) =>
    request<ResumptionResponse>(`/v1/thoughts/${thoughtId}/resumption`),
  startSession: (body: object) =>
    request<{ id: string }>("/v1/sessions", { method: "POST", body: JSON.stringify(body) }),
  completeSession: (id: string, body: object) =>
    request(`/v1/sessions/${id}/complete`, { method: "POST", body: JSON.stringify(body) }),
  action: (retrievalId: string, body: object) =>
    request(`/v1/retrievals/${retrievalId}/action`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  jobs: () => request<Array<Record<string, unknown>>>("/v1/debug/jobs"),
  agentRuns: () => request<Array<Record<string, unknown>>>("/v1/debug/agent-runs"),
};
