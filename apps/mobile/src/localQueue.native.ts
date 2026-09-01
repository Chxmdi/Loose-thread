import { openDatabaseAsync, type SQLiteDatabase } from "expo-sqlite";

import { persistBeforeSync, syncPending, type CaptureStore } from "./queueCore";
import type { LocalCapture } from "./types";

class SQLiteCaptureStore implements CaptureStore {
  private database: SQLiteDatabase | null = null;

  async initialize(): Promise<void> {
    this.database = await openDatabaseAsync("loose-thread.db");
    await this.database.execAsync(`
      create table if not exists capture_queue (
        id text primary key not null,
        payload text not null,
        updated_at text not null
      );
    `);
  }
  async upsert(capture: LocalCapture): Promise<void> {
    if (!this.database) await this.initialize();
    await this.database!.runAsync(
      `insert into capture_queue (id, payload, updated_at) values (?, ?, ?)
       on conflict(id) do update set payload = excluded.payload, updated_at = excluded.updated_at`,
      capture.id,
      JSON.stringify(capture),
      new Date().toISOString(),
    );
  }
  async list(): Promise<LocalCapture[]> {
    if (!this.database) await this.initialize();
    const rows = await this.database!.getAllAsync<{ payload: string }>(
      "select payload from capture_queue order by updated_at desc",
    );
    return rows.map((row) => JSON.parse(row.payload) as LocalCapture);
  }
}

export function createCaptureStore(): CaptureStore {
  return new SQLiteCaptureStore();
}
export { persistBeforeSync, syncPending, type CaptureStore } from "./queueCore";
