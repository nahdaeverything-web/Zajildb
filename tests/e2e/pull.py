# tests/e2e/pull.py — the pull path: cursor on server_seq, verbatim apply,
# tombstone semantics, and the echo prevention the whole design rests on.
#
# The server is stubbed via page.route and serves rows from a Python-side list,
# honouring server_seq=gt.<cursor> and limit exactly as PostgREST would.
import json, os, re
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
    'rows': [],          # every row the "server" holds, server_seq ascending
    'mode': 'ok',        # ok | abort | server-error | 4xx | 401
    'token_mode': 'ok',
    'requests': [],      # ('GET'|'POST', url)
    'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'},
}

def handler(route, request):
    url = request.url
    if '/auth/v1/token' in url:
        if srv['token_mode'] == 'dead':
            route.fulfill(status=400, content_type='application/json',
                          body='{"error":"invalid_grant"}'); return
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-1', 'refresh_token': 'REFRESH-1',
            'token_type': 'bearer', 'expires_in': 3600, 'user': srv['user']}))
        return

    srv['requests'].append((request.method, url))
    if request.method == 'POST':                      # push — always succeeds here
        rows = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(rows)); return

    m = srv['mode']
    if m == 'abort':
        route.abort('connectionfailed'); return
    if m == 'server-error':
        route.fulfill(status=503, content_type='application/json', body='{"msg":"down"}'); return
    if m == '4xx':
        route.fulfill(status=400, content_type='application/json', body='{"message":"bad"}'); return
    if m == '401':
        srv['mode'] = 'ok'
        route.fulfill(status=401, content_type='application/json', body='{"message":"JWT expired"}'); return

    # Absent parameters must behave the way PostgREST behaves — no filter means
    # no filter — rather than raising inside the route handler. A stub that
    # crashes leaves the page hanging, which reads as "the suite passed" to
    # anything watching for a failure line.
    cm = re.search(r'server_seq=gt\.(\d+)', url)
    lm = re.search(r'limit=(\d+)', url)
    cursor = int(cm.group(1)) if cm else 0
    limit = int(lm.group(1)) if lm else len(srv['rows'])
    page = [r for r in srv['rows'] if r['server_seq'] > cursor][:limit]
    route.fulfill(status=200, content_type='application/json', body=json.dumps(page))

def row(seq, store, record_id, data, deleted=False, updated_at='2026-08-29T12:00:00.000Z'):
    return {'owner': srv['user']['id'], 'store': store, 'record_id': record_id,
            'data': data, 'deleted': deleted, 'updated_at': updated_at,
            'device_id': 'other-device-uuid', 'op_seq': seq, 'server_seq': seq}

class Res(dict):
    def __missing__(self, key): return None
def _wrap(v):
    if isinstance(v, dict): return Res({k: _wrap(x) for k, x in v.items()})
    if isinstance(v, list): return [_wrap(x) for x in v]
    return v

JS = "async (a) => { const db = await import('./js/db.js'); return (%s)(db, a); }"
def run(page, fn, arg=None):
    return _wrap(page.evaluate(JS % fn, arg))

RESET = """async (db) => {
    await db.idbClear('oplog'); await db.idbClear('tombstones');
    await db.setSetting('lastAckedSeq', 0); await db.setSetting('opSeq', 0);
    await db.setSetting('syncCursor', 0); await db.setSetting('syncAnomalies', []);
    return true;
}"""

