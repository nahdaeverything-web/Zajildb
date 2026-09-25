#!/usr/bin/env python3
"""THE DEPLOY GATE — the ported copy. CUTOVER.md §g stage 2, RULED 2026-09-25.

    ZAJIL_LIVE_URL=https://nahdaeverything-web.github.io/zajilv2/ python3 tests/e2e/live_deployment.py

WHAT THIS IS FOR. Every other suite in this tree proves the app against a build on this
machine. None of them can prove what a host actually serves — and the gap between those two
is where a deploy fails: a worker baked for the wrong prefix, a cache key shared with another
app, a static host that will not serve the URLs the app's own links point at. This suite runs
against a real origin over the real internet and asks only questions that a local server
cannot answer.

WHY THE VANILLA ORIGINAL COULD NOT BE THIS GATE (§0.4). It is a vanilla detector, and
usefully so — green against a rolled-back origin it proves the browser got vanilla and not
the port, which is exactly what a rollback asks. But as a gate for the PORT it fails on three
counts, all fixed here:

  · THE URL AND SCOPE WERE HARD-CODED to `/Zajildb/`. `run_all.py:9` documented a
    ZAJIL_LIVE_URL env var and nothing read it; the original's `import os` was unused. Against
    any other origin it failed at the scope assertion for a reason with nothing to do with the
    app. Here the URL comes from the environment and the expected scope is DERIVED from it.
  · EVERY DOM TOKEN WAS VANILLA-ONLY — `.nav-link`, `.empty-state button`, `.bird-row`,
    `.coi-headline .coi-badge`, and a hash route `#/pedigree/<id>` that a path-routed static
    export cannot serve. The substitutions are the five that `tests/pwa/subpath_hosting.py`
    already documents.
  · `wait_until='networkidle'` — a page controlled by a service worker never goes idle, so
    that is a timeout waiting to happen. Never used here.

AND TWO THINGS THE ORIGINAL DID NOT ASK, both of which are the whole point of this deploy:

  · THE EXACT CACHE VERSION, not `any('zajil-' in k)`. §0.1: the port and vanilla both named
    `zajil-v1.9.1`, so they were the same CacheStorage key and neither worker's activate sweep
    could ever evict the other. `any('zajil-')` is true in precisely the broken case. This
    asserts the key is EXACTLY what this build stamped, and that NO other `zajil-` cache is
    left beside it.
  · THE URLS THE APP'S OWN LINKS POINT AT. `output: 'export'` writes `birds.html`, not
    `birds/index.html`, while next/link renders `href="<base>/birds"` with no extension. Those
    only agree if the host resolves `/birds` to `birds.html`. A python http.server does not do
    that, so no local suite has ever tested it, and if the host does not either then every
    in-app navigation 404s on a site that looks perfect at its root. So this walks the
    extensionless deep routes, which is also §g's "walk more than the root path".

Provisions nothing: the origin under test is the deployment."""
import os
import sys
import uuid as _uuid

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
NEXT = os.path.abspath(os.path.join(HERE, '..', '..'))

# ── what to test, and what to expect of it ────────────────────────────────────────
URL = (os.environ.get('ZAJIL_LIVE_URL') or '').strip()
if not URL:
    print('✗ ZAJIL_LIVE_URL is not set.\n'
          '  This suite tests a DEPLOYED origin; it has no default and will not invent one —\n'
          '  a hard-coded URL is exactly what made the vanilla copy unusable as a gate.\n'
          '  e.g. ZAJIL_LIVE_URL=https://nahdaeverything-web.github.io/zajilv2/')
    sys.exit(2)
if not URL.endswith('/'):
    URL += '/'

# The expected cache key comes from the SAME source the worker's does — package.json, which
# scripts/build-sw.mjs composes into 'zajil-v' + version. Overridable for testing an origin
# that is deliberately behind.
import json
_pkg = json.load(open(os.path.join(NEXT, 'package.json'), encoding='utf-8'))
EXPECTED_VERSION = os.environ.get('ZAJIL_EXPECTED_VERSION') or ('zajil-v' + _pkg['version'])

# The scope is DERIVED from the URL, never asserted against a literal.
from urllib.parse import urlparse
EXPECTED_SCOPE = urlparse(URL).path or '/'

# The shipped datasets carry real uuids. Python's uuid5 derives exactly what tools/idmap.js
# derives from the same namespace and key, so this suite names birds by the readable key.
_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c:
        ok += 1; print(f'  ✓ {n}')
    else:
        fail += 1; print(f'  ✗ {n}  {e}')

print(f'origin   {URL}')
print(f'expect   cache {EXPECTED_VERSION} · scope {EXPECTED_SCOPE}')
print()

