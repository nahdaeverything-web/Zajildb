import type * as db from '@/src/db.js';
declare global {
  interface Window {
    __zajilDb: typeof db;
    __zajilEngine: Record<string, unknown>;
    __zajilReady: Promise<void>;
    __zajilSyncLoop: (() => void) | null;
  }
}
export {};
