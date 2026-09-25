#!/usr/bin/env python3
"""3.1 — the shipped config is EMPTY and sync is inert; the suites' add_init_script
injection makes syncConfig() configured. Zero new mechanism: syncConfig() reads
globalThis.ZAJIL_SYNC_CONFIG at call time (sync.js:76-81), byte-identical to root.

ALSO, since 2026-09-25: THE CONFIG INJECTION POINT (CUTOVER §a.3). A release has to reach a
real project while the repository stays sync-inert and the guards stay honest. The mechanism
is one committed-empty public asset, `public/sync-config.js`, loaded beforeInteractive and
rewritten by `scripts/inject-config.mjs` AFTER the guards run and BEFORE upload.

Three properties are asserted here because each one, if it silently broke, would be found in
production instead:

  · THE REPOSITORY STAYS INERT. The committed file must be empty. If it is ever filled in,
    this suite fails before any browser starts — a live project URL in a public repo is the
    thing §a.3 exists to prevent.
  · THE MECHANISM ACTUALLY RUNS. Next does NOT emit a plain <script src> for
    beforeInteractive in the App Router: it emits a <link rel=preload> plus a push onto
    `self.__next_s`, which its runtime drains. Reading the strategy name out of the source
    proves nothing about whether the file executed, so this asserts that
    globalThis.ZAJIL_SYNC_CONFIG is actually SET in the page — and set to the empty shape,
    which is the inert state and the running state at once.
  · THE INJECTOR REFUSES WHAT WOULD BE A CATASTROPHE. It runs after the guards, so the guards
    cannot help it. A secret key or a legacy service_role JWT in a static export exposes
    every row in the project to anyone who views source. Both are refused by shape, and both
    must leave the file untouched — "it failed" is not enough if it wrote first.
"""
import sys, hashlib, os, json, subprocess, tempfile, shutil
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from _serve import serve
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed; passed += ok; failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + d) if d else ''}")
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
check('next/src/sync-config.js byte-identical to js/sync-config.js', h(f'{ROOT}/js/sync-config.js') == h(f'{ROOT}/next/src/sync-config.js'), h(f'{ROOT}/next/src/sync-config.js'))
check('next/src/db/sync.js byte-identical to js/db/sync.js', h(f'{ROOT}/js/db/sync.js') == h(f'{ROOT}/next/src/db/sync.js'), h(f'{ROOT}/next/src/db/sync.js'))

# ── the injection point: the committed file is EMPTY ──────────────────────────────
NEXT = f'{ROOT}/next'
pub = io_read = open(f'{NEXT}/public/sync-config.js', encoding='utf-8').read()
check('public/sync-config.js is committed EMPTY — the repository stays sync-inert',
      "url: '', publishableKey: ''" in pub, pub.strip().splitlines()[-1][:80])
# the guard that keeps this file from breaking every sync suite in the tree
check('…and it supplies a DEFAULT rather than clobbering a pre-set config',
      'globalThis.ZAJIL_SYNC_CONFIG = globalThis.ZAJIL_SYNC_CONFIG ||' in pub)
for needle, what in (('supabase.co', 'a Supabase host'), ('sb_publishable_', 'a publishable key'),
                     ('sb_' + 'secret_', 'a secret key'), ('eyJ', 'a JWT')):
    check(f'…and carries no {what}', needle not in pub)

# ── the injector refuses what the guards can no longer catch ──────────────────────
# It runs on a finished export, so give it a throwaway one: a directory with out/sync-config.js.
def inject(url, key):
    d = tempfile.mkdtemp()
    try:
        os.makedirs(f'{d}/out')
        shutil.copy(f'{NEXT}/public/sync-config.js', f'{d}/out/sync-config.js')
        before = h(f'{d}/out/sync-config.js')
        env = dict(os.environ, ZAJIL_SUPABASE_URL=url, ZAJIL_SUPABASE_PUBLISHABLE_KEY=key)
        r = subprocess.run(['node', f'{NEXT}/scripts/inject-config.mjs'], cwd=d, env=env,
                           capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip(), h(f'{d}/out/sync-config.js') == before
    finally:
        shutil.rmtree(d, ignore_errors=True)

def jwt(role):
    import base64
    body = base64.urlsafe_b64encode(json.dumps({'role': role, 'iss': 'supabase'}).encode()).decode().rstrip('=')
    return f'eyJhbGciOiJIUzI1NiJ9.{body}.sig'

URL = 'https://example-project.supabase.co'
for label, key in (('a SECRET key', 'sb_' + 'secret_' + 'A' * 16),
                   ('a legacy service_role JWT', jwt('service_' + 'role')),
                   ('a JWT whose role is neither anon nor service_role', jwt('authenticated')),
                   ('a key that is neither publishable nor a JWT', 'hunter2')):
    code, out, untouched = inject(URL, key)
    check(f'the injector REFUSES {label}', code == 1, out.splitlines()[0][:96] if out else '(no output)')
    check(f'…and wrote nothing when it refused {label}', untouched)

code, out, untouched = inject('ftp://example-project.supabase.co', 'sb_publishable_' + 'A' * 16)
check('the injector REFUSES a URL that is not an https origin', code == 1 and untouched, out.splitlines()[0][:96])
code, out, _ = inject('', '')
check('the injector REFUSES an empty configuration rather than writing blanks', code == 1,
      out.splitlines()[0][:96])

for label, key in (('a publishable key', 'sb_publishable_' + 'A' * 16),
                   ('a legacy ANON JWT — the case §0.3 found the guard blind to', jwt('anon'))):
    code, out, untouched = inject(URL, key)
    check(f'the injector ACCEPTS {label}', code == 0 and not untouched, out.splitlines()[0][:96])

srv, BASE = serve()
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        # (1) nothing injected — the shipped state
        pg = b.new_page(); pg.goto(BASE, wait_until='load'); pg.wait_for_timeout(1200)
        # the injection point RAN. Next emits beforeInteractive as a preload plus a push onto
        # self.__next_s, not as a <script src>, so the only honest test is whether the global
        # is actually set in the page.
        g0 = pg.evaluate("() => globalThis.ZAJIL_SYNC_CONFIG ?? null")
        check('public/sync-config.js executed — globalThis.ZAJIL_SYNC_CONFIG is SET', g0 is not None, str(g0))
        check("…and it is the INERT shape: url '' and publishableKey ''",
              isinstance(g0, dict) and g0.get('url') == '' and g0.get('publishableKey') == '', str(g0))
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
