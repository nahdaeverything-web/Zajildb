# tests/e2e/pull_live.py — pull against the REAL project. Opt-in (--live-pull).
#
# The stub in pull.py models PostgREST's filtering. This checks the model: that
# `server_seq=gt.<cursor>&order=server_seq.asc&limit=<n>` means to the real
# server what the pull loop assumes it means, and that rows written by an
# earlier push come back intact.
#
# Reads only. NO CREDENTIAL IS COMMITTED — see the header of auth_live.py.
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

class Res(dict):
    def __missing__(self, key): return None
def _wrap(v):
    if isinstance(v, dict): return Res({k: _wrap(x) for k, x in v.items()})
    if isinstance(v, list): return [_wrap(x) for x in v]
    return v

JS = "async (a) => { const db = await import('./js/db.js'); return (%s)(db, a); }"
def run(page, fn, arg=None):
    return _wrap(page.evaluate(JS % fn, arg))

print(f'  live project: {URL[:28]}…  account {EMAIL}')

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(45000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.add_init_script('globalThis.ZAJIL_SYNC_CONFIG = ' +
                         json.dumps({'url': URL, 'publishableKey': KEY}) + ';')
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    st = run(page, "async (db, a) => await db.signIn(a.email, a.password)",
             {'email': EMAIL, 'password': PASSWORD})
    check('signed in against the real project', st['signedIn'] is True, str(st))

    # start from an empty local mirror and cursor 0, so everything below comes
    # from the server rather than from anything already on this device
    run(page, """async (db) => {
        for (const s of ['birds', 'pairs', 'raceResults', 'healthEvents', 'media', 'oplog', 'tombstones'])
            await db.idbClear(s);
        db.state.birds.clear(); db.state.pairs.clear();
        db.state.raceResults.clear(); db.state.healthEvents.clear();
        await db.setSetting('syncCursor', 0);
        await db.setSetting('lastAckedSeq', 0);
        await db.setSetting('opSeq', 0);
        await db.setSetting('syncAnomalies', []);
    }""")

    # the raw query, exactly as the pull loop builds it
    raw = run(page, """async (db) => {
        const { url } = db.syncConfig();
        const q = 'select=*&server_seq=gt.0&order=server_seq.asc&limit=500';
        const res = await fetch(`${url}/rest/v1/sync_records?${q}`, { headers: db.authHeaders() });
        const rows = await res.json();
        const seqs = Array.isArray(rows) ? rows.map(r => r.server_seq) : [];
        return { status: res.status, count: seqs.length, seqs: seqs.slice(0, 5),
                 ascending: seqs.every((v, i) => i === 0 || v > seqs[i - 1]) };
    }""")
    check('the cursor query is accepted by the real server', raw['status'] == 200, str(raw['status']))
    check('...and returns the rows an earlier push wrote', raw['count'] > 0,
          'no rows — has --live-push ever run against this project?')
    check('...in strictly ascending server_seq order', raw['ascending'] is True, str(raw['seqs']))

    pulled = run(page, """async (db) => {
        const opsBefore = (await db.listOps()).length;
        const pull = await db.pullAll();
        const opsAfter = (await db.listOps()).length;
        return { pull, opsBefore, opsAfter, cursor: db.state.settings.syncCursor,
                 birds: db.allBirds().length,
                 races: (await db.idbGetAll('raceResults')).length };
    }""")
    check('a real pull applies rows', pulled['pull']['ok'] is True and pulled['pull']['applied'] > 0,
          str(pulled['pull']))
    check('ECHO PREVENTION HOLDS AGAINST THE REAL SERVER — zero ops logged',
          pulled['opsAfter'] == pulled['opsBefore'] == 0,
          f"{pulled['opsBefore']} -> {pulled['opsAfter']}")
    check('the cursor advanced past every row seen', (pulled['cursor'] or 0) > 0, str(pulled['cursor']))
    check('records landed in the local stores',
          (pulled['birds'] or 0) + (pulled['races'] or 0) > 0, str(pulled))

    idle = run(page, "async (db) => await db.pullOnce()")
    check('a second pull from the advanced cursor is idle', idle['reason'] == 'idle', str(idle))

    # a row this device did NOT author keeps the authoring device's identity
    verbatim = run(page, """async (db) => {
        const mine = db.state.settings.deviceId;
        const foreign = db.allBirds().filter(b => b.deviceId && b.deviceId !== mine);
        const rows = await (await fetch(
            `${db.syncConfig().url}/rest/v1/sync_records?select=*&store=eq.birds&limit=500`,
            { headers: db.authHeaders() })).json();
        const byId = new Map((rows || []).map(r => [r.record_id, r]));
        const mismatched = db.allBirds().filter(b => {
            const r = byId.get(b.id);
            return r && !r.deleted && r.data && r.data.updatedAt !== b.updatedAt;
        });
        return { total: db.allBirds().length, foreign: foreign.length,
                 mismatched: mismatched.length };
    }""")
    check('every applied record kept the server row\'s updatedAt byte for byte',
          verbatim['mismatched'] == 0, f"{verbatim['mismatched']} of {verbatim['total']} differ")

    check('no anomalies against the real server', run(page, "(db) => db.listSyncAnomalies().length") == 0,
          str(run(page, "(db) => db.listSyncAnomalies().slice(0,2)")))
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
