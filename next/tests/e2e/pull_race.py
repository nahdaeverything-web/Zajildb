# tests/e2e/pull_race.py — RF-26 (RULED 2026-11-18): a pull never takes back a local write made while it was applying.
#
# The defect, measured on the live build: a pull page decided last-write-wins against the operations that were
# pending WHEN THE PAGE STARTED and then wrote each row without looking at the device. A save made after the page
# started was invisible to it, an older row — typically this device's own echo — was written over the save, and the
# next local save of that record read the reverted version and pushed it as the newest.
#
# The fix (src/db/records.js): for each row, the comparison against the record on the device and its unpushed
# operations, and the write, are ONE IndexedDB transaction.
#
# DETERMINISTIC, not a stress loop. The page fires a change event for every row it applies; the local write is
# started from inside that event for the FIRST row, so it always begins after the page's index was built and while
# the page is still applying. Where the row under test sits in the page then decides which half is exercised:
#   · last, behind a run of filler rows  → the local op is logged by the time the row is reached (the op half);
#   · immediately next                   → the record is on the device and its op is NOT logged yet (the record half).
# Each mutant is named at the check it fails.
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12
import json, os, re, datetime
from playwright.sync_api import sync_playwright
from _net import Net                           # THE NET (RULED 2026-10-08): armed beneath the stub, asserted at the end
NET = Net()

BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
STUB_URL = 'https://stub.zajil.test'
STUB_KEY = 'sb_publishable_STUBKEY'

ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {str(e)[:600]}')

srv = {'rows': [], 'pushed': [], 'user': {'id': 'user-uuid-1', 'email': 'spike-a@zajil.test'}}

def handler(route, request):
    try:
        url = request.url
        if '/auth/v1/token' in url:
            route.fulfill(status=200, content_type='application/json', body=json.dumps({
                'access_token': 'ACCESS-1', 'refresh_token': 'REFRESH-1',
                'token_type': 'bearer', 'expires_in': 3600, 'user': srv['user']})); return
        if '/rest/v1/sync_records' not in url:
            route.fulfill(status=404, content_type='application/json', body='{"message":"not stubbed"}'); return
        if request.method == 'POST':               # push — accepted, and kept so an echo can be built from it
            rows = json.loads(request.post_data or '[]')
            srv['pushed'].extend(rows)
            route.fulfill(status=200, content_type='application/json', body=json.dumps(rows)); return
        cm = re.search(r'server_seq=gt\.(\d+)', url); lm = re.search(r'limit=(\d+)', url)
        cursor = int(cm.group(1)) if cm else 0
        limit = int(lm.group(1)) if lm else len(srv['rows'])
        page = [r for r in srv['rows'] if r['server_seq'] > cursor][:limit]
        route.fulfill(status=200, content_type='application/json', body=json.dumps(page))
    except Exception as e:                          # a stub that raises leaves the page waiting; answer instead
        try: route.fulfill(status=500, content_type='application/json', body=json.dumps({'message': f'stub: {e}'}))
        except Exception: pass

def row(seq, store, record_id, data, updated_at, device_id='other-device-uuid', deleted=False):
    return {'owner': srv['user']['id'], 'store': store, 'record_id': record_id, 'data': data, 'deleted': deleted,
            'updated_at': updated_at, 'device_id': device_id, 'op_seq': seq, 'server_seq': seq}

def filler(seq):
    i = f'filler-{seq:04d}'
    return row(seq, 'birds', i, {'id': i, 'name': i, 'sex': 'cock', 'rings': [], 'status': 'stock', 'sireId': None,
                                 'damId': None, 'external': False, 'notes': [], 'updatedAt': '2026-06-02T09:30:00.000Z',
                                 'deviceId': 'other-device-uuid', 'loftId': None}, '2026-06-02T09:30:00.000Z')

def later(minutes):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%S.000Z')

