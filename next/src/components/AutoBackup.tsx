'use client';
import { useEffect } from 'react';
import * as db from '@/src/db.js';
import { initDB } from './boot';

/**
 * THE INTERVAL SNAPSHOT'S CALLER, MOUNTED ONCE AT BOOT (ROOT-FINDINGS RF-21, RULED a defect 2026-11-01).
 *
 * `autoBackup()` (src/db/io.js) had no caller in the port: the restore screen promised a snapshot every 12 hours
 * and none was ever taken. This is vanilla's caller (js/app.js:254-262), unchanged in behaviour:
 *   · after the ONE shared boot, a snapshot is taken if none was ever taken or the last is older than the interval;
 *   · then one every interval for as long as the page stays open;
 *   · never for an empty register — a snapshot of nothing would push a real one out of the kept set.
 * A failure is swallowed, as in vanilla: a snapshot that cannot be written must not stop the app from opening.
 *
 * NOT AT THE SIGN-IN GATE (RULED 2026-11-16). A configured build with no session shows only the sign-in screen
 * (src/components/Gate.tsx), and that is where an account collision stops a device: the check there is that NOTHING
 * on the device changed, the snapshots store included. So the caller uses the gate's own two conditions and takes
 * nothing while the gate is shut — nobody can change a record from there, so there is nothing new to protect either.
 * The condition is read each time a snapshot is due, so the interval tick of a page that was signed in since is taken.
 *
 * Renders nothing.
 */
export default function AutoBackup() {
  useEffect(() => {
    let alive = true; let timer: ReturnType<typeof setInterval> | null = null;
    const every = (db.AUTO_BACKUP_HOURS as number) * 3600 * 1000;
    const gateOpen = () => !(db.syncConfig() as { configured: boolean }).configured || (db.authState() as { signedIn: boolean }).signedIn;
    const take = () => { if (gateOpen() && db.state.birds.size > 0) (db.autoBackup() as Promise<unknown>).catch(() => {}); };
    initDB().then(() => {
      if (!alive) return;
      const last = (db.state.settings as Record<string, unknown>).lastAutoBackup as string | undefined;
      if (!last || Date.now() - new Date(last).getTime() > every) take();
      timer = setInterval(take, every);
    });
    return () => { alive = false; if (timer) clearInterval(timer); };
  }, []);
  return null;
}
