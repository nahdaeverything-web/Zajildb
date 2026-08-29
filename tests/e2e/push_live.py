# tests/e2e/push_live.py — push against the REAL project. Opt-in (--live-push).
#
# The stub in push.py models what the server does. This one checks that the
# model is right — in particular two things no stub can prove:
#
#   1. PostgREST accepts an upsert whose payload OMITS `owner`, even though
#      `owner` is part of the primary key. The design depends on this: the
#      client never sends an owner, the server defaults it to auth.uid(), and
#      that is what makes writing into someone else's rows impossible rather
#      than merely forbidden.
#   2. `return=representation` really does echo the rows back, so the
#      affected-row ack has something to count.
#
# NO CREDENTIAL IS COMMITTED — see the header of auth_live.py. Same variables.
#
# Rows written here STAY in the project: clients hold no DELETE grant, which is
# deliberate (a tombstone cannot be lost by any client bug). Test rows are
# therefore given a recognisable id prefix rather than cleaned up.
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

    run(page, """async (db) => {
        await db.idbClear('oplog');
        await db.setSetting('lastAckedSeq', 0);
        await db.setSetting('opSeq', 0);
        await db.setSetting('syncAnomalies', []);
    }""")

    pushed = run(page, """async (db) => {
        const bird = await db.saveBird(db.newBird({ name: 'live-push-test', sex: 'cock' }));
        const push = await db.pushOnce();
        return { push, id: bird.id, ops: (await db.listOps()).length };
    }""")
    check('a real push is acked', pushed['push']['ok'] is True and pushed['push']['reason'] == 'acked',
          str(pushed['push']))
    check('...meaning the server echoed a row for every record sent',
          pushed['push']['rows'] == pushed['push']['pushed'], str(pushed['push']))

    # read the row back and inspect what the server actually stored
    row = run(page, """async (db, a) => {
        const { url } = db.syncConfig();
        const res = await fetch(`${url}/rest/v1/sync_records?record_id=eq.${a.id}&select=*`,
                                { headers: db.authHeaders() });
        const rows = await res.json();
        return { status: res.status, row: rows[0] || null, count: rows.length };
    }""", {'id': pushed['id']})
    r = row['row'] or Res()
    check('the row is readable back through RLS', row['status'] == 200 and row['count'] == 1, str(row))
    check('OWNER WAS DEFAULTED SERVER-SIDE to the signed-in user — the client never sent it',
          r['owner'] == st['userId'], f"owner={r['owner']} user={st['userId']}")
    check('server_seq was assigned by the trigger', isinstance(r['server_seq'], int) and r['server_seq'] > 0,
          str(r['server_seq']))
    check('store and record_id round-tripped', r['store'] == 'birds' and r['record_id'] == pushed['id'],
          str({'store': r['store'], 'record_id': r['record_id']}))
    check('the record body arrived intact', (r['data'] or {}).get('name') == 'live-push-test',
          str((r['data'] or {}).get('name')))
    check('deleted is false for a put', r['deleted'] is False, str(r['deleted']))
    check('op_seq and device_id were carried', r['op_seq'] is not None and r['device_id'] is not None,
          str({'op_seq': r['op_seq'], 'device_id': r['device_id']}))

    first_seq = r['server_seq']
    updated = run(page, """async (db, a) => {
        await db.saveBird({ ...db.getBird(a.id), name: 'live-push-test-EDITED' });
        const push = await db.pushOnce();
        const { url } = db.syncConfig();
        const res = await fetch(`${url}/rest/v1/sync_records?record_id=eq.${a.id}&select=*`,
                                { headers: db.authHeaders() });
        const rows = await res.json();
        return { push, row: rows[0] || null, count: rows.length };
    }""", {'id': pushed['id']})
    u = updated['row'] or Res()
    check('a second push of the same record is an UPSERT, not a duplicate',
          updated['count'] == 1, f"{updated['count']} rows for one record")
    check('...the body was replaced', (u['data'] or {}).get('name') == 'live-push-test-EDITED',
          str((u['data'] or {}).get('name')))
    check('...and the trigger reassigned server_seq on UPDATE too',
          u['server_seq'] is not None and first_seq is not None and u['server_seq'] > first_seq,
          f"{first_seq} -> {u['server_seq']}")

    deleted = run(page, """async (db, a) => {
        await db.deleteBird(a.id);
        const push = await db.pushOnce();
        const { url } = db.syncConfig();
        const res = await fetch(`${url}/rest/v1/sync_records?record_id=eq.${a.id}&select=*`,
                                { headers: db.authHeaders() });
        const rows = await res.json();
        return { push, row: rows[0] || null };
    }""", {'id': pushed['id']})
    d = deleted['row'] or Res()
    check('a delete pushes as deleted = true', d['deleted'] is True, str(d['deleted']))
    check('...keeping the last-known body rather than nulling it',
          d['data'] is not None and (d['data'] or {}) != {}, str(d['data'])[:80])

    # the client must not be able to hard-delete: no DELETE grant (§2 Deletes)
    hard = run(page, """async (db, a) => {
        const { url } = db.syncConfig();
        const res = await fetch(`${url}/rest/v1/sync_records?record_id=eq.${a.id}`,
                                { method: 'DELETE', headers: db.authHeaders() });
        const body = await res.text();
        const after = await (await fetch(`${url}/rest/v1/sync_records?record_id=eq.${a.id}&select=record_id`,
                                { headers: db.authHeaders() })).json();
        return { status: res.status, body: body.slice(0, 160), stillThere: after.length };
    }""", {'id': pushed['id']})
    check('a client cannot hard-delete a row — the tombstone cannot be lost',
          hard['stillThere'] == 1, f"status={hard['status']} left={hard['stillThere']} {hard['body']}")

    # a batch larger than one, to exercise the affected-row count for real
    batch = run(page, """async (db) => {
        for (let i = 0; i < 12; i++)
            await db.Races.save({ birdId: 'live-b-' + i, date: '2026-05-01', distance: 120, name: 'live-r' + i });
        const push = await db.pushOnce();
        return { push, idle: (await db.pushOnce()).reason };
    }""")
    check('a multi-record batch acks with a full affected-row count',
          batch['push']['ok'] is True and batch['push']['rows'] == 12, str(batch['push']))
    check('...and the queue then drains to idle', batch['idle'] == 'idle', str(batch['idle']))
    check('no anomalies were recorded against the real server',
          run(page, "(db) => db.listSyncAnomalies().length") == 0)

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
sys.exit(1 if fail else 0)
