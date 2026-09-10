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

SUITES = sorted(f for f in glob.glob(os.path.join(HERE, '*.py')) if os.path.basename(f) != 'run_all.py')
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
print(f'\n  {total_pass} assertions passed, {total_fail} failed, {len(failed_suites)} suite(s) errored')
sys.exit(1 if (total_fail or failed_suites) else 0)
