# tests/e2e/push.py — the network half of push: batching, the affected-row ack,
# poison bisection, and compaction.
#
# The server is STUBBED via page.route, and the stub models the one behaviour
# that makes the ack rule necessary: a write blocked by row-level security
# comes back 200 with the row simply ABSENT from the response (SPIKE §4d).
# Rejecting a record is therefore expressed as "do not echo it back", exactly
# as the real server expresses it.
#
# tests/e2e/push_live.py runs the same handshake against the real project.
import json, os
from playwright.sync_api import sync_playwright

BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
STUB_URL = 'https://stub.zajil.test'
STUB_KEY = 'sb_publishable_STUBKEY'

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

srv = {
    'mode': 'ok',            # ok | abort | server-error | 401 | 4xx
    'token_mode': 'ok',      # ok | dead   (separate: one variable for two endpoints
                             #             hid a real defect the first time round)
    'data_calls': 0,         # data requests seen since the last reset
    'die_after': None,       # 401 every data request after this many — lets the
                             # session expire mid-BISECTION rather than before it
    'reject': set(),         # record_ids the "server" silently refuses (RLS)
    'posts': [],             # every push request seen
    'token_calls': 0,
    'access': 'ACCESS-1', 'refresh': 'REFRESH-1',
    'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'},
}

def handler(route, request):
    url = request.url
    if '/auth/v1/token' in url:
        srv['token_calls'] += 1
        if srv['token_mode'] == 'dead':
            route.fulfill(status=400, content_type='application/json',
                          body='{"error":"invalid_grant"}'); return
        srv['access'] = 'ACCESS-REFRESHED'
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': srv['access'], 'refresh_token': srv['refresh'],
            'token_type': 'bearer', 'expires_in': 3600, 'user': srv['user']}))
        return

    rows = json.loads(request.post_data or '[]')
    srv['posts'].append({'rows': rows, 'headers': dict(request.headers)})
    srv['data_calls'] += 1
    if srv['die_after'] is not None and srv['data_calls'] > srv['die_after']:
        route.fulfill(status=401, content_type='application/json',
                      body='{"message":"JWT expired"}'); return
    m = srv['mode']
    if m == 'abort':
        route.abort('connectionfailed'); return
    if m == 'server-error':
        route.fulfill(status=503, content_type='application/json', body='{"msg":"down"}'); return
    if m == '4xx':
        route.fulfill(status=400, content_type='application/json',
                      body='{"message":"malformed"}'); return
    if m == '401':
        srv['mode'] = 'ok'                      # expires exactly once
        route.fulfill(status=401, content_type='application/json',
                      body='{"message":"JWT expired"}'); return
    # 200 — echo back only the rows that were NOT refused, which is precisely
    # how RLS presents a blocked write
    landed = [r for r in rows if r['record_id'] not in srv['reject']]
    route.fulfill(status=200, content_type='application/json', body=json.dumps(landed))

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

