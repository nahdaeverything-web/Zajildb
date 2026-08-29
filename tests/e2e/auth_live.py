# tests/e2e/auth_live.py — the same handshake as auth.py, but against the REAL
# Supabase project. Opt-in: it needs the internet and live credentials.
#
# NO CREDENTIAL IS COMMITTED. Everything comes from the environment:
#
#   ZAJIL_LIVE_SUPABASE_URL   project URL
#   ZAJIL_LIVE_PUBLISHABLE_KEY  sb_publishable_… (safe to hold in a client)
#   ZAJIL_LIVE_EMAIL / ZAJIL_LIVE_PASSWORD   a test account
#
# PRECONDITION GATE. If any of those is missing the suite reports NOT RUN and
# exits non-zero rather than printing "0 passed". A suite that passes because
# it did nothing is worse than one that fails: it reports safety it never
# checked. (Learned the hard way in the storage spike, where an empty bucket
# denied everyone and four meaningless assertions came back green.)
import json, os, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
URL = os.environ.get('ZAJIL_LIVE_SUPABASE_URL', '')
KEY = os.environ.get('ZAJIL_LIVE_PUBLISHABLE_KEY', '')
EMAIL = os.environ.get('ZAJIL_LIVE_EMAIL', '')
PASSWORD = os.environ.get('ZAJIL_LIVE_PASSWORD', '')

missing = [n for n, v in [('ZAJIL_LIVE_SUPABASE_URL', URL), ('ZAJIL_LIVE_PUBLISHABLE_KEY', KEY),
                          ('ZAJIL_LIVE_EMAIL', EMAIL), ('ZAJIL_LIVE_PASSWORD', PASSWORD)] if not v]
if missing:
    print(f'  NOT RUN — no live credentials in the environment: {", ".join(missing)}')
    print('  0 passed, 0 failed  (nothing was checked)')
    sys.exit(2)

if not KEY.startswith('sb_publishable_'):
    print(f'  REFUSING TO RUN — ZAJIL_LIVE_PUBLISHABLE_KEY is not a publishable key '
          f'(starts "{KEY[:8]}…"). A secret key must never reach a browser.')
    print('  0 passed, 0 failed  (nothing was checked)')
    sys.exit(2)

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

def redact(v):
    return (str(v)[:8] + 'XXXX') if v else '(none)'

JS = "async (a) => { const db = await import('./js/db.js'); return (%s)(db, a); }"
def run(page, fn, arg=None):
    return page.evaluate(JS % fn, arg)

print(f'  live project: {URL[:28]}…  key {redact(KEY)}  account {EMAIL}')

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(30000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.add_init_script('globalThis.ZAJIL_SYNC_CONFIG = ' +
                         json.dumps({'url': URL, 'publishableKey': KEY}) + ';')
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    st = run(page, "async (db, a) => await db.signIn(a.email, a.password)",
             {'email': EMAIL, 'password': PASSWORD})
    check('signs in against the real project', st['signedIn'] is True, str(st))
    check('the real user id comes back', bool(st['userId']), str(st))
    check('the email matches the account', st['email'] == EMAIL, str(st))

    first = run(page, """async (db) => ({
        access: ((await db.idbGet('settings','authAccessToken')) || {}).value ?? null,
        refresh: ((await db.idbGet('settings','authRefreshToken')) || {}).value ?? null,
    })""")
    check('a real access token was stored', bool(first['access']))
    check('a real refresh token was stored', bool(first['refresh']))

    r = run(page, "async (db) => await db.refreshSession()")
    second = run(page, """async (db) => ({
        access: ((await db.idbGet('settings','authAccessToken')) || {}).value ?? null,
        refresh: ((await db.idbGet('settings','authRefreshToken')) || {}).value ?? null,
        userId: db.authState().userId,
    })""")
    check('a real refresh succeeds', r['ok'] is True and r['reason'] == 'refreshed', str(r))
    check('Supabase rotates the refresh token, as the design assumes',
          second['refresh'] != first['refresh'],
          'the refresh token came back unchanged — §5 assumes rotation')
    check('the identity survives a real refresh', second['userId'] == st['userId'])

    bad = run(page, """async (db, a) => { try { await db.signIn(a.email, 'definitely-not-the-password');
        return { threw: false }; } catch (e) { return { threw: true, kind: e.kind, status: e.status }; } }""",
        {'email': EMAIL})
    check('a wrong password is rejected by the real server',
          bad['threw'] and bad['kind'] == 'rejected', str(bad))
    check('...with a 4xx, not a network error', bad['status'] is not None and 400 <= bad['status'] < 500, str(bad))

    # a genuinely bad refresh token must be a REJECTION, not a network error —
    # this is the case that decides whether a real user gets signed out
    dead = run(page, """async (db) => {
        await db.idbPut('settings', { key: 'authRefreshToken', value: 'not-a-real-refresh-token' });
        db.state.settings.authRefreshToken = 'not-a-real-refresh-token';
        return await db.refreshSession();
    }""")
    check('a spent refresh token is a rejection against the real server',
          dead['ok'] is False and dead['reason'] == 'rejected', str(dead))

    check('sign out clears the real session',
          run(page, "async (db) => { await db.signOut(); return db.authState().signedIn; }") is False)
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
