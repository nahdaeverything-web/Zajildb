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
  · THE URLS THE APP'S OWN LINKS POINT AT. `output: 'export'` writes `birds/`, not
    `birds/index.html`, while next/link renders `href="<base>/birds"` with no extension. Those
    only agree if the host resolves `/birds` to `birds/`. A python http.server does not do
    that, so no local suite has ever tested it, and if the host does not either then every
    in-app navigation 404s on a site that looks perfect at its root. So this walks the
    extensionless deep routes, which is also §g's "walk more than the root path".

Provisions nothing: the origin under test is the deployment."""
import json
import os
import re
import sys
import urllib.request
import uuid as _uuid

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

HERE = os.path.dirname(os.path.abspath(__file__))
NEXT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, 'screens'))
import _language as L                          # noqa: E402  the dictionary-derived detector

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
_u = urlparse(URL)
EXPECTED_SCOPE = _u.path or '/'
ORIGIN = f'{_u.scheme}://{_u.netloc}'      # hrefs resolve against this, not against the prefix

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

# ── THE SIGN-IN GATE (RULED 2026-10-07) ─────────────────────────────────────────────
# A configured deployment shows the sign-in screen on every route until a session exists, so
# every walk below signs in first. The backend host is read from the DEPLOYED sync-config.js
# and answered by a stub through request interception: the real project is never contacted
# and no credential is used — a session on this device is all the gate asks for. An
# unconfigured deployment has nothing to sign into and does not gate; then this is a no-op.
with urllib.request.urlopen(URL + 'sync-config.js', timeout=30) as _r:
    # the committed source says `url: '…'`; the INJECTED line is JSON, `"url":"…"` (scripts/inject-config.mjs).
    # On 2026-10-07 this knew only the first shape, read '' from a configured build, routed no stub — and the
    # gate's sign-in left for the real project. Both shapes now, and the net below catches any third.
    _m = re.search(r"""(?:"url"\s*:\s*"([^"]*)"|url:\s*'([^']*)')""", _r.read().decode('utf-8'))
BACKEND = ((_m.group(1) or _m.group(2)) if _m else '').rstrip('/')
# THE NET: any request to the backend host family that the stub does not answer is aborted here, never sent.
# Registered first, so it is the fallback behind the stub; `_escaped` must stay empty.
_BACKEND_FAMILY = re.compile(r'^https://[a-z0-9-]+\.supabase\.co/.*')
_escaped = []
def _net(route, request):
    _escaped.append(f'{request.method} {request.url[:80]}'); route.abort()
_seq = {'n': 0}
def _stub(route, request):
    if '/auth/v1/token' in request.url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-G', 'refresh_token': 'REFRESH-G', 'token_type': 'bearer', 'expires_in': 3600,
            'user': {'id': 'user-gate', 'email': 'gate@zajil.test'}})); return
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]'); out = []
        for r_ in rows: _seq['n'] += 1; out.append(dict(r_, server_seq=_seq['n'], owner='user-gate'))
        route.fulfill(status=200, content_type='application/json', body=json.dumps(out)); return
    route.fulfill(status=200, content_type='application/json', body='[]')
def stubbed(ctx_):
    ctx_.route(_BACKEND_FAMILY, _net)
    if BACKEND: ctx_.route(BACKEND + '/**', _stub)
    return ctx_
