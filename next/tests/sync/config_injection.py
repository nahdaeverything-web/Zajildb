#!/usr/bin/env python3
"""3.1 — the shipped config is EMPTY and sync is inert; the suites' add_init_script
injection makes syncConfig() configured. Zero new mechanism: syncConfig() reads
globalThis.ZAJIL_SYNC_CONFIG at call time (sync.js:76-81), byte-identical to root."""
import sys, hashlib, os
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from _serve import serve
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed; passed += ok; failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + d) if d else ''}")
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
check('next/src/sync-config.js byte-identical to js/sync-config.js', h(f'{ROOT}/js/sync-config.js') == h(f'{ROOT}/next/src/sync-config.js'), h(f'{ROOT}/next/src/sync-config.js'))
check('next/src/db/sync.js byte-identical to js/db/sync.js', h(f'{ROOT}/js/db/sync.js') == h(f'{ROOT}/next/src/db/sync.js'), h(f'{ROOT}/next/src/db/sync.js'))
srv, BASE = serve()
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        # (1) nothing injected — the shipped state
        pg = b.new_page(); pg.goto(BASE, wait_until='load'); pg.wait_for_timeout(1200)
        c0 = pg.evaluate("async () => { const db = await window.__zajilDb; return db.syncConfig(); }")
        st0 = pg.evaluate("async () => (await window.__zajilDb).syncStatus().state")
        check('nothing injected → configured === false', c0['configured'] is False, str(c0))
        check("nothing injected → url '' and publishableKey ''", c0['url'] == '' and c0['publishableKey'] == '')
        check("nothing injected → syncStatus().state === 'hidden' (sync inert)", st0 == 'hidden', st0)
        pg.close()
        # (2) the suites' injection, verbatim shape (auth.py:69)
        ctx = b.new_context()
        ctx.add_init_script("globalThis.ZAJIL_SYNC_CONFIG = { url: 'https://stub.zajil.test', publishableKey: 'sb_publishable_TEST' };")
        pg = ctx.new_page(); pg.goto(BASE, wait_until='load'); pg.wait_for_timeout(1200)
        c1 = pg.evaluate("async () => { const db = await window.__zajilDb; return db.syncConfig(); }")
        check('injected → configured === true', c1['configured'] is True, str(c1))
        check("injected → url reads back 'https://stub.zajil.test'", c1['url'] == 'https://stub.zajil.test')
        check("injected → publishableKey reads back 'sb_publishable_TEST'", c1['publishableKey'] == 'sb_publishable_TEST')
        check("injected but signed out → state still 'hidden'", pg.evaluate("async () => (await window.__zajilDb).syncStatus().state") == 'hidden')
        b.close()
finally: srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
