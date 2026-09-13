#!/usr/bin/env python3
"""Run the Phase-2 (DB-ONLY) browser suites against the port's test-harness route.

    cd next && npm run build:harness && python3 tests/e2e/run_all.py

The suites are copies of tests/e2e/*.py changing ONLY the module token
(`import('./js/db.js')` → `window.__zajilDb`). The app URL is not edited in
any suite: each reads ZAJIL_URL, which this runner sets. The server is
provisioned HERE, on an ephemeral port, serving next/out — a test that depends
on a server it did not start can be green about the wrong tree (R6).
"""
import os, subprocess, sys, glob, socket, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'out'))
ROUTE = 'test-harness.html'

if not os.path.exists(os.path.join(OUT, ROUTE)):
    print(f'  no {ROUTE} in {OUT} — run `npm run build:harness` first (a normal build must NOT produce it)')
    sys.exit(2)

s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '-d', OUT, '--bind', '127.0.0.1'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
env = dict(os.environ, ZAJIL_URL=f'http://127.0.0.1:{port}/{ROUTE}')
print(f'  serving {OUT} on 127.0.0.1:{port} → ZAJIL_URL={env["ZAJIL_URL"]}')

# Live suites are OPT-IN, as in the root runner: they need the internet and
# credentials, and push_live WRITES to the real project. A suite that does not
# run is printed as skipped, never silently absent.
OPT_IN = {
    'push_live.py': ('--live-push', 'needs the internet and live credentials, and WRITES to the real project'),
    'pull_live.py': ('--live-pull', 'needs the internet and live credentials; reads the real project'),
    'auth_live.py': ('--live-auth', 'needs the internet and live credentials, and WRITES to the real project (the sign-in screen runs the first-login cycle)'),
    'import_boundary.py': ('--boundary', 'seeds ~537 MB of media and writes a file of the same order — slow and disk-hungry, not slow-and-flaky'),
}
SUITES = sorted(f for f in glob.glob(os.path.join(HERE, '*.py')) if os.path.basename(f) not in ({'run_all.py'} | set(OPT_IN)))
skipped = []
for _name, (_flag, _reason) in OPT_IN.items():
    if _flag in sys.argv: SUITES.append(os.path.join(HERE, _name))
    else: skipped.append((_name, _flag, _reason))
SUITES = sorted(SUITES)
total_pass = total_fail = 0
failed_suites = []
try:
    for path in SUITES:
        name = os.path.basename(path)
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600, env=env)
        out = (r.stdout or '') + (r.stderr or '')
        last = [l for l in out.strip().splitlines() if 'passed' in l]
        summary = last[-1].strip() if last else '(no summary — suite errored)'
        p = f = 0
        if last:
            try:
                parts = summary.replace(',', '').split()
                p = int(parts[parts.index('passed') - 1]); f = int(parts[parts.index('failed') - 1])
            except (ValueError, IndexError):
                pass
        total_pass += p; total_fail += f
        flag = 'ok  ' if (f == 0 and r.returncode == 0) else 'FAIL'
        if flag == 'FAIL':
            failed_suites.append(name)
            for line in out.splitlines():
                if line.strip().startswith('✗') or 'Error' in line or 'Traceback' in line:
                    summary += '\n        ' + line.strip()[:160]
        print(f'  [{flag}] {name:26} {summary}')
finally:
    srv.terminate()
for _name, _flag, _reason in skipped:
    print(f'  [skip] {_name:26} not run — {_reason} (add {_flag})')
print(f"  [elsewhere] {'subpath_hosting.py':22} tests/pwa/subpath_hosting.py — needs its own build "
      "(basePath is baked into the export), so it builds, snapshots and restores out/ itself: "
      "`python3 tests/pwa/subpath_hosting.py`")
print(f'\n  {total_pass} assertions passed, {total_fail} failed, {len(failed_suites)} suite(s) errored' + (f', {len(skipped)} skipped' if skipped else ''))
sys.exit(1 if (total_fail or failed_suites) else 0)
