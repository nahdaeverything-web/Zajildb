#!/usr/bin/env python3
"""Run every browser suite against a locally served Zajil and summarise.

    cd /path/to/zajil && python3 -m http.server 8123 &
    python3 tests/e2e/run_all.py

Env:
    ZAJIL_URL        base URL for the local suites (default http://127.0.0.1:8123/)
    ZAJIL_LIVE_URL   base URL for live_deployment.py (default the GitHub Pages site)

live_deployment.py is skipped unless --live is passed, since it needs the
internet and exercises the deployed build rather than the working tree.
"""
import os, subprocess, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))

# Suites that are NOT part of the default run, with the reason shown in the
# output. A suite must never be silently absent: if it does not run, the
# summary says so and why.
OPT_IN = {
    'live_deployment.py': (
        '--live',
        'needs the internet and tests the DEPLOYED build, not the working tree',
    ),
}

LOCAL = sorted(f for f in glob.glob(os.path.join(HERE, '*.py'))
               if os.path.basename(f) not in ({'run_all.py'} | set(OPT_IN)))
skipped = []
for name, (flag, reason) in OPT_IN.items():
    if flag in sys.argv:
        LOCAL.append(os.path.join(HERE, name))
    else:
        skipped.append((name, flag, reason))
LOCAL = sorted(LOCAL)

total_pass = total_fail = 0
failed_suites = []
for path in LOCAL:
    name = os.path.basename(path)
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600)
    out = (r.stdout or '') + (r.stderr or '')
    last = [l for l in out.strip().splitlines() if 'passed' in l]
    summary = last[-1].strip() if last else '(no summary — suite errored)'
    p = f = 0
    if last:
        try:
            parts = summary.replace(',', '').split()
            p = int(parts[parts.index('passed') - 1])
            f = int(parts[parts.index('failed') - 1])
        except (ValueError, IndexError):
            pass
    total_pass += p; total_fail += f
    flag = 'ok  ' if (f == 0 and r.returncode == 0) else 'FAIL'
    if flag == 'FAIL':
        failed_suites.append(name)
        for line in out.splitlines():
            if line.strip().startswith('✗'):
                summary += '\n        ' + line.strip()
    print(f'  [{flag}] {name:26} {summary}')

for name, flag, reason in skipped:
    print(f'  [skip] {name:26} not run — {reason} (add {flag})')

print(f'\n  {total_pass} assertions passed, {total_fail} failed, '
      f'{len(failed_suites)} suite(s) errored'
      + (f', {len(skipped)} skipped' if skipped else ''))
sys.exit(1 if (total_fail or failed_suites) else 0)
