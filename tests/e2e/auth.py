# tests/e2e/auth.py — the auth flows that need a real browser: IndexedDB-backed
# token storage, the network-vs-rejection split, refresh-token rotation, and
# the multi-instance refresh race.
#
# The Supabase endpoint is STUBBED via page.route, so this suite is fast,
# deterministic, and runs with no network. tests/e2e/auth_live.py does the same
# handshake against the real dev project and is opt-in.
import json, os
from playwright.sync_api import sync_playwright

BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
STUB_URL = 'https://stub.zajil.test'
STUB_KEY = 'sb_publishable_STUBKEY'
ACCESS, REFRESH = 'ACCESS-TOKEN-1', 'REFRESH-TOKEN-1'

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

# what the stub does next, and what it saw
srv = {'mode': 'ok', 'access': ACCESS, 'refresh': REFRESH,
       'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'}, 'seen': []}

def handler(route, request):
    srv['seen'].append({'url': request.url, 'headers': dict(request.headers),
                        'body': request.post_data})
    m = srv['mode']
    if m == 'abort':
        route.abort('connectionfailed'); return
    if m == 'server-error':
        route.fulfill(status=503, content_type='application/json', body='{"msg":"upstream unavailable"}'); return
    if m == 'reject':
        route.fulfill(status=400, content_type='application/json',
                      body='{"error":"invalid_grant","error_description":"Invalid login credentials"}'); return
    if m == 'ok-no-tokens':
        route.fulfill(status=200, content_type='application/json', body='{"weird":true}'); return
    body = {'access_token': srv['access'], 'refresh_token': srv['refresh'],
            'token_type': 'bearer', 'expires_in': 3600}
    if m != 'ok-no-user':
        body['user'] = srv['user']
    route.fulfill(status=200, content_type='application/json', body=json.dumps(body))

class Res(dict):
    """A page result whose missing keys read as None instead of raising.

    pushOnce/refreshSession deliberately return DIFFERENT SHAPES per outcome,
    so a test that indexes a key the failing path did not set would die with a
    KeyError — aborting the whole suite on the first failure and hiding every
    assertion after it. A regression has to be REPORTED, not turned into a
    traceback. (Found by mutation testing: breaking the ack rule made five
    other proofs silently unreachable.)"""
    def __missing__(self, key):
        return None

def _wrap(v):
    if isinstance(v, dict): return Res({k: _wrap(x) for k, x in v.items()})
    if isinstance(v, list): return [_wrap(x) for x in v]
    return v