JS = "async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }"
def run(page, fn, arg=None): return page.evaluate(JS % fn, arg)

RESET = """async (db) => {
    for (const b of db.allBirds()) { await db.idbDelete('birds', b.id); db.state.birds.delete(b.id); }
    await db.idbClear('oplog'); await db.idbClear('tombstones');
    await db.setSetting('lastAckedSeq', 0); await db.setSetting('opSeq', 0);
    await db.setSetting('syncCursor', 0); await db.setSetting('syncAnomalies', []);
    return true;
}"""

# Save a bird and push it, so the server holds it and its row will come back as this device's own echo.
SAVE_AND_PUSH = """async (db, a) => {
    const bird = await db.saveBird(db.newBird({ name: a.name, sex: 'cock' }));
    const push = await db.pushOnce();
    return { id: bird.id, pushOk: push.ok, pending: (await db.listOps()).filter(o => o.seq > (db.state.settings.lastAckedSeq || 0)).length };
}"""

# Pull one page; from inside the change event of the FIRST row applied, start the local write (never awaited by the
# pull). Returns what the device holds afterwards, in memory and in the store, and the state of the local op.
PULL_WITH_WRITE = """async (db, a) => {
    let started = null, firedAt = null;
    const off = db.onChange((e) => {
        if (started || e.type !== 'sync') return;
        firedAt = e.id;
        if (a.write === 'save')    started = db.saveBird({ ...db.getBird(a.id), name: a.name });
        if (a.write === 'restore') started = db.restoreBird(window.__snap);
    });
    const pull = await db.pullOnce();
    off();
    const wrote = await started;
    const mem = db.getBird(a.id), disk = await db.idbGet('birds', a.id);
    const ops = (await db.listOps()).filter(o => o.recordId === a.id && o.seq > (db.state.settings.lastAckedSeq || 0));
    return { pull: { ok: pull.ok, applied: pull.applied, skipped: pull.skipped, superseded: pull.superseded, rows: pull.rows },
             firedAt, wroteName: wrote && wrote.name, mem: mem && mem.name, disk: disk && disk.name,
             memAt: mem && mem.updatedAt, diskAt: disk && disk.updatedAt,
             ops: ops.map(o => ({ op: o.op, origin: o.origin, superseded: !!o.superseded, name: o.record && o.record.name })) };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(60000); NET.arm(check=check, ctx=page.context)
    errs = []; page.on('pageerror', lambda e, _p=page: errs.append(perr(e, _p)))
    page.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB_URL}', publishableKey: '{STUB_KEY}' }};")
    page.route(f'{STUB_URL}/**', handler)
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(600)
    page.evaluate("async () => { await window.__zajilReady; }"); page.wait_for_timeout(2000)
    run(page, "async (db) => await db.signIn('spike-a@zajil.test','pw')")
    me = run(page, "(db) => db.state.settings.deviceId")

    def echo_of(record_id, seq):
        """This device's own pushed row for a record, as the server would send it back."""
        mine = [r for r in srv['pushed'] if r['record_id'] == record_id]
        r = dict(mine[-1]); r.update(owner=srv['user']['id'], server_seq=seq)
        return r

    # ── 1. THE STRESS SHAPE, made deterministic: a save while the page applies, the echo row last ──
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'نسخة أولى'})
    check('[setup] the first version was pushed and nothing is pending', b['pushOk'] is True and b['pending'] == 0, b)
    srv['rows'] = [filler(n) for n in range(1, 41)] + [echo_of(b['id'], 41)]
    check('[setup] the echo row is this device\'s own, and carries the first version',
          srv['rows'][-1]['device_id'] == me and srv['rows'][-1]['data']['name'] == 'نسخة أولى', srv['rows'][-1]['device_id'])
    r = run(page, PULL_WITH_WRITE, {'id': b['id'], 'write': 'save', 'name': 'نسخة ثانية'})
    check('[page] the local save started from the first row\'s change event — after the page\'s index was built',
          r['firedAt'] == 'filler-0001' and r['wroteName'] == 'نسخة ثانية', r)
    check('[page · M-old fails here] a save made while a pull page is applying is NOT reverted by the device\'s own echoed row — in memory',
          r['mem'] == 'نسخة ثانية', r)
    check('[page · M-old fails here] …nor in the store', r['disk'] == 'نسخة ثانية', r)
    check('[page] the echoed row was skipped, the forty others applied', r['pull']['skipped'] == 1 and r['pull']['applied'] == 40, r['pull'])
    check('[page] the save\'s operation is still owed to the server — not superseded',
          len(r['ops']) == 1 and r['ops'][0]['superseded'] is False and r['ops'][0]['name'] == 'نسخة ثانية', r['ops'])
    # what RF-26 did next on the live build: a later save of the same record read the reverted version and pushed it
    n = run(page, """async (db, a) => {
        const cur = db.getBird(a.id);
        await db.saveBird({ ...cur, colour: 'أزرق' });
        const push = await db.pushOnce();
        return { ok: push.ok };
    }""", {'id': b['id']})
    sent = [x for x in srv['pushed'] if x['record_id'] == b['id']][-1]
    check('[page · M-old fails here] the next save of that record carries the second version to the server, not the reverted one',
          n['ok'] is True and sent['data']['name'] == 'نسخة ثانية' and sent['data']['colour'] == 'أزرق', sent['data'].get('name'))

    # ── 2. THE RECORD HALF: the echo row is the very next one, the save's op is not logged yet ──
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'نسخة أولى'})
    srv['rows'] = [filler(1), echo_of(b['id'], 2)] + [filler(n) for n in range(3, 8)]
    r = run(page, PULL_WITH_WRITE, {'id': b['id'], 'write': 'save', 'name': 'نسخة ثانية'})
    check('[record · M-norecord fails here] a save whose record is on the device and whose op is not logged yet is NOT overwritten by the next row — in memory',
          r['mem'] == 'نسخة ثانية', r)
    check('[record · M-norecord fails here] …nor in the store', r['disk'] == 'نسخة ثانية', r)
    check('[record] memory and the store agree on the record', r['memAt'] == r['diskAt'], (r['memAt'], r['diskAt']))
    check('[record] the save\'s operation is owed, not superseded',
          len(r['ops']) == 1 and r['ops'][0]['superseded'] is False, r['ops'])

    # ── 3. THE OP HALF: an undo made while the page applies; the echoed DELETE arrives last ──
    # restoreBird puts the record back with its ORIGINAL, older stamp, so the record on the device does not look
    # newer than the deletion — only the restore's operation says the deletion was undone.
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'طائر محذوف ثم مُعاد'})
    d = run(page, """async (db, a) => { window.__snap = await db.deleteBird(a.id); const push = await db.pushOnce();
        return { ok: push.ok, gone: db.getBird(a.id) === null }; }""", {'id': b['id']})
    check('[setup] the deletion was pushed', d['ok'] is True and d['gone'] is True and srv['pushed'][-1]['deleted'] is True, d)
    srv['rows'] = [filler(n) for n in range(1, 41)] + [echo_of(b['id'], 41)]
    r = run(page, PULL_WITH_WRITE, {'id': b['id'], 'write': 'restore'})
    check('[undo · M-snapshot fails here] an undo made while a pull page is applying is NOT undone by the device\'s own echoed deletion — in memory',
          r['mem'] == 'طائر محذوف ثم مُعاد', r)
    check('[undo · M-snapshot fails here] …nor in the store', r['disk'] == 'طائر محذوف ثم مُعاد', r)
    tomb = run(page, "async (db, a) => (await db.listTombstones()).some(t => t.recordId === a.id)", {'id': b['id']})
    check('[undo] no tombstone is left for the restored bird', tomb is False)
    check('[undo] the restore\'s operation is owed, not superseded',
          any(o['origin'] == 'restore' and not o['superseded'] for o in r['ops']), r['ops'])

    # ── 4. THE PLAIN CASE: save, then save the same record again, then the first save's echo arrives ──
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'نسخة أولى'})
    run(page, "async (db, a) => { await db.saveBird({ ...db.getBird(a.id), name: 'نسخة ثانية' }); }", {'id': b['id']})
    srv['rows'] = [echo_of(b['id'], 1)]
    e1 = run(page, """async (db, a) => { const pull = await db.pullOnce(); const disk = await db.idbGet('birds', a.id);
        return { skipped: pull.skipped, applied: pull.applied, mem: db.getBird(a.id).name, disk: disk.name }; }""", {'id': b['id']})
    check('[plain] save, save again, then the first save\'s echo: the second version stays, in memory and in the store',
          e1['mem'] == 'نسخة ثانية' and e1['disk'] == 'نسخة ثانية' and e1['skipped'] == 1 and e1['applied'] == 0, e1)
    e2 = run(page, """async (db, a) => { const push = await db.pushOnce(); return { ok: push.ok }; }""", {'id': b['id']})
    srv['rows'].append(echo_of(b['id'], 2))
    e3 = run(page, """async (db, a) => { const before = (await db.listOps()).length; const pull = await db.pullOnce();
        const disk = await db.idbGet('birds', a.id);
        return { applied: pull.applied, mem: db.getBird(a.id).name, disk: disk.name, added: (await db.listOps()).length - before }; }""", {'id': b['id']})
    check('[plain] the second save is pushed and ITS echo is applied as it is — same record, no operation logged',
          e2['ok'] is True and e3['applied'] == 1 and e3['mem'] == 'نسخة ثانية' and e3['disk'] == 'نسخة ثانية' and e3['added'] == 0, e3)

    # ── 5. A DELETION from another device, dated BEFORE a save made while the page applies ──
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'نسخة أولى'})
    srv['rows'] = [filler(1), row(2, 'birds', b['id'], {'id': b['id']}, '2026-06-02T09:30:00.000Z', deleted=True)]
    r = run(page, PULL_WITH_WRITE, {'id': b['id'], 'write': 'save', 'name': 'نسخة ثانية'})
    check('[delete · M-norecord fails here] a deletion older than a save made while the page applies does not remove the record',
          r['mem'] == 'نسخة ثانية' and r['disk'] == 'نسخة ثانية', r)

    # ── 6. CONTROLS: last-write-wins still decides for the row when the row IS the later one ──
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'نسخة أولى'})
    newer = {'id': b['id'], 'name': 'من الجهاز الآخر', 'sex': 'cock', 'rings': [], 'status': 'stock', 'sireId': None, 'damId': None,
             'external': False, 'notes': [], 'updatedAt': later(5), 'deviceId': 'other-device-uuid', 'loftId': None}
    srv['rows'] = [filler(n) for n in range(1, 41)] + [row(41, 'birds', b['id'], newer, later(5))]
    r = run(page, PULL_WITH_WRITE, {'id': b['id'], 'write': 'save', 'name': 'نسخة ثانية'})
    check('[control] a row LATER than the save made during the page wins: the record is the other device\'s',
          r['mem'] == 'من الجهاز الآخر' and r['disk'] == 'من الجهاز الآخر', r)
    check('[control] …and the beaten local operation is superseded, so it is never pushed over the winner',
          r['pull']['superseded'] == 1 and len(r['ops']) == 1 and r['ops'][0]['superseded'] is True, (r['pull'], r['ops']))
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'نسخة أولى'})
    srv['rows'] = [row(1, 'birds', b['id'], {'id': b['id']}, later(5), deleted=True)]
    g = run(page, """async (db, a) => { const pull = await db.pullOnce();
        return { applied: pull.applied, mem: db.getBird(a.id) === null, disk: (await db.idbGet('birds', a.id)) === null }; }""", {'id': b['id']})
    check('[control] a deletion LATER than the record on the device removes it', g['applied'] == 1 and g['mem'] and g['disk'], g)

    # ── 7. a direct call, with no page index at all, reads every unpushed operation itself ──
    run(page, RESET); srv['pushed'].clear()
    v = run(page, """async (db) => {
        const bird = await db.saveBird(db.newBird({ name: 'محلي', sex: 'hen' }));
        const res = await db.applySyncPut('birds', { ...bird, name: 'أقدم' }, '2026-06-02T09:30:00.000Z', bird.id);
        return { res, name: db.getBird(bird.id).name };
    }""")
    check('[direct] applySyncPut called without a page index still sees the unpushed operation and leaves the record',
          v['res']['applied'] is False and v['res']['skipped'] == 'local-op' and v['name'] == 'محلي', v)

    # ── 8. only a record THIS device stamped can stand against a row ──
    # A record that arrived by pull keeps its author's stamp, which may be later than the operation time of the next
    # row (a restored or imported record, or an author whose clock ran ahead). It must never block that row: the
    # device would keep a version the server and every other device have moved on from.
    run(page, RESET); srv['pushed'].clear()
    far = {'id': 'remote-ahead-0001', 'name': 'قبل', 'sex': 'cock', 'rings': [], 'status': 'stock', 'sireId': None, 'damId': None,
           'external': False, 'notes': [], 'updatedAt': later(600), 'deviceId': 'other-device-uuid', 'loftId': None}
    srv['rows'] = [row(1, 'birds', far['id'], far, '2026-06-02T09:30:00.000Z')]
    run(page, "async (db) => await db.pullOnce()")
    srv['rows'].append(row(2, 'birds', far['id'], dict(far, name='بعد'), '2026-06-03T09:30:00.000Z'))
    o = run(page, "async (db, a) => { const pull = await db.pullOnce(); return { applied: pull.applied, name: db.getBird(a.id).name }; }", {'id': far['id']})
    check('[other device · M-anydevice fails here] a record another device stamped never blocks the next row for it, whatever its stamp says',
          o['applied'] == 1 and o['name'] == 'بعد', o)

    # ── 9. THE TWO WINDOWS INSIDE A LOCAL WRITER (measured 2026-11-19, then closed) ──
    # A local delete used to remove the record, THEN log its operation, THEN write its tombstone — three transactions;
    # an undo used to put the record back, THEN log, THEN clear the tombstone. A pulled row applied between the first
    # step and the rest saw neither the operation nor the tombstone. Made deterministic by issuing the row from
    # INSIDE the writer's own first store request: the row's transaction is then queued directly behind it.
    HOOKED = """async (db, a) => {
        const proto = IDBObjectStore.prototype, orig = proto[a.method]; let row = null, fired = 0;
        proto[a.method] = function (v) {
            const key = a.method === 'delete' ? v : (v && v.id);
            if (this.name === 'birds' && key === a.id && !fired) {
                fired++;
                row = a.method === 'delete' ? db.applySyncPut('birds', a.echo.data, a.echo.updated_at, a.id, { deviceId: a.echo.device_id })
                                            : db.applySyncDelete('birds', a.id, a.echo.updated_at, { deviceId: a.echo.device_id });
            }
            return orig.apply(this, arguments);
        };
        try { if (a.method === 'delete') window.__snap = await db.deleteBird(a.id); else await db.restoreBird(window.__snap); }
        finally { proto[a.method] = orig; }
        const res = await row;
        const disk = await db.idbGet('birds', a.id), mem = db.getBird(a.id);
        const tomb = (await db.listTombstones()).some(t => t.recordId === a.id);
        const ops = (await db.listOps()).filter(o => o.recordId === a.id && o.seq > (db.state.settings.lastAckedSeq || 0));
        return { fired, row: res && { applied: res.applied, skipped: res.skipped }, disk: !!disk, mem: !!mem, tomb,
                 ops: ops.map(o => ({ op: o.op, origin: o.origin, superseded: !!o.superseded })) };
    }"""
    run(page, RESET); srv['pushed'].clear()
    b = run(page, SAVE_AND_PUSH, {'name': 'يُحذف والصف في الطريق'})
    put_echo = echo_of(b['id'], 1)
    w = run(page, HOOKED, {'id': b['id'], 'method': 'delete', 'echo': put_echo})
    check('[window · setup] the echoed row was issued from inside the delete, once', w['fired'] == 1 and w['row'] is not None, w)
    check('[window · delete · M-split-delete fails here] a row applied behind a local delete\'s first write does NOT put the record back — the store and memory both say deleted',
          w['disk'] is False and w['mem'] is False and w['row']['applied'] is False, w)
    check('[window · delete] the deletion is whole: its tombstone is there and its operation is owed, not superseded',
          w['tomb'] is True and any(o['op'] == 'delete' and not o['superseded'] for o in w['ops']), w)
    run(page, "async (db) => await db.pushOnce()")
    del_echo = echo_of(b['id'], 2)
    check('[window · setup] the deletion was pushed', del_echo['deleted'] is True, del_echo['deleted'])
    w = run(page, HOOKED, {'id': b['id'], 'method': 'put', 'echo': del_echo})
    check('[window · setup] the echoed deletion was issued from inside the undo, once', w['fired'] == 1 and w['row'] is not None, w)
    check('[window · undo · M-split-undo fails here] a deletion applied behind an undo\'s first write does NOT take the bird away again — the store and memory both hold it',
          w['disk'] is True and w['mem'] is True and w['row']['applied'] is False, w)
    check('[window · undo] the undo is whole: no tombstone is left and its operation is owed, not superseded',
          w['tomb'] is False and any(o['origin'] == 'restore' and not o['superseded'] for o in w['ops']), w)

    # ── 10. THE SAME WINDOWS IN THE GENERIC AND MEDIA WRITERS (RULED 2026-11-20, before stage 2's gate) ──
    # Section 9 drives deleteBird/restoreBird only. The generic remove/restore (pairs, races, health, lofts) and
    # deleteMedia/restoreMedia go through the same one-transaction writer; each is driven here the same way: the
    # pulled row is issued from INSIDE the writer's own first store request on that record.
    HOOKED_ANY = """async (db, a) => {
        const proto = IDBObjectStore.prototype, orig = proto[a.method]; let row = null, fired = 0;
        proto[a.method] = function (v) {
            const key = a.method === 'delete' ? v : (v && v.id);
            if (this.name === a.store && key === a.id && !fired) {
                fired++;
                row = a.method === 'delete' ? db.applySyncPut(a.store, a.echo.data, a.echo.updated_at, a.id, { deviceId: a.echo.device_id })
                                            : db.applySyncDelete(a.store, a.id, a.echo.updated_at, { deviceId: a.echo.device_id });
            }
            return orig.apply(this, arguments);
        };
        try {
            if (a.writer === 'generic') { if (a.method === 'delete') window.__snapAny = await db.Health.remove(a.id); else await db.Health.restore(window.__snapAny); }
            else { if (a.method === 'delete') window.__snapAny = await db.deleteMedia(a.id); else await db.restoreMedia(window.__snapAny); }
        } finally { proto[a.method] = orig; }
        const res = await row;
        const disk = await db.idbGet(a.store, a.id);
        const mem = a.mirror ? !!db.state[a.mirror].get(a.id) : null;
        const tomb = (await db.listTombstones()).some(t => t.recordId === a.id);
        const ops = (await db.listOps()).filter(o => o.recordId === a.id && o.seq > (db.state.settings.lastAckedSeq || 0));
        return { fired, row: res && { applied: res.applied, skipped: res.skipped }, disk: !!disk, bytes: !!(disk && disk.blob), mem, tomb,
                 ops: ops.map(o => ({ op: o.op, origin: o.origin, superseded: !!o.superseded })) };
    }"""
    def window_pair(label, writer, store, mirror, rid, del_mutant, undo_mutant):
        a = {'id': rid, 'store': store, 'mirror': mirror, 'writer': writer}
        put_echo = echo_of(rid, 101)
        w = run(page, HOOKED_ANY, dict(a, method='delete', echo=put_echo))
        check(f'[window · {label} · setup] the echoed row was issued from inside the delete, once', w['fired'] == 1 and w['row'] is not None, w)
        check(f'[window · {label} · delete · {del_mutant} fails here] a row applied behind the delete\'s first write does NOT put the record back'
              + (' — the store and memory both say deleted' if mirror else ' — the store says deleted'),
              w['disk'] is False and w['mem'] in (False, None) and w['row']['applied'] is False, w)
        check(f'[window · {label} · delete] the deletion is whole: its tombstone is there and its operation is owed, not superseded',
              w['tomb'] is True and any(o['op'] == 'delete' and not o['superseded'] for o in w['ops']), w)
        run(page, "async (db) => await db.pushOnce()")
        del_echo = echo_of(rid, 102)
        check(f'[window · {label} · setup] the deletion was pushed', del_echo['deleted'] is True, del_echo['deleted'])
        w = run(page, HOOKED_ANY, dict(a, method='put', echo=del_echo))
        check(f'[window · {label} · setup] the echoed deletion was issued from inside the undo, once', w['fired'] == 1 and w['row'] is not None, w)
        check(f'[window · {label} · undo · {undo_mutant} fails here] a deletion applied behind the undo\'s first write does NOT take the record away again'
              + (' — the store and memory both hold it' if mirror else ' — the store holds it, with its bytes'),
              w['disk'] is True and w['mem'] in (True, None) and (mirror or w['bytes'] is True) and w['row']['applied'] is False, w)
        check(f'[window · {label} · undo] the undo is whole: no tombstone is left and its operation is owed, not superseded',
              w['tomb'] is False and any(o['origin'] == 'restore' and not o['superseded'] for o in w['ops']), w)

    # the generic writer, through health events
    run(page, RESET); srv['pushed'].clear()
    h = run(page, """async (db) => {
        const bird = await db.saveBird(db.newBird({ name: 'صاحب الحدث', sex: 'hen' }));
        const ev = await db.Health.save({ eventType: 'check', wholeLoft: false, birdId: bird.id, date: '2026-11-01', medication: 'فحص', notes: '' });
        const push = await db.pushOnce(); return { id: ev.id, pushOk: push.ok };
    }""")
    check('[window · generic · setup] a health event was saved and pushed', h['pushOk'] is True, h)
    window_pair('generic', 'generic', 'healthEvents', 'healthEvents', h['id'], 'M-split-remove', 'M-split-restore')

    # the media writer — a photo that holds its bytes
    run(page, RESET); srv['pushed'].clear()
    m = run(page, """async (db) => {
        const bird = await db.saveBird(db.newBird({ name: 'صاحب الصورة', sex: 'cock' }));
        const md = await db.addMedia(bird.id, 'photo', 'body', 'w.png', new Blob([new Uint8Array(64)], { type: 'image/png' }));
        const push = await db.pushOnce(); return { id: md.id, pushOk: push.ok };
    }""")
    check('[window · media · setup] a photo was saved and its record pushed', m['pushOk'] is True, m)
    window_pair('media', 'media', 'media', None, m['id'], 'M-split-mdelete', 'M-split-mrestore')

    check('zero page errors overall', not errs, '; '.join(errs[:2]))
    NET.assert_empty(check)
    br.close()

print(f'\n{ok} passed, {fail} failed')
import sys; sys.exit(1 if fail else 0)
