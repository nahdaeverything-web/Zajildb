#!/usr/bin/env python3
"""The coordinator's boot contract (REWRITTEN 2026-11-13, RF-19 — it used to assert the OPPOSITE: "startSyncLoop() runs
only with ?sync=1").

  · by default the loop IS started at boot, on every route, by src/components/SyncCoordinator.tsx;
  · with the shipped empty config it is inert — sync hidden, nothing armed, nothing sent;
  · it can be stopped, and stopping it leaves nothing armed;
  · the harness-only test switch keeps it from starting (the postbuild guard proves a NORMAL build cannot carry it).
"""
import sys, os
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from _serve import serve
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed; passed += ok; failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + d) if d else ''}")
srv, BASE = serve()
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for label, init, want in (('default', '', True), ('test-only switch', 'globalThis.__ZAJIL_TEST_NO_AUTOSYNC = true;', False)):
            ctx = b.new_context(); reqs = []
            if init: ctx.add_init_script(init)
            pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('request', lambda r: reqs.append(r.url) if ('/rest/v1/' in r.url or '/auth/v1/' in r.url) else None)
            pg.goto(BASE, wait_until='load'); pg.wait_for_timeout(1500)
            pg.evaluate("async () => { await window.__zajilReady; }"); pg.wait_for_timeout(800)
            r = pg.evaluate("async () => { const db = await window.__zajilDb; return { loop: db.syncLoopState(), state: db.syncStatus().state, status: document.getElementById('harness-status').textContent }; }")
            check(f"{label}: initDB reached ready", r['status'] == 'ready', r['status'])
            check(f"{label}: the loop is {'STARTED at boot by the coordinator' if want else 'NOT started'}", r['loop']['on'] == want, str(r['loop']))
            check(f"{label}: empty config → state 'hidden', and INERT — no timer armed, no cycle in flight, no request sent", r['state'] == 'hidden' and not r['loop']['timerArmed'] and not r['loop']['inFlight'] and not reqs, f"{r['state']} {r['loop']} {reqs[:2]}")
            if want:
                st = pg.evaluate("async () => { const db = await window.__zajilDb; const stop = db.startSyncLoop(); const on = db.syncLoopState().on; stop(); return { on, after: db.syncLoopState() }; }")
                check("default: the loop can be stopped, and stopped it leaves nothing armed", st['on'] is True and st['after']['on'] is False and not st['after']['timerArmed'], str(st))
            check(f"{label}: zero page errors", not errs, str(errs))
            ctx.close()
        b.close()
finally: srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
