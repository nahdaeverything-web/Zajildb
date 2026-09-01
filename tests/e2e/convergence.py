# tests/e2e/convergence.py — TWO DEVICES, one server.
#
# Everything else in the suite tests one device against a scripted server. This
# tests what the design is actually for: two devices belonging to one fancier,
# editing the same loft, reaching the same answer.
#
# Each device is a separate browser CONTEXT, so they have separate IndexedDB and
# separate device identities — genuinely two devices, not two tabs. The server
# is stateful and models the real one: an upsert keyed on (store, record_id),
# a server_seq assigned per write, and §4's last-write-wins enforced where it
# CAN be authoritative.
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


class Server:
    """The corrected sync_records table, in Python.

    THE LAST-WRITE-WINS GUARD IS THE POINT. A client push is a blind upsert, so
    without a comparison here a device that has been offline for months
    overwrites fresher data simply by pushing — and no amount of client-side
    care can prevent it, because the client cannot see what it is about to
    overwrite. §4 can only be authoritative on the server.
    """
    def __init__(self):
        self.rows = {}
        self.seq = 0
        self.lww_enabled = True
        self.received = []          # every row any device asked the server to take

    def upsert(self, incoming):
        self.received.append(incoming)
        key = (incoming['store'], incoming['record_id'])
        old = self.rows.get(key)
        row = dict(incoming)
        if old is not None and self.lww_enabled:
            older = (row['updated_at'], str(row.get('device_id') or '')) <= \
                    (old['updated_at'], str(old.get('device_id') or ''))
            if older:
                row = dict(old)            # keep the winner's body
        self.seq += 1
        row['server_seq'] = self.seq       # advances either way, so the loser re-pulls
        row['owner'] = 'user-uuid-1'
        self.rows[key] = row
        return row

    def page(self, cursor, limit):
        rows = sorted((r for r in self.rows.values() if r['server_seq'] > cursor),
                      key=lambda r: r['server_seq'])
        return rows[:limit]


srv = Server()

def handler(route, request):
    url = request.url
    if '/auth/v1/token' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-1', 'refresh_token': 'REFRESH-1',
            'token_type': 'bearer', 'expires_in': 3600,
            'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'}}))
        return
    if request.method == 'POST':
        body = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps([srv.upsert(r) for r in body]))
        return
    cm = re.search(r'server_seq=gt\.(\d+)', url)
    lm = re.search(r'limit=(\d+)', url)
    cursor = int(cm.group(1)) if cm else 0
    limit = int(lm.group(1)) if lm else 1000
    route.fulfill(status=200, content_type='application/json', body=json.dumps(srv.page(cursor, limit)))


class Res(dict):
    def __missing__(self, key): return None
def _wrap(v):
    if isinstance(v, dict): return Res({k: _wrap(x) for k, x in v.items()})
    if isinstance(v, list): return [_wrap(x) for x in v]
    return v

JS = "async (a) => { const db = await import('./js/db.js'); return (%s)(db, a); }"