def through_gate(pg_):
    """If the gate is up, sign in through it (the only way past it) and wait for it to lift."""
    pg_.wait_for_timeout(1500)
    if pg_.locator('[data-testid=signin-screen][data-gate]').count() == 0: return False
    pg_.fill('[data-testid=f-email]', 'gate@zajil.test'); pg_.fill('[data-testid=f-password]', 'pw'); pg_.click('[data-testid=signin-submit]')
    try:
        pg_.wait_for_selector('[data-testid=signin-screen][data-gate]', state='detached', timeout=30000); pg_.wait_for_timeout(1200)
    except PlaywrightTimeoutError:
        # a counted failure, not a crash without a summary line — the net's check below must still print
        check('[GATE] the stub sign-in lifted the gate', False,
              pg_.evaluate("() => [...document.querySelectorAll('[data-testid^=msg-]')].map(e => e.innerText.replace(/\\n/g, ' ').slice(0, 80)).join(' | ')") or 'no message shown')
    return True

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = stubbed(br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                         user_agent='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 '
                                    '(KHTML, like Gecko) Chrome/126 Mobile Safari/537.36'))
    page = ctx.new_page()
    page.set_default_timeout(60000)
    errs, bad = [], []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('response', lambda r: bad.append(f'{r.status} {r.url}') if r.status >= 400 else None)

    # 'load', never 'networkidle': a page controlled by a service worker never goes idle
    page.goto(URL, wait_until='load'); page.wait_for_timeout(3000)
    gated = through_gate(page)
    check('[GATE] a configured deployment shows the sign-in gate to a device with no session, on the first route it opens',
          gated == bool(BACKEND), f'backend {"configured" if BACKEND else "not configured"} · gate seen: {gated}')

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
    # `trailingSlash: true` (RULED 2026-09-25) makes next/link render href="<base>/birds/"
    # and the export write birds/index.html. A directory WITH an index is the one thing every
    # static host serves identically, so this should hold anywhere — but "should" is exactly
    # what this suite exists to replace with a measurement, and GitHub Pages has never been
    # measured. Before the ruling the export wrote birds.html beside an INDEXLESS birds/
    # directory, and Pages does not list directories, so a cold visit to a deep link could
    # have 404d on a site that looked perfect at its root.
    #
    # Both shapes are asked: the trailing-slash form next/link renders, and the bare form a
    # human types or a chat app strips.
    #
    # This MUST run with the worker blocked. Measured 2026-09-25: with a worker installed
    # these checks passed against a server that answers /birds with a 301, because the worker
    # served the navigation from its precache and the network was never consulted. That is a
    # true statement about returning visitors and says nothing about the host — and a first
    # visit to a shared deep link is exactly the case that has no worker yet.
    cold = stubbed(br.new_context(viewport={'width': 390, 'height': 844}, service_workers='block'))
    cpage = cold.new_page(); cpage.set_default_timeout(60000)
    # the gate stands in front of a cold device too (RULED 2026-10-07); a session is what lets the walk
    # below prove the whole app at each deep link — six nav links — rather than the sign-in screen
    cpage.goto(URL + 'birds/', wait_until='load'); through_gate(cpage)
    for route in ('birds/', 'tools/', 'breeding/', 'birds', 'tools'):
        resp = cpage.goto(URL + route, wait_until='load')
        cpage.wait_for_timeout(1200)
        status = resp.status if resp else 0
        got = cpage.evaluate(VISIBLE_NAV_LINKS)
        shape = 'as next/link renders it' if route.endswith('/') else 'bare, as a human types it'
        check(f'COLD (no worker): /{route} is served as the app — {shape}',
              status == 200 and got == 6, f'HTTP {status}, {got} nav links at {URL + route}')

    cold.close()

    # ── seed over the real network, through the UI: a release build has no harness ──
    page.goto(URL, wait_until='load'); page.wait_for_timeout(2000)
    if page.locator('[data-testid=empty-example]').count():
        page.locator('[data-testid=empty-example]').click()
        page.wait_for_timeout(5000)
    page.goto(URL + 'birds/', wait_until='load'); page.wait_for_timeout(2500)
    rows = page.locator('[data-testid=bird-row]').count()
    check('the 38-bird example loaded from the live site', rows == 38, f'{rows} rows')

    # ── EVERY ROUTE THE EXPORT WROTE, AND EVERY LINK THE APP RENDERS ──────────────
    # ADDED 2026-09-25, after «أضف أول طائر» 404d on the live site and this gate passed.
    #
    # The hand-written list above walked three routes. It could not have caught that, and
    # neither could a list of ten: the broken control pointed at `/bird/new`, which is not a
    # route of this app at all. `/zajilv2/bird/new/` was 200 the whole time. So there are two
    # questions here and only the second one finds that class of defect:
    #
    #   A. is every route the export WROTE actually served?   (a deploy that dropped a file)
    #   B. does every href the app RENDERS resolve inside this deployment and answer 200?
    #      (a link that leaves the app — basePath missing, a raw <a> where next/link belongs)
    #
    # Both lists are DERIVED, never typed. A is the worker's own precache manifest, which is
    # generated from out/, fetched from the live origin so it describes what is deployed
    # rather than what is on this machine. B is the DOM: whatever the app puts in an href is
    # what a human can click, including controls no test author thought to name.
    with urllib.request.urlopen(URL + 'sw.js', timeout=30) as _r:
        _sw = _r.read().decode('utf-8')
    _shell = json.loads(re.search(r'const SHELL = (\[[\s\S]*?\n\]);', _sw).group(1))
    export_routes = sorted({u[:-len('index.html')] for u in _shell if u.endswith('/index.html')})
    check('the route list was derived from the deployment, not typed here',
          len(export_routes) >= 10, f'{len(export_routes)} routes from the served precache manifest')

    cold2 = br.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
    cp = cold2.new_page(); cp.set_default_timeout(60000)
    missing = []
    for r in export_routes:
        resp = cp.goto(ORIGIN + r, wait_until='load')
        cp.wait_for_timeout(350)
        if not resp or resp.status != 200:
            missing.append(f'{r} -> HTTP {resp.status if resp else "no response"}')
    check(f'[A] every one of the {len(export_routes)} routes the export wrote is served COLD',
          not missing, '; '.join(missing[:5]))

    # BOTH STATES, and the empty one is not optional. A seeded loft renders the register; an
    # EMPTY loft renders the first-run empty state, whose CTA is the only control it offers —
    # and that is the control a human found 404ing while this gate was green. Walking only the
    # seeded app would have caught the backup banner and missed the reported bug entirely.
    COLLECT = """() => [...document.querySelectorAll('a[href]')].map(a => ({
          href: a.getAttribute('href'), resolved: a.href,
          testid: a.getAttribute('data-testid') || '', text: (a.textContent||'').trim().slice(0,18) }))"""
    hrefs = {}
    empty = stubbed(br.new_context(viewport={'width': 390, 'height': 844}))
    ep = empty.new_page(); ep.set_default_timeout(60000)
    ep.goto(URL + 'birds/', wait_until='load'); through_gate(ep)       # the empty loft, signed in: the gate stands in front of it too
    for who, pg_ in (('empty loft', ep), ('seeded loft', page)):
        for r in export_routes:
            pg_.goto(ORIGIN + r, wait_until='load'); pg_.wait_for_timeout(700)
            for h in pg_.evaluate(COLLECT):
                # one representative per (testid, path): 38 bird rows are one link, 38 times
                if h['href'].startswith('#') or not h['resolved'].startswith(ORIGIN):
                    continue
                h['state'] = who
                hrefs.setdefault((h['testid'], h['resolved'].split('?')[0]), h)
    empty.close()
    check('links were actually found to check, in BOTH loft states (else this proves nothing)',
          len(hrefs) >= 8 and {h['state'] for h in hrefs.values()} == {'empty loft', 'seeded loft'},
          f"{len(hrefs)} distinct internal links across {len(export_routes)} routes; "
          f"states seen: {sorted({h['state'] for h in hrefs.values()})}")

    # (i) the cheap, decisive half: a link that leaves the deployment is broken by inspection
    escaped = [h for h in hrefs.values() if not h['resolved'].startswith(URL)]
    check('[B1] no rendered link points OUTSIDE this deployment',
          not escaped,
          '; '.join(f"{h['testid'] or h['text']!r} ({h['state']}) -> {h['href']}" for h in escaped[:5]))

    # (ii) and the ones that stay inside must actually answer
    dead = []
    for h in hrefs.values():
        if not h['resolved'].startswith(URL):
            continue
        resp = cp.goto(h['resolved'], wait_until='load')
        cp.wait_for_timeout(300)
        if not resp or resp.status != 200:
            dead.append(f"{h['testid'] or h['text']} {h['href']} -> HTTP {resp.status if resp else '?'}")
    check(f'[B2] every one of the {len(hrefs)} rendered links answers 200 COLD',
          not dead, '; '.join(dead[:5]))
    cold2.close()
    # ── [C] the language, on every surface at once ────────────────────────────────────
    # FOUND LIVE 2026-10-04, by a person, with this gate green: Arabic selected, and the desktop
    # rail read Birds / Breeding / Races… and the backup banner «More than 30 days since your
    # last export.» beside an Arabic page. The nav re-rendered only on a route change and the
    # banner only when it appeared, so each kept the language of its last render. Nothing here
    # had ever switched the language at all, and the rail does not exist at this suite's 390px.
    # So: through English and back WITHOUT a reload — the path that left them stale — at the
    # tab-bar width and at the rail's, then tab by tab, which is where chrome that outlives a
    # navigation shows what it kept. The detector is derived from the app's own dictionary
    # (screens/_language.py); the loft's own text is fetched from this origin and set aside.
    with urllib.request.urlopen(URL + 'example-loft-large.json', timeout=30) as _r:
        loft_text = L.strings_of(json.loads(_r.read().decode('utf-8')), set())
    for vw in (430, 1400):
        which = 'rail' if vw >= 1100 else 'tabbar'
        lctx = stubbed(br.new_context(viewport={'width': vw, 'height': 900}))
        lp = lctx.new_page(); lp.set_default_timeout(60000)
        lp.goto(URL + 'tools/', wait_until='load'); through_gate(lp)
        lp.wait_for_selector('[data-testid=set-lang], [data-row=lang]')
        L.open_row(lp, 'teaching')
        lp.click('[data-testid=load-large]'); lp.wait_for_timeout(4000)
        lp.wait_for_function("() => document.querySelectorAll('[data-testid=toast]').length === 0", timeout=20000)
        check(f'[C] @{vw} the {which} is the nav on screen and the backup banner is up (else this proves nothing)',
              lp.locator(f'[data-testid={which}]').is_visible() and len(L.nav_labels(lp, which)) == 6
              and lp.locator('[data-testid=backup-warn]').is_visible(), str(L.nav_labels(lp, which)))
        L.set_lang(lp, 'en', 1200)
        check(f'[C] @{vw} «English» tapped: the {which} and the banner answer at once, with the page',
              L.nav_labels(lp, which) == L.NAV['en']
              and lp.locator('[data-testid=backup-warn] span').inner_text().strip() == L.BANNER['en'],
              f"{L.nav_labels(lp, which)} / «{lp.locator('[data-testid=backup-warn] span').inner_text().strip()[:40]}»")
        lp.reload(wait_until='load'); lp.wait_for_timeout(2500)
        check(f'[C] @{vw} reloaded with English stored: the {which} comes back in English',
              L.nav_labels(lp, which) == L.NAV['en'], str(L.nav_labels(lp, which)))
        L.tab(lp, '/birds', 1800); L.tab(lp, '/tools', 1800)
        L.set_lang(lp, 'ar', 1200)
        check(f'[C] @{vw} «العربية» tapped after English: the {which} reads Arabic',
              L.nav_labels(lp, which) == L.NAV['ar'], str(L.nav_labels(lp, which)))
        check(f'[C] @{vw} …and so does the backup banner',
              lp.locator('[data-testid=backup-warn] span').inner_text().strip() == L.BANNER['ar'],
              f"«{lp.locator('[data-testid=backup-warn] span').inner_text().strip()[:48]}»")
        english = [('tools · ' + w, s_, k) for w, s_, k in L.leaks(lp, 'ar', loft_text)]
        for href in L.TABS:
            L.tab(lp, href, 1800)
            english += [(f'{href} · {w}', s_, k) for w, s_, k in L.leaks(lp, 'ar', loft_text)]
        check(f'[C] @{vw} …and NO visible UI string renders in English, there or on any of the six tabs',
              not english, L.say(english))
        lctx.close()
    check('[C] the language scan was not vacuous', L.STATS['scanned'] >= 800, f"{L.STATS['scanned']} visible strings examined")

    # leave `page` where the offline section expects it: the walk above ended on whatever
    # route came last, and reloading THERE offline counts zero bird rows for a reason that
    # has nothing to do with offline.
    page.goto(URL + 'birds/', wait_until='load'); page.wait_for_timeout(2000)

    # ── offline ───────────────────────────────────────────────────────────────────
    ctx.set_offline(True)
    page.reload(wait_until='load'); page.wait_for_timeout(2500)
    check('OFFLINE: app boots with no connection', page.evaluate(VISIBLE_NAV_LINKS) == 6)
    check('[GATE] OFFLINE: a signed-in device goes straight through — the session is read locally, nothing is asked of the network',
          page.locator('[data-testid=signin-screen][data-gate]').count() == 0)
    rows_off = page.locator('[data-testid=bird-row]').count()
    check('OFFLINE: data intact', rows_off == 38, f'{rows_off} rows')

    page.goto(URL + 'pedigree/?id=' + bird_id('g5-faris26'), wait_until='load')
    page.wait_for_timeout(2000)
    badge = (page.locator('[data-testid=coi-headline] [data-testid=coi-badge]').inner_text()
             if page.locator('[data-testid=coi-headline] [data-testid=coi-badge]').count() else 'none')
    check('OFFLINE: pedigree + COI compute on a deep route', '12.5' in badge, badge)

    ctx.set_offline(False)
    check('zero page errors', not errs, '; '.join(errs[:2]))
    check('[GATE] every request to the backend host was answered by the stub — nothing reached the real project',
          not _escaped, '; '.join(_escaped[:3]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
