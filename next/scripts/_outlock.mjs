/**
 * An exclusive lock on `out/`.
 *
 * WHY THIS EXISTS. On 2026-09-25 a release was built with NEXT_PUBLIC_BASE_PATH=/zajilv2 and,
 * while it was being copied to the deploy branch, a full gate running in another shell rebuilt
 * `out/` at the ROOT prefix. The bytes that reached GitHub Pages were the gate's, not the
 * release's: every asset URL lost its prefix and the live site could not load at all. Both
 * processes were correct in isolation. `out/` is ONE mutable directory and had two writers.
 *
 * The postbuild guards cannot see this. They check `out/` at the moment they run, and they
 * passed — truthfully, about a build that no longer existed by the time it was copied.
 *
 * mkdir is the primitive because it is atomic on every platform this runs on: it either
 * creates the directory or fails with EEXIST, with no window between the check and the claim
 * that a `existsSync` + `writeFile` pair would have.
 */
import { mkdirSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const LOCK = join(process.cwd(), 'out.lock');
const STALE_MS = 45 * 60 * 1000;   // a full gate is ~18 min; well clear of it

function holder() {
  try {
    return JSON.parse(readFileSync(join(LOCK, 'owner.json'), 'utf8'));
  } catch {
    return null;
  }
}

/** Claim `out/`. Throws, with the holder named, rather than waiting: a deploy that queues
 *  behind an 18-minute gate is a deploy nobody is watching any more. */
export function lockOut(who) {
  try {
    mkdirSync(LOCK);
  } catch (e) {
    if (e.code !== 'EEXIST') throw e;
    const h = holder();
    const age = h ? Date.now() - h.at : Infinity;
    if (h && age < STALE_MS && isAlive(h.pid)) {
      throw new Error(
        `out/ is locked by ${h.who} (pid ${h.pid}, ${Math.round(age / 1000)}s ago).\n`
        + '  Two processes writing out/ is what shipped a root-basePath build to production.\n'
        + '  Wait for it, or stop it — do not build around it.',
      );
    }
    // stale: the holder is gone or impossibly old
    rmSync(LOCK, { recursive: true, force: true });
    mkdirSync(LOCK);
  }
  writeFileSync(join(LOCK, 'owner.json'), JSON.stringify({ who, pid: process.pid, at: Date.now() }));
  const release = () => { try { rmSync(LOCK, { recursive: true, force: true }); } catch {} };
  process.on('exit', release);
  process.on('SIGINT', () => { release(); process.exit(130); });
  process.on('SIGTERM', () => { release(); process.exit(143); });
  return release;
}

function isAlive(pid) {
  try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; }
}

export function lockHolder() { return existsSync(LOCK) ? holder() : null; }