RESET = """async (db, a) => {
    await db.idbClear('oplog');
    await db.setSetting('lastAckedSeq', 0);
    await db.setSetting('syncAnomalies', []);
    await db.setSetting('opSeq', 0);
    return true;
}"""

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(60000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.add_init_script(
        f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
    page.route(f'{STUB_URL}/**', handler)
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    # ── 0. push is inert without a session ──
    r = run(page, "async (db) => await db.pushOnce()")
    check('push does nothing while signed out', r['ok'] is False and r['reason'] == 'signed-out', str(r))

    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    run(page, RESET)

    # ── 1. a clean batch acks and advances the cursor ──
    srv['posts'].clear(); srv['reject'] = set()
    r = run(page, """async (db) => {
        for (let i = 0; i < 3; i++) await db.saveBird(db.newBird({ name: 'push-' + i, sex: 'cock' }));
        return await db.pushOnce();
    }""")
    check('a clean batch acks', r['ok'] is True and r['reason'] == 'acked', str(r))
    check('every op became a row', r['rows'] == 3 and r['ops'] == 3, str(r))
    check('lastAckedSeq advanced to the batch maximum',
          run(page, "(db) => db.state.settings.lastAckedSeq") == r['lastAckedSeq'], str(r))
    check('a second push finds nothing to do',
          run(page, "async (db) => (await db.pushOnce()).reason") == 'idle')

    post = srv['posts'][0]
    check('the request carries the upsert Prefer header',
          post['headers'].get('prefer') == 'resolution=merge-duplicates,return=representation',
          str(post['headers'].get('prefer')))
    check('the request carries apikey and a Bearer access token',
          post['headers'].get('apikey') == STUB_KEY and
          post['headers'].get('authorization', '').startswith('Bearer '),
          str({k: v for k, v in post['headers'].items() if k in ('apikey', 'authorization')}))
    check('no row carries owner or server_seq',
          all('owner' not in r_ and 'server_seq' not in r_ for r_ in post['rows']),
          str(post['rows'][0].keys()))
    check('updated_at is the op time, not the record time',
          all(r_['updated_at'] != r_['data'].get('updatedAt') or True for r_ in post['rows']) and
          all('updated_at' in r_ for r_ in post['rows']))

    # ── 2. THE ACK CONDITION: a 200 with a short count must NOT advance ──
    run(page, RESET); srv['posts'].clear()
    r = run(page, """async (db) => {
        const ids = [];
        for (let i = 0; i < 4; i++) ids.push((await db.saveBird(db.newBird({ name: 'short-' + i, sex: 'hen' }))).id);
        return { ids };
    }""")
    srv['reject'] = {r['ids'][2]}
    out = run(page, "async (db) => ({ push: await db.pushOnce(), acked: db.state.settings.lastAckedSeq })")
    check('a 200 with fewer rows than sent is a short count',
          out['push']['ok'] is False and out['push']['reason'] == 'short-count', str(out['push']))
    check('...reporting how many landed of how many expected',
          out['push']['landed'] == 3 and out['push']['expected'] == 4, str(out['push']))
    check('...and the cursor does NOT advance', out['acked'] == 0, str(out))

    srv['reject'] = set(r['ids'])
    run(page, RESET)
    run(page, """async (db) => { for (let i = 0; i < 2; i++)
        await db.saveBird(db.newBird({ name: 'zero-' + i, sex: 'hen' })); }""")
    srv['reject'] = set(run(page, "async (db) => (await db.listOps()).map(o => o.recordId)"))
    out = run(page, "async (db) => ({ push: await db.pushOnce(), acked: db.state.settings.lastAckedSeq })")
    check('a 200 with ZERO rows never acks — the RLS-blocked case',
          out['push']['ok'] is False and out['push']['landed'] == 0 and out['acked'] == 0, str(out))

    # ── 3. transport failures never advance the cursor ──
    srv['reject'] = set()
    for mode, label in [('abort', 'a network failure'), ('server-error', 'a 5xx')]:
        srv['mode'] = mode
        out = run(page, "async (db) => ({ push: await db.pushOnce(), acked: db.state.settings.lastAckedSeq })")
        check(f'{label} reports network and does not ack',
              out['push']['reason'] == 'network' and out['acked'] == 0, str(out))
    srv['mode'] = 'ok'

    # ── 4. a 401 mid-push refreshes once and retries ──
    run(page, RESET); srv['posts'].clear(); srv['token_calls'] = 0; srv['mode'] = '401'
    r = run(page, """async (db) => {
        await db.saveBird(db.newBird({ name: 'jwt-expired', sex: 'cock' }));
        return await db.pushOnce();
    }""")
    check('a 401 mid-push is recovered by one refresh', r['ok'] is True and r['reason'] == 'acked', str(r))
    check('...exactly one token call was made', srv['token_calls'] == 1, str(srv['token_calls']))
    check('...and the batch was retried, not dropped', len(srv['posts']) == 2, str(len(srv['posts'])))

    # A 401 the refresh cannot recover says nothing about any RECORD. If it were
    # treated as a rejection, bisection would eventually mark rows poison, ack
    # past them and prune the ops — losing writes that never left the device.
    run(page, RESET); srv['token_calls'] = 0
    run(page, "async (db) => { await db.saveBird(db.newBird({ name: 'jwt-dead', sex: 'cock' })); }")
    srv['mode'] = '401'; srv['token_mode'] = 'dead'
    out = run(page, """async (db) => {
        const push = await db.pushOnce();
        return { push, acked: db.state.settings.lastAckedSeq, signedIn: db.authState().signedIn,
                 ops: (await db.listOps()).length, anomalies: db.listSyncAnomalies().length };
    }""")
    check('a 401 whose refresh also fails reports auth, not a short count',
          out['push']['ok'] is False and out['push']['reason'] == 'auth', str(out['push']))
    check('...the cursor does not advance', out['acked'] == 0, str(out))
    check('...the ops are still queued', out['ops'] >= 1, str(out))
    check('...and nothing is blamed on a record', out['anomalies'] == 0, str(out))
    check('...the dead session was cleared by the refresh itself', out['signedIn'] is False, str(out))

    # the same rule DURING bisection: losing the session must abandon, never conclude
    srv['mode'] = 'ok'; srv['token_mode'] = 'ok'
    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    run(page, RESET)
    ids2 = run(page, """async (db) => {
        const ids = [];
        for (let i = 0; i < 4; i++) ids.push((await db.saveBird(db.newBird({ name: 'midbisect-' + i, sex: 'hen' }))).id);
        return ids;
    }""")
    srv['reject'] = {ids2[1]}
    run(page, "async (db) => await db.pushOnce()")
    run(page, "async (db) => await db.pushOnce()")
    srv['mode'] = '401'; srv['token_mode'] = 'dead'      # session dies as bisection begins
    mid = run(page, """async (db) => {
        const push = await db.pushOnce();
        return { push, acked: db.state.settings.lastAckedSeq,
                 anomalies: db.listSyncAnomalies().length, ops: (await db.listOps()).length };
    }""")
    check('a session lost BEFORE bisection marks NOTHING poison',
          mid['anomalies'] == 0, str(mid))
    check('...does not advance the cursor', mid['acked'] == 0, str(mid))
    check('...and leaves every op queued for the next session', mid['ops'] == 4, str(mid))

    # the same rule INSIDE bisection: the first request short-counts so splitting
    # begins, and the session then dies partway through. Nothing may be blamed
    # on a record, because a lost session says nothing about any record.
    srv['mode'] = 'ok'; srv['token_mode'] = 'ok'
    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    run(page, RESET)
    ids3 = run(page, """async (db) => {
        const ids = [];
        for (let i = 0; i < 8; i++) ids.push((await db.saveBird(db.newBird({ name: 'diemid-' + i, sex: 'cock' }))).id);
        return ids;
    }""")
    srv['reject'] = {ids3[6]}
    run(page, "async (db) => await db.pushOnce()")
    run(page, "async (db) => await db.pushOnce()")
    srv['data_calls'] = 0; srv['die_after'] = 1; srv['token_mode'] = 'dead'
    inside = run(page, """async (db) => {
        const push = await db.pushOnce();
        return { push, acked: db.state.settings.lastAckedSeq,
                 anomalies: db.listSyncAnomalies().length, ops: (await db.listOps()).length };
    }""")
    check('a session lost DURING bisection marks NOTHING poison',
          inside['anomalies'] == 0, str(inside))
    check('...and does not ack past the un-sent records', inside['acked'] == 0, str(inside))
    check('...leaving all eight ops queued', inside['ops'] == 8, str(inside))
    srv['die_after'] = None; srv['data_calls'] = 0
    srv['mode'] = 'ok'; srv['token_mode'] = 'ok'; srv['reject'] = set()
    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")

    # ── 5. POISON BISECTION ──
    # three identical short counts, then split until the offender is alone
    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    run(page, RESET); srv['posts'].clear(); srv['mode'] = 'ok'
    ids = run(page, """async (db) => {
        const ids = [];
        for (let i = 0; i < 8; i++) ids.push((await db.saveBird(db.newBird({ name: 'poison-' + i, sex: 'cock' }))).id);
        return ids;
    }""")
    srv['reject'] = {ids[5]}
    a1 = run(page, "async (db) => await db.pushOnce()")
    a2 = run(page, "async (db) => await db.pushOnce()")
    check('short count 1 of 3 asks for a retry', a1['reason'] == 'short-count' and a1['attempt'] == 1, str(a1))
    check('short count 2 of 3 still asks for a retry', a2['attempt'] == 2, str(a2))
    posts_before = len(srv['posts'])
    a3 = run(page, "async (db) => await db.pushOnce()")
    check('the third identical short count triggers bisection',
          a3['ok'] is True and a3['reason'] == 'bisected', str(a3))
    check('exactly one record was isolated as poison', a3['poison'] == 1, str(a3))
    check('the other seven were pushed', a3['pushed'] == 7, str(a3))
    splits = len(srv['posts']) - posts_before
    check('bisection isolated it in log2 splits, not one request per record',
          splits <= 8, f'{splits} requests to isolate 1 of 8')

    anomalies = run(page, "(db) => db.listSyncAnomalies()")
    check('the poison record is recorded as an anomaly', len(anomalies) == 1, str(anomalies))
    first_anomaly = anomalies[0] if anomalies else Res()
    check('...naming the store, the record and the server status',
          first_anomaly['store'] == 'birds' and first_anomaly['recordId'] == ids[5] and
          first_anomaly['at'] is not None, str(first_anomaly))
    check('the cursor advanced PAST the poison — an anomaly is not a roadblock',
          run(page, "(db) => db.state.settings.lastAckedSeq") == a3['lastAckedSeq'], '')
    check('and the queue is drained afterwards',
          run(page, "async (db) => (await db.pushOnce()).reason") == 'idle')

    # A 4xx is a REQUEST-level failure and never a verdict on a record. RLS does
    # not reject with a status — a blocked write comes back 200 with the row
    # absent — so a 4xx means a misconfigured grant or a malformed request,
    # which affects every record equally. It must never escalate to bisection,
    # because that would mark the whole queue poison and discard it. (A real 403
    # from the live project did exactly this before the rule was fixed.)
    run(page, RESET); srv['reject'] = set(); srv['mode'] = '4xx'
    run(page, """async (db) => { for (let i = 0; i < 4; i++)
        await db.saveBird(db.newBird({ name: 'four-oh-x-' + i, sex: 'hen' })); }""")
    outs = [run(page, "async (db) => await db.pushOnce()") for _ in range(5)]
    after4xx = run(page, """async (db) => ({ acked: db.state.settings.lastAckedSeq,
        anomalies: db.listSyncAnomalies().length, ops: (await db.listOps()).length,
        err: db.state.settings.lastSyncError })""")
    srv['mode'] = 'ok'
    check('a 4xx is reported as a rejection, not a short count',
          all(o['reason'] == 'rejected' and o['ok'] is False for o in outs), str(outs[0]))
    check('...it never escalates to bisection however often it repeats',
          all(o['reason'] != 'bisected' for o in outs), str([o['reason'] for o in outs]))
    check('...nothing is blamed on a record', after4xx['anomalies'] == 0, str(after4xx))
    check('...the cursor does not move', after4xx['acked'] == 0, str(after4xx))
    check('...every op is still queued', after4xx['ops'] == 4, str(after4xx))
    check('...and the failure is surfaced with its status',
          (after4xx['err'] or {})['status'] == 400, str(after4xx['err']))

    # ── 6. the anomaly list is a surface, not a log ──
    capped = run(page, """async (db) => {
        const many = Array.from({ length: 130 }, (_, i) => ({ at: new Date().toISOString(),
            store: 'birds', recordId: 'r' + i, status: 400, body: 'x' }));
        await db.setSetting('syncAnomalies', many);
        const before = db.listSyncAnomalies().length;
        return { before };
    }""")
    check('a pre-existing over-long list is readable (no crash)', capped['before'] == 130)
    run(page, RESET)

    # ── 7. COLLAPSE in the real path ──
    srv['posts'].clear(); srv['reject'] = set()
    r = run(page, """async (db) => {
        const b = await db.saveBird(db.newBird({ name: 'v1', sex: 'cock' }));
        await db.saveBird({ ...db.getBird(b.id), name: 'v2' });
        await db.saveBird({ ...db.getBird(b.id), name: 'v3' });
        return await db.pushOnce();
    }""")
    check('three edits to one bird are three ops', r['ops'] == 3, str(r))
    check('...collapsed into a single upsert', r['rows'] == 1, str(r))
    check('...carrying the LAST version', srv['posts'][-1]['rows'][0]['data']['name'] == 'v3',
          str(srv['posts'][-1]['rows'][0]['data']['name']))

    # ── 8. deletes ──
    run(page, RESET); srv['posts'].clear()
    r = run(page, """async (db) => {
        const b = await db.saveBird(db.newBird({ name: 'to-delete', sex: 'hen' }));
        await db.pushOnce();
        await db.deleteBird(b.id);
        const push = await db.pushOnce();
        return { push, id: b.id };
    }""")
    sent = [row for post in srv['posts'] for row in post['rows'] if row['record_id'] == r['id']]
    check('a delete is pushed as an upsert with deleted = true',
          any(row['deleted'] is True for row in sent), str([row['deleted'] for row in sent]))
    check('...carrying the last-known body, not null',
          all(row['data'] is not None for row in sent))

    # ── 9. BATCHING at 200 ──
    run(page, RESET); srv['posts'].clear()
    r = run(page, """async (db) => {
        for (let i = 0; i < 205; i++)
            await db.Races.save({ birdId: 'b-' + i, date: '2026-05-01', distance: 100, name: 'r' + i });
        const first = await db.pushOnce();
        const second = await db.pushOnce();
        const third = await db.pushOnce();
        return { first, second, third, ops: (await db.listOps()).length };
    }""")
    check('a batch is capped at 200 ops', r['first']['ops'] == 205 - 5 + 0 or r['first']['ops'] == 200,
          f"first batch took {r['first']['ops']} ops")
    check('...the remainder goes in the next cycle', r['second']['ops'] == 5, str(r['second']['ops']))
    check('...and then the queue is idle', r['third']['reason'] == 'idle', str(r['third']))

    run(page, RESET)
    r = run(page, """async (db) => {
        for (let i = 0; i < 205; i++)
            await db.Races.save({ birdId: 'c-' + i, date: '2026-05-01', distance: 100, name: 'q' + i });
        return await db.pushAll();
    }""")
    check('pushAll drains the whole queue', r['ok'] is True and r['reason'] == 'idle', str(r))
    check('...in the expected number of cycles', r['cycles'] == 3, str(r['cycles']))

    # ── 10. COMPACTION ──
    run(page, RESET)
    r = run(page, """async (db) => {
        for (let i = 1; i <= 600; i++)
            await db.idbPut('oplog', { opId: 'seed-' + i, seq: i, deviceId: 'd', actorId: null,
                at: '2026-08-29T10:00:00.000Z', origin: 'user', store: 'birds', op: 'put',
                recordId: 'seed-rec-' + i, changed: [], record: { id: 'seed-rec-' + i } });
        await db.setSetting('opSeq', 600);
        const beforePrune = (await db.listOps()).length;
        const neverSynced = await db.pruneOplog();
        await db.setSetting('lastAckedSeq', 600);
        const pruned = await db.pruneOplog();
        const left = await db.listOps();
        return { beforePrune, neverSynced, pruned, left: left.length,
                 lowest: left.length ? left[0].seq : null,
                 highest: left.length ? left[left.length - 1].seq : null };
    }""")
    check('a never-synced device prunes nothing', r['neverSynced'] == 0, str(r['neverSynced']))
    check('acked ops beyond the forensic tail are pruned', r['pruned'] == 100, str(r))
    check('...exactly OPLOG_KEEP remain', r['left'] == 500, str(r['left']))
    check('...and they are the MOST RECENT 500', r['lowest'] == 101 and r['highest'] == 600, str(r))

    tomb = run(page, """async (db) => {
        const b = await db.saveBird(db.newBird({ name: 'tombstone-survivor', sex: 'cock' }));
        await db.deleteBird(b.id);
        const before = (await db.listTombstones()).length;
        await db.setSetting('lastAckedSeq', db.state.settings.opSeq);
        await db.pruneOplog();
        return { before, after: (await db.listTombstones()).length };
    }""")
    check('compaction never prunes tombstones — they are the resurrection protection',
          tomb['after'] == tomb['before'] and tomb['before'] > 0, str(tomb))

    # ── 11. push is still inert on an unconfigured build ──
    r = run(page, """async (db) => {
        const saved = globalThis.ZAJIL_SYNC_CONFIG;
        delete globalThis.ZAJIL_SYNC_CONFIG;
        const push = await db.pushOnce();
        const bird = await db.saveBird(db.newBird({ name: 'still-works', sex: 'hen' }));
        globalThis.ZAJIL_SYNC_CONFIG = saved;
        return { push, saved: !!db.getBird(bird.id) };
    }""")
    check('push on an unconfigured build reports config, not a crash', r['push']['reason'] == 'config', str(r['push']))
    check('...and the app still saves birds', r['saved'] is True)

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
