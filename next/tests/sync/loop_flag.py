#!/usr/bin/env python3
"""3.2 — startSyncLoop() runs only with ?sync=1. Both states proved."""
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
        for url, want in ((BASE, False), (BASE + '?sync=1', True)):
            pg = b.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(url, wait_until='load'); pg.wait_for_timeout(1500)
            pg.evaluate("async () => { await window.__zajilReady; }")
            r = pg.evaluate("async () => ({ loop: typeof window.__zajilSyncLoop, state: (await window.__zajilDb).syncStatus().state, status: document.getElementById('harness-status').textContent })")
            label = '?sync=1' if want else 'default'
            check(f"{label}: initDB reached ready", r['status'] == 'ready', r['status'])
            check(f"{label}: loop {'STARTED (stop fn on window)' if want else 'NOT started (null)'}", (r['loop'] == 'function') == want, f"typeof __zajilSyncLoop = {r['loop']}")
            check(f"{label}: empty config → state 'hidden' (loop inert)", r['state'] == 'hidden', r['state'])
            if want:
                check("?sync=1: stop() returns cleanly", pg.evaluate("() => { try { window.__zajilSyncLoop(); return true; } catch (e) { return String(e); } }") is True)
            check(f"{label}: zero page errors", not errs, str(errs))
            pg.close()
        b.close()
finally: srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