with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []

    def device(label):
        ctx = br.new_context()
        ctx.add_init_script(
            f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
        ctx.route(f'{STUB_URL}/**', handler)
        pg = ctx.new_page(); pg.set_default_timeout(60000)
        pg.on('pageerror', lambda e: errs.append(f'{label}: {e}'))
        pg.goto(BASE, wait_until='load'); pg.wait_for_timeout(1800)
        return pg

    A = device('A')
    B = device('B')

    def run(pg, fn, arg=None):
        return _wrap(pg.evaluate(JS % fn, arg))

    for pg in (A, B):
        run(pg, "async (db) => await db.signIn('spike-a@zajil.test','pw')")

    sync = "async (db) => await db.syncOnce()"
    ids = lambda pg: run(pg, "(db) => db.allBirds().map(b => b.id).sort()")
    tombs = lambda pg: run(pg, "async (db) => (await db.listTombstones()).map(t => t.id).sort()")

    devA = run(A, "(db) => db.state.settings.deviceId")
    devB = run(B, "(db) => db.state.settings.deviceId")
    check('the two contexts really are two devices', devA != devB and bool(devA) and bool(devB),
          f'{str(devA)[:8]} vs {str(devB)[:8]}')

    # ── 1. a record made on A reaches B ──
    bird = run(A, """async (db) => await db.saveBird(db.newBird({ name: 'convergence-one', sex: 'cock' }))""")
    run(A, sync); run(B, sync)
    check('a bird created on A arrives on B', bird['id'] in (ids(B) or []), str(ids(B)))

    # ── 2. AMENDMENT A: delete on A, B pulls it, undo on A, sync both ──
    snapshot = run(A, "async (db, a) => await db.deleteBird(a.id)", {'id': bird['id']})
    run(A, sync); run(B, sync)
    check('the delete reaches B', bird['id'] not in (ids(B) or []), str(ids(B)))
    check('...and B holds a tombstone for it', f"birds:{bird['id']}" in (tombs(B) or []), str(tombs(B)))

    # the undo. restoreBird deliberately reinstates the ORIGINAL updatedAt, so
    # this is exactly the case the op-time rule exists for: the record looks
    # old, the OPERATION is new, and only the operation time can beat B's
    # tombstone.
    run(A, "async (db, a) => await db.restoreBird(a.snap)", {'snap': snapshot})
    run(A, sync); run(B, sync)

    a_ids, b_ids = ids(A), ids(B)
    a_tombs, b_tombs = tombs(A), tombs(B)
    check('AFTER THE UNDO, A HOLDS THE BIRD', bird['id'] in (a_ids or []), str(a_ids))
    check('AFTER THE UNDO, B HOLDS THE BIRD', bird['id'] in (b_ids or []), str(b_ids))
    check('...A retains NO tombstone for it', f"birds:{bird['id']}" not in (a_tombs or []), str(a_tombs))
    check('...B retains NO tombstone for it', f"birds:{bird['id']}" not in (b_tombs or []), str(b_tombs))
    check('the two devices converged', sorted(a_ids or []) == sorted(b_ids or []),
          f'A={a_ids} B={b_ids}')

    # ── 3. LWW — the later edit wins, whichever device pushes first ──
    for order, first, second, label in [('A-then-B', A, B, 'A pushes first'),
                                        ('B-then-A', B, A, 'B pushes first')]:
        base = run(A, """async (db) => await db.saveBird(db.newBird({ name: 'lww-base', sex: 'hen' }))""")
        run(A, sync); run(B, sync)
        # A edits, then B edits — B's edit is strictly later in real time
        run(A, "async (db, a) => await db.saveBird({ ...db.getBird(a.id), name: 'edited-on-A' })", {'id': base['id']})
        B.wait_for_timeout(20)
        run(B, "async (db, a) => await db.saveBird({ ...db.getBird(a.id), name: 'edited-on-B' })", {'id': base['id']})
        run(first, sync); run(second, sync); run(first, sync)
        names = [run(pg, "(db, a) => (db.getBird(a.id) || {}).name", {'id': base['id']}) for pg in (A, B)]
        check(f'the LATER edit wins when {label}', names == ['edited-on-B', 'edited-on-B'], str(names))

    # ── 4. the loser's op is superseded, and never leaves the device ──
    # The server's own guard would refuse a stale body anyway, so this is belt
    # and braces — but it is the belt that matters on a weak connection: there
    # is no reason to spend a round trip sending a record already known to have
    # lost, and no reason to depend on the server to undo it.
    lose = run(A, """async (db) => await db.saveBird(db.newBird({ name: 'supersede-base', sex: 'cock' }))""")
    run(A, sync); run(B, sync)
    run(A, "async (db, a) => await db.saveBird({ ...db.getBird(a.id), name: 'THE-LOSER' })", {'id': lose['id']})
    B.wait_for_timeout(20)
    run(B, "async (db, a) => await db.saveBird({ ...db.getBird(a.id), name: 'THE-WINNER' })", {'id': lose['id']})
    run(B, sync)                       # the winner reaches the server first
    srv.received.clear()
    run(A, sync)                       # A pulls the winner, then pushes
    sent = [r for r in srv.received if r['record_id'] == lose['id']]
    check('a losing local op is marked superseded rather than deleted',
          (run(A, "async (db) => (await db.listOps()).filter(o => o.superseded).length") or 0) >= 1)
    check('...and the log still holds it, as §4 promises',
          (run(A, "async (db) => (await db.listOps()).length") or 0) > 0)
    check('THE LOSER IS NEVER SENT — no round trip is spent on a record already beaten',
          not any((r.get('data') or {}).get('name') == 'THE-LOSER' for r in sent),
          f'{len(sent)} rows for that record were pushed after it lost')
    check('...and both devices hold the winner',
          [run(pg, "(db, a) => (db.getBird(a.id) || {}).name", {'id': lose['id']}) for pg in (A, B)]
          == ['THE-WINNER', 'THE-WINNER'])

    # ── 5. a stale device signing in must NOT overwrite fresher server data ──
    C = device('C')
    run(C, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    fresh = run(B, """async (db) => await db.saveBird(db.newBird({ name: 'fresh-on-B', sex: 'cock' }))""")
    run(B, sync)
    # C holds the SAME record, as it knew it months ago, and has never synced
    run(C, """async (db, a) => {
        const stale = { ...a.rec, name: 'stale-on-C', updatedAt: '2026-06-01T08:00:00.000Z' };
        await db.idbPut('birds', stale);
        db.state.birds.set(stale.id, stale);
        await db.idbClear('oplog');
        await db.setSetting('opSeq', 0);
        await db.setSetting('lastSyncAt', null);      // never synced
        await db.setSetting('lastAckedSeq', 0);
        await db.setSetting('syncCursor', 0);
    }""", {'rec': fresh})
    first_sync = run(C, sync)
    check('C treats this as a first login', first_sync['firstLogin'] is True, str(first_sync)[:120])
    check('...enqueueing its local records as synthetic ops', (first_sync['enqueued'] or 0) >= 1,
          str(first_sync['enqueued']))
    c_name = run(C, "(db, a) => (db.getBird(a.id) || {}).name", {'id': fresh['id']})
    check("THE SERVER'S NEWER VERSION WINS — the stale device does not overwrite it",
          c_name == 'fresh-on-B', f'C now shows {c_name}')
    run(B, sync)
    b_name = run(B, "(db, a) => (db.getBird(a.id) || {}).name", {'id': fresh['id']})
    check('...and B still holds its own fresher version', b_name == 'fresh-on-B', str(b_name))

    # the synthetic op carried the RECORD's time, not now()
    synth = run(C, """async (db, a) => {
        const ops = await db.listOps();
        const mine = ops.filter(o => o.recordId === a.id);
        return mine.map(o => o.at);
    }""", {'id': fresh['id']})
    check('the synthetic op carried the record\'s own updatedAt, not now()',
          any(str(x).startswith('2026-06-01') for x in (synth or [])), str(synth))

    # ── 6. the duplicate notice ──
    D = device('D')
    run(D, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    ring = {'country': 'JOR', 'union': 'JRPF', 'year': '2025', 'serial': '01234',
            'raw': 'JOR-JRPF-2025-01234', 'type': 'national'}
    run(B, "async (db, a) => { await db.saveBird(db.newBird({ name: 'same-bird-B', sex: 'cock', rings: [a.ring] })); }",
        {'ring': ring})
    run(B, sync)
    dup = run(D, """async (db, a) => {
        // D entered the same physical bird independently, so it has a DIFFERENT
        // id — which is exactly why the first sync produces two records.
        await db.saveBird(db.newBird({ name: 'same-bird-D', sex: 'cock', rings: [a.ring] }));
        await db.setSetting('lastSyncAt', null);
        return await db.syncOnce();
    }""", {'ring': ring})
    check('after a first sync, duplicate rings are counted',
          (dup or {})['duplicates'] >= 1, str((dup or {})['duplicates']))

    # The notice is asserted where the fancier would see it. The app consumes it
    # from the sync-complete event, so reading it back through the API here
    # would only prove the test can beat the app to it.
    D.wait_for_timeout(600)
    toasts = D.eval_on_selector_all('.toast', 'ns => ns.map(n => n.textContent)')
    check('...and the fancier is told, once, in Arabic',
          any('تمت المزامنة' in x and 'مكررة' in x for x in toasts), str(toasts))
    check('...with the count in the message',
          any(('١' in x or '1' in x) for x in toasts if 'تمت المزامنة' in x), str(toasts))

    run(D, "async (db) => { await db.setSetting('syncCursor', 0); await db.syncOnce(); }")
    D.wait_for_timeout(600)
    again = D.eval_on_selector_all('.toast', 'ns => ns.map(n => n.textContent)')
    check('...and NOT told again on the next sync',
          len([x for x in again if 'تمت المزامنة' in x]) <= len([x for x in toasts if 'تمت المزامنة' in x]),
          str(again))
    check('both records survive — a ring is not identity',
          (run(D, "(db) => db.allBirds().filter(b => (b.rings||[]).some(r => r.raw === 'JOR-JRPF-2025-01234')).length") or 0) == 2,
          'the duplicate finder reports, it never merges')

    # ── 7. THE PRISTINE DEFAULT LOFT (R4) ──
    # initDB() creates an empty loft on every fresh device. Pushing it added one
    # empty loft to the account per device, and — the half that actually
    # damages data — left currentLoftId pointing at it, so every bird created on
    # a second device was filed under an id the rest of the loft knew nothing
    # about. One loft, silently split in two.
    # A deterministic fixture: exactly ONE loft on the server. The earlier
    # devices in this suite each pushed their own, and with several present
    # adoption correctly declines — which is the next case, not this one.
    srv.rows.clear()
    REAL_LOFT = 'the-real-loft-uuid'
    srv.upsert({'store': 'lofts', 'record_id': REAL_LOFT,
                'data': {'id': REAL_LOFT, 'name': 'لوفت الزرقاء', 'location': 'الزرقاء',
                         'statuses': [], 'createdAt': '2026-01-01T00:00:00.000Z',
                         'updatedAt': '2026-01-01T00:00:00.000Z'},
                'deleted': False, 'updated_at': '2026-01-01T00:00:00.000Z',
                'device_id': '33333333-3333-3333-3333-333333333333', 'op_seq': 1})

    E = device('E')
    run(E, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    pristine = run(E, """(db) => ({
        lofts: db.state.lofts.size,
        currentIsPristine: db.isPristineLoft(db.currentLoft()),
        name: (db.currentLoft() || {}).name })""")
    check('a fresh device starts on an untouched default loft',
          pristine['currentIsPristine'] is True and pristine['name'] == '', str(pristine))

    srv_lofts_before = len([r for r in srv.rows.values() if r['store'] == 'lofts' and not r['deleted']])
    run(E, """async (db) => {
        await db.setSetting('lastSyncAt', null);
        return await db.syncOnce();
    }""")
    after = run(E, """async (db) => {
        const bird = await db.saveBird(db.newBird({ name: 'filed-after-adoption', sex: 'cock' }));
        return { lofts: db.state.lofts.size, currentId: db.state.currentLoftId,
                 currentName: (db.currentLoft() || {}).name, birdLoftId: bird.loftId };
    }""")
    srv_lofts_after = len([r for r in srv.rows.values() if r['store'] == 'lofts' and not r['deleted']])

    check('the pristine default is NEVER pushed',
          srv_lofts_after == srv_lofts_before,
          f'server lofts {srv_lofts_before} -> {srv_lofts_after}')
    check('...it is dropped once a remote loft is adopted', after['lofts'] == 1, str(after))
    check('...and dropping it logs NO op and writes NO tombstone',
          run(E, "async (db) => (await db.listOps()).filter(o => o.store === 'lofts' && o.op === 'delete').length") == 0
          and run(E, "async (db) => (await db.listTombstones()).filter(t => t.store === 'lofts').length") == 0)
    # THE assertion whose absence let this through — filed into the ADOPTED id
    # specifically, not merely into whatever this device happens to call current.
    check('THE SECOND DEVICE FILES NEW BIRDS INTO THE ADOPTED LOFT',
          after['birdLoftId'] == REAL_LOFT and after['currentId'] == REAL_LOFT, str(after))
    check('...and shows the real loft name, not a blank one',
          after['currentName'] == 'لوفت الزرقاء', repr(after['currentName']))

    # zero remote lofts: nothing to adopt, keep the local default, push nothing
    F = device('F')
    zero = run(F, """async (db) => {
        // a device whose account has no lofts at all: adoption must not fire
        const before = db.state.currentLoftId;
        const adopted = await db.adoptRemoteLoftIfPristine();
        return { adopted, unchanged: db.state.currentLoftId === before,
                 lofts: db.state.lofts.size };
    }""")
    check('with ZERO remote lofts, nothing is adopted and the default stays',
          zero['adopted'] is None and zero['unchanged'] is True and zero['lofts'] == 1, str(zero))

    # several remote lofts: never guess
    several = run(F, """async (db) => {
        await db.applySyncPut('lofts', { id: 'remote-a', name: 'لوفت أ', location: '',
            statuses: [], createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z' },
            '2026-01-01T00:00:00.000Z', 'remote-a');
        await db.applySyncPut('lofts', { id: 'remote-b', name: 'لوفت ب', location: '',
            statuses: [], createdAt: '2026-01-01T00:00:00.000Z', updatedAt: '2026-01-01T00:00:00.000Z' },
            '2026-01-01T00:00:00.000Z', 'remote-b');
        const before = db.state.currentLoftId;
        const adopted = await db.adoptRemoteLoftIfPristine();
        return { adopted, unchanged: db.state.currentLoftId === before, lofts: db.state.lofts.size };
    }""")
    check('with SEVERAL remote lofts, nothing is adopted — never guess',
          several['adopted'] is None and several['unchanged'] is True, str(several))

    # a default that already holds records is NOT pristine, and DOES push
    G = device('G')
    used = run(G, """async (db) => {
        await db.saveBird(db.newBird({ name: 'filed-before-signin', sex: 'hen' }));
        const loft = db.currentLoft();
        return { pristine: db.isPristineLoft(loft), name: loft.name };
    }""")
    check('a default loft that already holds records is NOT pristine',
          used['pristine'] is False and used['name'] == '',
          'unnamed but used is still the fancier\'s loft')
    pushed = run(G, """async (db) => {
        await db.signIn('spike-a@zajil.test','pw');
        await db.setSetting('lastSyncAt', null);
        const enq = await db.enqueueFirstSyncOps();
        const ops = await db.listOps();
        return { enqueued: enq, loftOps: ops.filter(o => o.store === 'lofts').length };
    }""")
    check('...so it IS enqueued for the server', pushed['loftOps'] >= 1, str(pushed))

    check('zero page errors across all devices', not errs, '; '.join(errs[:2]))
    br.close()

print(f'\n{ok} passed, {fail} failed')