# a record as another device would have written it — note the FOREIGN deviceId
# and an updatedAt from days ago, both of which must survive untouched
REMOTE_BIRD = {
    'id': 'remote-bird-0001', 'name': 'زاجل بعيد', 'sex': 'cock', 'rings': [],
    'hatchDate': '', 'colour': '', 'strain': '', 'eyeSign': '', 'status': 'stock',
    'sireId': None, 'damId': None, 'external': False, 'breeder': '', 'owner': '',
    'acquiredFrom': '', 'acquiredDate': '', 'notes': [],
    'provenance': [{'event': 'created', 'at': '2026-06-01T08:00:00.000Z',
                    'deviceId': 'other-device-uuid'}],
    'createdAt': '2026-06-01T08:00:00.000Z',
    'updatedAt': '2026-06-02T09:30:00.000Z',
    'deviceId': 'other-device-uuid',
    'loftId': None,
}

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(60000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.add_init_script(
        f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
    page.route(f'{STUB_URL}/**', handler)
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    # ── 0. inert without a session ──
    r = run(page, "async (db) => await db.pullOnce()")
    check('pull does nothing while signed out', r['ok'] is False and r['reason'] == 'signed-out', str(r))

    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    run(page, RESET)

    # ── 1. ECHO PREVENTION — the behavioural half of the §8 guard ──
    srv['rows'] = [row(1, 'birds', REMOTE_BIRD['id'], REMOTE_BIRD)]
    e = run(page, """async (db, a) => {
        const opsBefore = (await db.listOps()).length;
        const pull = await db.pullOnce();
        const opsAfter = (await db.listOps()).length;
        return { pull, opsBefore, opsAfter, ackedSeq: db.state.settings.lastAckedSeq };
    }""")
    check('a page of rows is applied', e['pull']['ok'] is True and e['pull']['applied'] == 1, str(e['pull']))
    check('APPLYING A PULLED RECORD LOGS ZERO OPS — echo prevention',
          e['opsAfter'] == e['opsBefore'] == 0, f"{e['opsBefore']} -> {e['opsAfter']}")
    check('the cursor advanced to the highest server_seq seen',
          run(page, "(db) => db.state.settings.syncCursor") == 1)
    check('a second pull finds nothing', run(page, "async (db) => (await db.pullOnce()).reason") == 'idle')

    # ── 2. VERBATIM — the record is not re-authored ──
    v = run(page, """async (db, a) => {
        const b = db.getBird(a.id);
        return { updatedAt: b && b.updatedAt, deviceId: b && b.deviceId,
                 provenance: b && JSON.stringify(b.provenance), name: b && b.name,
                 inMirror: !!b, fromStore: (await db.idbGet('birds', a.id)) !== null };
    }""", {'id': REMOTE_BIRD['id']})
    check('updatedAt is byte-identical to what came over the wire',
          v['updatedAt'] == REMOTE_BIRD['updatedAt'], f"{v['updatedAt']} != {REMOTE_BIRD['updatedAt']}")
    check('deviceId still names the device that WROTE it, not this one',
          v['deviceId'] == 'other-device-uuid', str(v['deviceId']))
    check('provenance survives untouched',
          json.loads(v['provenance'] or '[]') == REMOTE_BIRD['provenance'], str(v['provenance']))
    check('the record reached the in-memory mirror (getBird is synchronous)', v['inMirror'] is True)
    check('...and IndexedDB', v['fromStore'] is True)

    # ── 3. a change event fires, so views refresh ──
    ev = run(page, """async (db) => {
        const seen = [];
        const off = db.onChange((e) => seen.push(e));
        await db.setSetting('syncCursor', 0);
        await db.pullOnce();
        off();
        return seen;
    }""")
    check('applying a pulled record emits a change event',
          any(x['type'] == 'sync' for x in ev), str(ev[:2]))

    # ── 4. a pulled DELETE ──
    run(page, RESET)
    srv['rows'] = [row(1, 'birds', REMOTE_BIRD['id'], REMOTE_BIRD),
                   row(2, 'birds', REMOTE_BIRD['id'], REMOTE_BIRD, deleted=True,
                       updated_at='2026-08-29T14:00:00.000Z')]
    d = run(page, """async (db, a) => {
        const pull = await db.pullAll();
        const tombs = await db.listTombstones();
        const t = tombs.find(x => x.recordId === a.id) || null;
        return { pull, gone: db.getBird(a.id) === null, tomb: t,
                 ops: (await db.listOps()).length };
    }""", {'id': REMOTE_BIRD['id']})
    check('a pulled delete removes the record', d['gone'] is True, str(d['pull']))
    check('...and writes a tombstone', d['tomb'] is not None, str(d['tomb']))
    check('...whose `at` is the REMOTE operation time, not now',
          (d['tomb'] or {})['at'] == '2026-08-29T14:00:00.000Z', str((d['tomb'] or {})['at']))
    check('...with seq null, because there is no local op behind it',
          (d['tomb'] or {})['seq'] is None, str((d['tomb'] or {})['seq']))
    check('a pulled delete also logs ZERO ops', d['ops'] == 0, str(d['ops']))

    # ── 5. TOMBSTONE SEMANTICS ──
    # a newer local deletion beats an older incoming record
    run(page, RESET)
    srv['rows'] = [row(1, 'birds', 'tomb-test-0001',
                       {**REMOTE_BIRD, 'id': 'tomb-test-0001', 'name': 'stale-arrival'},
                       updated_at='2026-08-29T10:00:00.000Z')]
    t1 = run(page, """async (db) => {
        // a local deletion at 12:00 — newer than the row's 10:00
        await db.idbPut('tombstones', { id: 'birds:tomb-test-0001', store: 'birds',
            recordId: 'tomb-test-0001', at: '2026-08-29T12:00:00.000Z', deviceId: 'me', seq: 9 });
        const pull = await db.pullOnce();
        const tombs = await db.listTombstones();
        return { pull, present: db.getBird('tomb-test-0001') !== null,
                 tombKept: tombs.some(x => x.recordId === 'tomb-test-0001') };
    }""")
    check('a record older than a local tombstone is SKIPPED',
          t1['present'] is False and t1['pull']['skipped'] == 1, str(t1['pull']))
    check('...and the tombstone is kept', t1['tombKept'] is True)
    check('...but the cursor still advances past it — refetching would never change the outcome',
          run(page, "(db) => db.state.settings.syncCursor") == 1)

    # THE COROLLARY (§2a): a winning record CLEARS the tombstone
    run(page, RESET)
    srv['rows'] = [row(5, 'birds', 'tomb-test-0002',
                       {**REMOTE_BIRD, 'id': 'tomb-test-0002', 'name': 'the-undo'},
                       updated_at='2026-08-29T13:00:00.000Z')]
    t2 = run(page, """async (db) => {
        await db.idbPut('tombstones', { id: 'birds:tomb-test-0002', store: 'birds',
            recordId: 'tomb-test-0002', at: '2026-08-29T11:00:00.000Z', deviceId: 'me', seq: 3 });
        const pull = await db.pullOnce();
        const tombs = await db.listTombstones();
        return { pull, present: db.getBird('tomb-test-0002') !== null,
                 tombGone: !tombs.some(x => x.recordId === 'tomb-test-0002') };
    }""")
    check('a record NEWER than a local tombstone is applied', t2['present'] is True, str(t2['pull']))
    check('...AND the tombstone is deleted — the §2a corollary',
          t2['tombGone'] is True,
          'leaving it would let the next merge re-suppress the record and the device would flip states')

    # ── 6. a pulled delete must NOT cascade ──
    run(page, RESET)
    cas = run(page, """async (db) => {
        const sire = await db.saveBird(db.newBird({ name: 'cascade-sire', sex: 'cock' }));
        const chick = await db.saveBird(db.newBird({ name: 'cascade-chick', sex: 'hen', sireId: sire.id }));
        return { sireId: sire.id, chickId: chick.id };
    }""")
    srv['rows'] = [row(1, 'birds', cas['sireId'], {'id': cas['sireId'], 'name': 'cascade-sire'},
                       deleted=True, updated_at='2026-08-29T15:00:00.000Z')]
    cas2 = run(page, """async (db, a) => {
        await db.setSetting('syncCursor', 0);
        const opsBefore = (await db.listOps()).length;
        await db.pullOnce();
        const chick = db.getBird(a.chickId);
        return { sireGone: db.getBird(a.sireId) === null, chickAlive: !!chick,
                 chickSire: chick && chick.sireId, opsAdded: (await db.listOps()).length - opsBefore };
    }""", cas)
    check('a pulled delete removes only the named record', cas2['sireGone'] is True)
    check('...it does NOT cascade — the offspring survives', cas2['chickAlive'] is True, str(cas2))
    check('...and its parent link is untouched, since the origin device sends that unlink as its own row',
          cas2['chickSire'] == cas['sireId'], str(cas2['chickSire']))
    check('...and no op is logged for any of it', cas2['opsAdded'] == 0, str(cas2['opsAdded']))

    # The transient dangling link above must not OUTLIVE the page. The origin
    # logged its unlinks BEFORE the delete, so server_seq replays them in that
    # order; once a full page has applied, the database is consistent again.
    srv['rows'] = [
        row(1, 'birds', cas['chickId'],
            {'id': cas['chickId'], 'name': 'cascade-chick', 'sex': 'hen',
             'sireId': None, 'damId': None, 'rings': [], 'status': 'stock', 'external': False},
            updated_at='2026-08-29T14:59:00.000Z'),
        row(2, 'birds', cas['sireId'], {'id': cas['sireId'], 'name': 'cascade-sire'},
            deleted=True, updated_at='2026-08-29T15:00:00.000Z'),
    ]
    integ = run(page, """async (db) => {
        const { checkIntegrity } = await import('./js/engine/integrity.js');
        await db.setSetting('syncCursor', 0);
        await db.pullAll();
        const problems = checkIntegrity({
            birds: db.allBirds(),
            pairs: [...db.state.pairs.values()],
            raceResults: [...db.state.raceResults.values()],
            healthEvents: [...db.state.healthEvents.values()],
            tombstones: await db.listTombstones(),
        });
        return { problems, count: problems.length };
    }""")
    check('after the FULL page applies, integrity is clean again',
          integ['count'] == 0, str(integ['problems'])[:200])

    # ── 7. transport failures never move the cursor ──
    run(page, RESET)
    srv['rows'] = [row(1, 'birds', REMOTE_BIRD['id'], REMOTE_BIRD)]
    for mode, label, expect in [('abort', 'a network failure', 'network'),
                                ('server-error', 'a 5xx', 'network'),
                                ('4xx', 'a 4xx', 'rejected')]:
        srv['mode'] = mode
        out = run(page, "async (db) => ({ pull: await db.pullOnce(), cursor: db.state.settings.syncCursor })")
        check(f'{label} leaves the cursor where it was',
              out['pull']['reason'] == expect and out['cursor'] == 0, str(out))
    srv['mode'] = 'ok'

    srv['mode'] = '401'
    out = run(page, "async (db) => ({ pull: await db.pullOnce(), cursor: db.state.settings.syncCursor })")
    check('a 401 mid-pull refreshes once and completes',
          out['pull']['ok'] is True and out['cursor'] == 1, str(out))
    srv['mode'] = 'ok'

    # ── 8. PAGING ──
    run(page, RESET)
    srv['rows'] = [row(i, 'raceResults', f'race-{i:04d}',
                       {'id': f'race-{i:04d}', 'birdId': 'b1', 'date': '2026-05-01', 'distance': 100})
                   for i in range(1, 1201)]
    pg = run(page, """async (db) => {
        const first = await db.pullOnce();
        const afterFirst = db.state.settings.syncCursor;
        const all = await db.pullAll();
        return { first, afterFirst, all, cursor: db.state.settings.syncCursor,
                 stored: (await db.idbGetAll('raceResults')).length };
    }""")
    check('one pull takes a full page of PULL_PAGE rows', pg['first']['rows'] == 500, str(pg['first']['rows']))
    check('...and reports that more remain', pg['first']['more'] is True, str(pg['first']))
    check('...advancing the cursor to the page maximum', pg['afterFirst'] == 500, str(pg['afterFirst']))
    check('pullAll drains every page', pg['cursor'] == 1200, str(pg['cursor']))
    check('...and every row landed', pg['stored'] >= 1200, str(pg['stored']))

    # ── 9. a record that fails LOCAL validation is applied AND reported ──
    run(page, RESET)
    srv['rows'] = [row(1, 'birds', 'invalid-remote-01', {
        **REMOTE_BIRD, 'id': 'invalid-remote-01', 'name': 'impossible',
        'sireId': 'invalid-remote-01',       # its own sire: a pedigree cycle
    })]
    inv = run(page, """async (db) => {
        const pull = await db.pullOnce();
        return { pull, present: db.getBird('invalid-remote-01') !== null,
                 anomalies: db.listSyncAnomalies() };
    }""")
    check('a remote record that fails local rules is still APPLIED',
          inv['present'] is True,
          'dropping it would make the mirror diverge from the server invisibly')
    check('...and is reported as an anomaly', len(inv['anomalies']) == 1, str(inv['anomalies']))
    check('...naming the record', (inv['anomalies'][0] if inv['anomalies'] else Res())['recordId'] == 'invalid-remote-01',
          str(inv['anomalies'][:1]))

    # ── 10. a row naming an unknown store is refused, not guessed ──
    run(page, RESET)
    srv['rows'] = [row(1, 'not_a_store', 'x-1', {'id': 'x-1'})]
    unk = run(page, """async (db) => {
        const pull = await db.pullOnce();
        return { pull, anomalies: db.listSyncAnomalies().length,
                 cursor: db.state.settings.syncCursor };
    }""")
    check('a row naming an unknown store is skipped, not guessed at',
          unk['pull']['applied'] == 0 and unk['pull']['skipped'] == 1, str(unk['pull']))
    check('...and reported', unk['anomalies'] == 1, str(unk['anomalies']))

    # ── 11. MEDIA: metadata arrives, the blob does not, and nothing crashes ──
    run(page, RESET)
    srv['rows'] = [row(1, 'birds', REMOTE_BIRD['id'], REMOTE_BIRD),
                   row(2, 'media', 'remote-media-01',
                       {'id': 'remote-media-01', 'birdId': REMOTE_BIRD['id'], 'kind': 'photo',
                        'subtype': 'side', 'name': 'pigeon.jpg', 'addedAt': '2026-06-02T09:00:00.000Z'})]
    med = run(page, """async (db, a) => {
        await db.pullAll();
        const items = await db.mediaForBird(a.id);
        return { count: items.length, hasBlob: items.some(m => m.blob !== undefined),
                 name: items[0] && items[0].name };
    }""", {'id': REMOTE_BIRD['id']})
    check('media METADATA syncs', med['count'] == 1 and med['name'] == 'pigeon.jpg', str(med))
    check('...and carries no blob, as designed', med['hasBlob'] is False, str(med))

    page.goto(BASE + f"#/bird/{REMOTE_BIRD['id']}", wait_until='load')
    page.wait_for_timeout(1500)
    body = page.inner_text('body')
    check('the bird detail view renders a placeholder instead of throwing',
          'جهاز آخر' in body or 'another device' in body, body[:120].replace('\n', ' '))
    check('no page error from a blob-less media row', not errs, '; '.join(errs[:2]))

    # ── 12. a full cycle PUSHES BEFORE PULLING (§6) ──
    run(page, RESET); srv['requests'].clear(); srv['rows'] = []
    run(page, """async (db) => { await db.saveBird(db.newBird({ name: 'order-test', sex: 'cock' })); }""")
    run(page, "async (db) => await db.syncOnce()")
    methods = [m for m, _ in srv['requests']]
    check('syncOnce pushes before it pulls',
          methods and methods[0] == 'POST' and 'GET' in methods, str(methods[:4]))

    # ── 13. still inert on an unconfigured build ──
    unc = run(page, """async (db) => {
        const saved = globalThis.ZAJIL_SYNC_CONFIG;
        delete globalThis.ZAJIL_SYNC_CONFIG;
        const pull = await db.pullOnce();
        globalThis.ZAJIL_SYNC_CONFIG = saved;
        return pull;
    }""")
    check('pull on an unconfigured build reports config, not a crash', unc['reason'] == 'config', str(unc))

    check('zero page errors overall', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
