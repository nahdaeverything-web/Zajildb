'use client';
import { useEffect } from 'react';
import * as db from '@/src/db.js';
import { autoSyncDisabled } from '@/src/harness-globals';
import { initDB } from './boot';

/**
 * THE SYNC COORDINATOR, MOUNTED ONCE AT BOOT (RULED 2026-11-13; ROOT-FINDINGS RF-19, RF-20).
 *
 * Vanilla's boot() starts the sync loop after its first route (js/app.js:252). The port had no
 * caller for it at all: sync ran at sign-in and on «مزامنة الآن», so a fancier who did not press
 * the button had a loft that lived on one device. This is that caller — the only one. The loop
 * itself, with every trigger it owns (open, a change debounced, online, foreground, background,
 * the heartbeat, the button), is src/db/sync.js; the `sync-single-owner` guard fails the build
 * if a cycle is started from anywhere else.
 *
 * It waits for the ONE shared boot (./boot), recounts what is unsent — the status must not say
 * «متزامن» from memory — and starts the loop. With no sync configuration or no session the loop
 * is inert: nothing is armed and nothing is sent.
 *
 * `autoSyncDisabled()` is the shipped stub's constant `false`. Only a harness build can answer
 * otherwise, for the suites that drive push and pull one leg at a time; the postbuild guard
 * fails a normal build that carries the switch.
 *
 * Renders nothing.
 */
export default function SyncCoordinator() {
  useEffect(() => {
    if (autoSyncDisabled()) return;
    let alive = true; let stop: (() => void) | null = null;
    initDB().then(async () => {
      if (!alive) return;
      await db.refreshSyncStatus();
      if (alive) stop = db.startSyncLoop() as () => void;
    });
    return () => { alive = false; if (stop) stop(); };
  }, []);
  return null;
}