# both navs render the same six tabs and CSS decides which is on screen, so a plain count is
# 12 — ask the one that is actually visible
VISIBLE_NAV_LINKS = """() => {
  const navs = [...document.querySelectorAll('nav')].filter((n) => getComputedStyle(n).display !== 'none');
  return navs.reduce((a, n) => a + n.querySelectorAll('[data-testid=nav-link]').length, 0);
}"""

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                         user_agent='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 '
                                    '(KHTML, like Gecko) Chrome/126 Mobile Safari/537.36')
    page = ctx.new_page()
    page.set_default_timeout(60000)
    errs, bad = [], []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('response', lambda r: bad.append(f'{r.status} {r.url}') if r.status >= 400 else None)

    # 'load', never 'networkidle': a page controlled by a service worker never goes idle
    page.goto(URL, wait_until='load'); page.wait_for_timeout(3000)

    check('secure context (HTTPS)', page.evaluate('window.isSecureContext'))
    n = page.evaluate(VISIBLE_NAV_LINKS)
    check('app rendered — six nav links in the visible nav', n == 6, f'{n} links')
    check('no failed requests', not bad, '; '.join(bad[:3]))

    sw = page.evaluate("async () => { const r = await navigator.serviceWorker.getRegistration();"
                       " return r ? r.scope : 'none'; }")
    check('service worker registered at the scope this origin implies',
          sw.endswith(EXPECTED_SCOPE), f'{sw} does not end with {EXPECTED_SCOPE}')

    keys = page.evaluate('async () => await caches.keys()')
    check(f'the cache is EXACTLY {EXPECTED_VERSION}', EXPECTED_VERSION in keys, str(keys))
    strays = [k for k in keys if k.startswith('zajil-') and k != EXPECTED_VERSION]
    check('…and no other zajil- cache is left beside it (§0.1: a shared key evicts nothing)',
          not strays, str(strays))

    man = page.evaluate("""async () => { const l = document.querySelector('link[rel=manifest]');
        if (!l) return { ok: false, why: 'no manifest link' };
        const r = await fetch(l.href); const j = await r.json();
        // start_url is RELATIVE ('./') by design, so one manifest works at any prefix.
        // Resolve it the way a browser does rather than string-matching a path that was
        // never meant to be absolute.
        return { ok: r.ok, name: j.name, raw: j.start_url, display: j.display,
                 icons: (j.icons || []).length,
                 start: new URL(j.start_url ?? './', l.href).href,
                 scope: new URL(j.scope ?? './', l.href).href }; }""")
    check('manifest valid & installable',
          man.get('ok') and man.get('display') == 'standalone' and man.get('icons', 0) >= 3, str(man))
    # a relative start_url is correct; what matters is where it RESOLVES
    check('…and its start_url resolves inside this deployment, not some other prefix',
          str(man.get('start', '')).startswith(URL),
          f"raw {man.get('raw')!r} resolves to {man.get('start')!r}, expected under {URL}")

    # ── the URLs the app's own links point at, asked of the HOST ──────────────────
    # next/link renders these WITHOUT .html; the export writes birds.html and, beside it, a
    # birds/ directory holding only RSC .txt payloads. Those only agree if the host resolves
    # /birds to birds.html — and GitHub Pages does not list directories, so if it prefers the
    # indexless directory instead, a COLD visit to any deep link 404s.
    #
    # This MUST run with the worker blocked. Measured 2026-09-25: with a worker installed
    # these checks passed against a server that answers /birds with a 301, because the worker
    # served the navigation from its precache and the network was never consulted. That is a
    # true statement about returning visitors and says nothing about the host — and a first
    # visit to a shared deep link is exactly the case that has no worker yet.
    cold = br.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
    cpage = cold.new_page(); cpage.set_default_timeout(60000)
    for route in ('birds', 'tools', 'breeding'):
        resp = cpage.goto(URL + route, wait_until='load')
        cpage.wait_for_timeout(1200)
        status = resp.status if resp else 0
        got = cpage.evaluate(VISIBLE_NAV_LINKS)
        check(f'COLD (no worker): /{route} is served as the app — the host resolves it to {route}.html',
              status == 200 and got == 6, f'HTTP {status}, {got} nav links at {URL + route}')
    cold.close()

    # ── seed over the real network, through the UI: a release build has no harness ──
    page.goto(URL, wait_until='load'); page.wait_for_timeout(2000)
    if page.locator('[data-testid=empty-example]').count():
        page.locator('[data-testid=empty-example]').click()
        page.wait_for_timeout(5000)
    page.goto(URL + 'birds', wait_until='load'); page.wait_for_timeout(2500)
    rows = page.locator('[data-testid=bird-row]').count()
    check('the 38-bird example loaded from the live site', rows == 38, f'{rows} rows')

    # ── offline ───────────────────────────────────────────────────────────────────
    ctx.set_offline(True)
    page.reload(wait_until='load'); page.wait_for_timeout(2500)
    check('OFFLINE: app boots with no connection', page.evaluate(VISIBLE_NAV_LINKS) == 6)
    rows_off = page.locator('[data-testid=bird-row]').count()
    check('OFFLINE: data intact', rows_off == 38, f'{rows_off} rows')

    page.goto(URL + 'pedigree?id=' + bird_id('g5-faris26'), wait_until='load')
    page.wait_for_timeout(2000)
    badge = (page.locator('[data-testid=coi-headline] [data-testid=coi-badge]').inner_text()
             if page.locator('[data-testid=coi-headline] [data-testid=coi-badge]').count() else 'none')
    check('OFFLINE: pedigree + COI compute on a deep route', '12.5' in badge, badge)

    ctx.set_offline(False)
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