JS = "async (a) => { const db = await import('./js/db.js'); return (%s)(db, a); }"
def run(page, fn, arg=None):
    return _wrap(page.evaluate(JS % fn, arg))

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(25000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
    page.route(f'{STUB_URL}/**', handler)
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    # ── 1. a fresh device has no session ──
    check('a fresh device is signed out', run(page, "(db) => db.authState().signedIn") is False)
    check('ensureAccessToken is null when signed out',
          run(page, "async (db) => await db.ensureAccessToken()") is None)

    # ── 2. sign-in stores the session ──
    srv['mode'] = 'ok'; srv['seen'].clear()
    st = run(page, "async (db) => await db.signIn('spike-a@zajil.test', 'pw')")
    check('signIn returns a signed-in state', st['signedIn'] is True and st['email'] == 'spike-a@zajil.test', str(st))
    check('signIn records the user id (this becomes actorId)', st['userId'] == 'user-uuid-1', str(st))

    seen = srv['seen'][-1]
    check('the token request carries the publishable key in apikey',
          seen['headers'].get('apikey') == STUB_KEY, str(seen['headers'].get('apikey')))
    check('the token request sends NO Authorization header',
          'authorization' not in {k.lower() for k in seen['headers']},
          str(list(seen['headers'])))
    check('the request went to grant_type=password', 'grant_type=password' in seen['url'], seen['url'])

    # ── 3. the session is in IndexedDB, not just memory ──
    page.reload(wait_until='load'); page.wait_for_timeout(1500)
    check('the session survives a reload (stored in settings)',
          run(page, "(db) => db.authState().signedIn") is True)
    check('both tokens are in the settings store',
          run(page, "async (db) => ((await db.idbGet('settings','authAccessToken')) || {}).value ?? null") == ACCESS)

    # ── 4. actorId is wired to the signed-in user ──
    a = run(page, """async (db) => {
        const before = (await db.listOps()).length;
        await db.saveBird(db.newBird({ name: 'auth-actor', sex: 'cock' }));
        const ops = await db.listOps();
        return { actorId: ops[ops.length - 1].actorId, grew: ops.length === before + 1 };
    }""")
    check('an op written while signed in carries the user id as actorId',
          a['actorId'] == 'user-uuid-1' and a['grew'], str(a))

    # ── 5. NETWORK failure must never cost the session ──
    srv['mode'] = 'abort'
    r = run(page, "async (db) => await db.refreshSession()")
    check('a refresh that cannot reach the network reports "network"', r['reason'] == 'network' and r['ok'] is False, str(r))
    check('...and the session is KEPT', run(page, "(db) => db.authState().signedIn") is True)

    srv['mode'] = 'server-error'
    r = run(page, "async (db) => await db.refreshSession()")
    check('a 5xx is a network failure, not an auth verdict', r['reason'] == 'network' and r['status'] == 503, str(r))
    check('...and the session is KEPT', run(page, "(db) => db.authState().signedIn") is True)

    # ── 6. a successful refresh ROTATES the refresh token ──
    srv['mode'] = 'ok'; srv['access'] = 'ACCESS-TOKEN-2'; srv['refresh'] = 'REFRESH-TOKEN-2'
    r = run(page, "async (db) => await db.refreshSession()")
    rot = run(page, """async (db) => ({
        access: ((await db.idbGet('settings','authAccessToken')) || {}).value ?? null,
        refresh: ((await db.idbGet('settings','authRefreshToken')) || {}).value ?? null,
        email: db.authState().email,
    })""")
    check('a refresh reports success', r['ok'] is True and r['reason'] == 'refreshed', str(r))
    check('the refresh token is REPLACED — the old one is spent',
          rot['refresh'] == 'REFRESH-TOKEN-2', str(rot))
    check('the access token is replaced too', rot['access'] == 'ACCESS-TOKEN-2', str(rot))

    # a refresh response without a user object must not erase the identity
    srv['mode'] = 'ok-no-user'; srv['refresh'] = 'REFRESH-TOKEN-3'
    run(page, "async (db) => await db.refreshSession()")
    check('a refresh with no user object keeps the identity',
          run(page, "(db) => db.authState().userId") == 'user-uuid-1')

    # ── 7. THE RE-READ RULE: another instance won the race ──
    # Simulate the installed app refreshing first: write a DIFFERENT token
    # straight into the shared store WITHOUT touching this instance's mirror,
    # which is exactly the state the losing instance is in.
    srv['mode'] = 'reject'
    r = run(page, """async (db) => {
        await db.idbPut('settings', { key: 'authRefreshToken', value: 'REFRESH-FROM-OTHER-INSTANCE' });
        await db.idbPut('settings', { key: 'authAccessToken', value: 'ACCESS-FROM-OTHER-INSTANCE' });
        return await db.refreshSession();   // still sends OUR stale token; server rejects it
    }""")
    check('a rejected refresh re-reads before declaring the session dead',
          r['ok'] is True and r['reason'] == 'adopted', str(r))
    after = run(page, "(db) => ({ signedIn: db.authState().signedIn, headers: db.authHeaders() })")
    check('...the session survives the lost race', after['signedIn'] is True, str(after))
    check('...and the winner\'s tokens are adopted',
          after['headers']['Authorization'] == 'Bearer ACCESS-FROM-OTHER-INSTANCE', str(after['headers']))

    # ── 8. a genuine rejection DOES end the session ──
    srv['mode'] = 'reject'
    r = run(page, "async (db) => await db.refreshSession()")   # stored == sent this time
    check('a rejection with nothing newer stored clears the session',
          r['ok'] is False and r['reason'] == 'rejected' and r['status'] == 400, str(r))
    cleared = run(page, """async (db) => {
        const out = {};
        for (const k of db.AUTH_SETTING_KEYS) out[k] = ((await db.idbGet('settings', k)) || {}).value ?? null;
        return { out, signedIn: db.authState().signedIn };
    }""")
    check('...every session key is cleared from storage',
          all(v is None for v in cleared['out'].values()) and cleared['signedIn'] is False, str(cleared))

    # ── 9. sign-in failures ──
    srv['mode'] = 'reject'
    r = run(page, """async (db) => { try { await db.signIn('a@b.test','wrong'); return {threw:false}; }
        catch (e) { return { threw:true, name:e.name, kind:e.kind, status:e.status }; } }""")
    check('a wrong password is a rejection', r['threw'] and r['kind'] == 'rejected' and r['status'] == 400, str(r))
    check('...and stores nothing', run(page, "(db) => db.authState().signedIn") is False)

    srv['mode'] = 'abort'
    r = run(page, """async (db) => { try { await db.signIn('a@b.test','pw'); return {threw:false}; }
        catch (e) { return { threw:true, kind:e.kind }; } }""")
    check('signing in with no network is a network error, not a bad password',
          r['threw'] and r['kind'] == 'network', str(r))

    srv['mode'] = 'ok-no-tokens'
    r = run(page, """async (db) => { try { await db.signIn('a@b.test','pw'); return {threw:false}; }
        catch (e) { return { threw:true, kind:e.kind }; } }""")
    check('a 200 carrying no tokens is not a session', r['threw'] and r['kind'] == 'rejected', str(r))

    # ── 10. sign out ──
    srv['mode'] = 'ok'; srv['access'] = ACCESS; srv['refresh'] = REFRESH
    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    out = run(page, """async (db) => {
        await db.signOut();
        const stored = {};
        for (const k of db.AUTH_SETTING_KEYS) stored[k] = ((await db.idbGet('settings', k)) || {}).value ?? null;
        return { signedIn: db.authState().signedIn, stored };
    }""")
    check('signOut clears every session key', out['signedIn'] is False and
          all(v is None for v in out['stored'].values()), str(out))

    ops = run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'auth-actor-out', sex: 'hen' }));
        const all = await db.listOps();
        return all[all.length - 1].actorId;
    }""")
    check('an op written after signing out carries actorId null', ops is None, str(ops))

    # ── 11. TOKENS MUST NEVER LEAVE THE DEVICE (SYNC-DESIGN §9) ──
    srv['mode'] = 'ok'
    leak = run(page, """async (db) => {
        await db.signIn('spike-a@zajil.test','pw');          // real tokens genuinely present
        const payload = await db.exportAll({ includeMedia: false });
        await db.autoBackup();
        const backups = await db.listBackups();
        const walk = (v, path, hits) => {
            if (v && typeof v === 'object') {
                for (const [k, val] of Object.entries(v)) {
                    if (k.startsWith('auth')) hits.push(path + '.' + k);
                    walk(val, path + '.' + k, hits);
                }
            }
            return hits;
        };
        const exportHits = walk(payload, '$', []);
        const backupHits = backups.flatMap((b) => walk(b, '$backup', []));
        const text = JSON.stringify(payload) + JSON.stringify(backups);
        return {
            exportHits, backupHits,
            accessInText: text.includes('ACCESS-TOKEN-1'),
            refreshInText: text.includes('REFRESH-TOKEN-1'),
            exportKeys: Object.keys(payload).sort(),
            signedIn: db.authState().signedIn,
        };
    }""")
    check('a live session is present for this check to mean anything', leak['signedIn'] is True)
    check('no export payload carries any auth* key', leak['exportHits'] == [], str(leak['exportHits']))
    check('no backups-store snapshot carries any auth* key', leak['backupHits'] == [], str(leak['backupHits']))
    check('neither token appears anywhere in an export or a backup',
          not leak['accessInText'] and not leak['refreshInText'], str(leak))
    check('the export payload keys are exactly the pinned set',
          leak['exportKeys'] == ['birds', 'exportedAt', 'format', 'healthEvents', 'lofts',
                                 'media', 'pairs', 'raceResults', 'tombstones', 'version'],
          str(leak['exportKeys']))

    # ── 12. auth is required to SYNC, not to FUNCTION ──
    unconf = run(page, """async (db) => {
        const saved = globalThis.ZAJIL_SYNC_CONFIG;
        delete globalThis.ZAJIL_SYNC_CONFIG;                  // a stock, unconfigured build
        const cfg = db.syncConfig();
        let kind = null;
        try { await db.signIn('a@b.test','pw'); } catch (e) { kind = e.kind; }
        const refresh = await db.refreshSession();
        const bird = await db.saveBird(db.newBird({ name: 'offline-bird', sex: 'cock' }));
        const readBack = db.getBird(bird.id);
        globalThis.ZAJIL_SYNC_CONFIG = saved;
        return { configured: cfg.configured, kind, refresh, saved: !!readBack,
                 name: readBack && readBack.name };
    }""")
    check('an unconfigured build reports itself unconfigured', unconf['configured'] is False)
    check('signIn on an unconfigured build is a config error, not a crash', unconf['kind'] == 'config', str(unconf))
    check('refreshSession on an unconfigured build keeps the session and does not throw',
          unconf['refresh']['ok'] is False and unconf['refresh']['reason'] == 'config', str(unconf['refresh']))
    check('the app still saves and reads birds with sync unconfigured',
          unconf['saved'] and unconf['name'] == 'offline-bird', str(unconf))

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
