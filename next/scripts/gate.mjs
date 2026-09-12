#!/usr/bin/env node
// ONE gate. Everything, in order, with totals.
//
//     cd next && node scripts/gate.mjs            # the whole gate
//     cd next && node scripts/gate.mjs --live     # …including the live suites
//
// Why a script and not a README list: a gate a person assembles by hand is a gate that
// gets assembled differently each time. This one owns the order (a normal build proves
// the export ships no harness, then a harness build gives every browser suite something
// to serve), counts the assertions itself, and refuses to report a total it could not
// parse — a step whose summary it cannot read is a FAILURE, not a zero.
import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';

const LIVE = process.argv.includes('--live');
const t0 = Date.now();
const rows = [];
let hardFail = 0;

function run(name, cmd, args, { env = {}, parse = 'assertions', timeout = 3_600_000, cwd } = {}) {
  const started = Date.now();
  const r = spawnSync(cmd, args, { encoding: 'utf8', timeout, cwd, env: { ...process.env, ...env } });
  const out = (r.stdout || '') + (r.stderr || '');
  const secs = ((Date.now() - started) / 1000).toFixed(0);
  let passed = null, failed = null, detail = '';

  if (parse === 'assertions') {
    // the suites' own summary line: "N passed, M failed"
    const lines = out.trim().split('\n').filter((l) => /\d+\s+(?:assertions\s+)?passed/.test(l));
    const last = lines[lines.length - 1];
    const m = last && last.match(/(\d+)\s+(?:assertions\s+)?passed,\s*(\d+)\s+failed/);
    if (m) { passed = +m[1]; failed = +m[2]; }
    else detail = 'NO SUMMARY LINE — could not count';
  } else if (parse === 'exit') {
    passed = r.status === 0 ? 1 : 0;
    failed = r.status === 0 ? 0 : 1;
  }

  const ok = r.status === 0 && failed === 0 && passed !== null;
  if (!ok) {
    hardFail++;
    const why = out.split('\n').filter((l) => l.trim().startsWith('✗') || /Traceback|Error:/.test(l)).slice(0, 4);
    detail = [detail, ...why].filter(Boolean).join(' | ').slice(0, 400);
  }
  rows.push({ name, passed, failed, ok, secs, detail, status: r.status });
  const tally = passed === null ? '     ?' : `${String(passed).padStart(4)}/${String(passed + (failed || 0)).padEnd(4)}`;
  console.log(`  [${ok ? 'ok  ' : 'FAIL'}] ${name.padEnd(34)} ${tally}  ${secs}s${detail ? '\n         ' + detail : ''}`);
  return r;
}

function skip(name, why) {
  rows.push({ name, passed: 0, failed: 0, ok: true, skipped: true, secs: '0', detail: why });
  console.log(`  [skip] ${name.padEnd(34)}        ${why}`);
}

console.log('\n── guards and builds ───────────────────────────────────────────────');
run('guards (prebuild)', 'node', ['guards/run.mjs'], { parse: 'exit' });
// A NORMAL build first: it is the only way to prove the export ships no harness route and
// no harness globals, and the postbuild guards say so as they run. It also regenerates
// .next/types/validator.ts, which a harness build leaves referring to a route that no
// longer exists — so the typecheck runs after it, against what a normal build produces.
run('build (normal, static)', 'npm', ['run', 'build'], { parse: 'exit' });
run('typecheck', 'npx', ['tsc', '--noEmit', '-p', '.'], { parse: 'exit' });
run('lint', 'npx', ['eslint'], { parse: 'exit' });
// then the harness build, which every browser suite needs to serve
run('build:harness', 'npm', ['run', 'build:harness'], { parse: 'exit' });

console.log('\n── node suites ─────────────────────────────────────────────────────');
run('engine (next/tests)', 'node', ['tests/run.js']);
run('engine (root, control)', 'node', ['../tests/run.js']);

