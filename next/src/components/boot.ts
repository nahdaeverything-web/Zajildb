import * as db from '@/src/db.js';

/**
 * ONE boot, shared by everything that mounts.
 *
 * db/storage.js:123 initDB() is not re-entrant: it reads the six stores, and if it
 * finds no loft it creates the default one. Two calls in flight at once therefore
 * BOTH see an empty loft store and both mint a default — which the sync layer then
 * treats as two real lofts, and the second device stops adopting the remote one
 * (db/sync.js:830, "an untouched default loft is not data").
 *
 * Vanilla could not hit this: boot() calls initDB() once for the whole app. The port
 * has a screen and the shell mounting independently, so the single call becomes a
 * single PROMISE — every caller awaits the same one, and the layer still initialises
 * exactly once.
 */
let booting: Promise<unknown> | null = null;

export function initDB(): Promise<unknown> {
  return (booting ??= db.initDB());
}