console.log('\n── browser suites: the port ────────────────────────────────────────');
run('e2e/run_all (ported root)', 'python3', ['tests/e2e/run_all.py',
  ...(LIVE ? ['--live-auth', '--live-push', '--live-pull'] : [])]);

const SCREENS = join('tests', 'e2e', 'screens');
for (const f of readdirSync(SCREENS).filter((x) => x.endsWith('.py') && !x.startsWith('_')).sort()) {
  run(`screens/${f}`, 'python3', [join(SCREENS, f)]);
}

console.log('\n── browser suites: the shell and the bridge ────────────────────────');
run('bridge/react_bridge', 'python3', ['tests/bridge/react_bridge.py']);
run('fidelity/shared_states', 'python3', ['tests/fidelity/shared_states.py']);
run('sync/config_injection', 'python3', ['tests/sync/config_injection.py']);
run('sync/loop_flag', 'python3', ['tests/sync/loop_flag.py']);

console.log('\n── PWA: its own build ──────────────────────────────────────────────');
// builds with NEXT_PUBLIC_BASE_PATH, snapshots, and restores the root harness build itself
run('pwa/subpath_hosting', 'python3', ['tests/pwa/subpath_hosting.py']);

console.log('\n── the root tree, as a control ─────────────────────────────────────');
// The root is read-only during the port, so this is not the port's gate — it is the
// evidence that the port changed nothing outside next/. It needs a server on 8123
// because one root suite hardcodes that port (RF-1).
let rootServed = false;
try {
  const res = await fetch('http://127.0.0.1:8123/', { signal: AbortSignal.timeout(3000) });
  rootServed = res.ok;
} catch { rootServed = false; }
if (rootServed) {
  run('root browser (control)', 'python3', ['tests/e2e/run_all.py'],
    { env: { ZAJIL_URL: 'http://127.0.0.1:8123/' }, cwd: '..' });
} else {
  skip('root browser (control)', 'needs `python3 -m http.server 8123` at the repo root (RF-1: one suite hardcodes it)');
}

console.log('\n── isolation ───────────────────────────────────────────────────────');
const iso = spawnSync('git', ['diff', '--stat', 'main..HEAD', '--', '.', ':(exclude)next/'],
  { encoding: 'utf8', cwd: '..' });
const isoClean = (iso.stdout || '').trim() === '';
rows.push({ name: 'isolation (main..HEAD outside next/)', passed: isoClean ? 1 : 0, failed: isoClean ? 0 : 1, ok: isoClean, secs: '0', detail: isoClean ? '' : iso.stdout.trim().slice(0, 300) });
if (!isoClean) hardFail++;
console.log(`  [${isoClean ? 'ok  ' : 'FAIL'}] ${'isolation'.padEnd(34)}        ${isoClean ? 'EMPTY' : iso.stdout.trim().slice(0, 200)}`);

if (!LIVE) {
  console.log('');
  skip('live suites', 'auth_live / push_live / pull_live write to or read the real project — `node scripts/gate.mjs --live`');
}

const counted = rows.filter((r) => !r.skipped && r.passed !== null);
const totalPass = counted.reduce((n, r) => n + r.passed, 0);
const totalFail = counted.reduce((n, r) => n + (r.failed || 0), 0);
const unparsed = rows.filter((r) => !r.skipped && r.passed === null);

console.log('\n═══════════════════════════════════════════════════════════════════');
console.log(`  ${totalPass} passed, ${totalFail} failed across ${counted.length} steps`
  + `${unparsed.length ? `, ${unparsed.length} UNCOUNTABLE` : ''}`
  + `, ${rows.filter((r) => r.skipped).length} skipped`
  + `  ·  ${((Date.now() - t0) / 60000).toFixed(1)} min`);
if (hardFail) {
  console.log(`  ${hardFail} step(s) FAILED:`);
  for (const r of rows.filter((x) => !x.ok)) console.log(`    ${r.name}${r.detail ? ' — ' + r.detail.slice(0, 200) : ''}`);
}
console.log('═══════════════════════════════════════════════════════════════════\n');
process.exit(hardFail ? 1 : 0);
