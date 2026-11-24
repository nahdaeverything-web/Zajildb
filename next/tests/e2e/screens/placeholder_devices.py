#!/usr/bin/env python3
"""PLACEHOLDER PARENTS ACROSS DEVICES (C1, RULED 2026-11-24; src/db/records.js keepNamedPlaceholders, src/db/sync.js).

The rule: NO BIRD MAY BE LEFT NAMING A PLACEHOLDER THAT NO DEVICE HOLDS. Measured before it existed: device 2, offline,
gave a placeholder father a second child; device 1 cleared the first child's father, which left the placeholder with
no child THERE, so it was deleted (B4); after both synced the second child named a father no device held.

Now a deleted placeholder is kept in its tombstone, and after every pull a device puts back — the same record, the
same id, the flag set, with an operation so it is pushed — any placeholder that a bird it holds still names.

  both causes of the deletion     B4 (a parent changed or cleared) and item 6 (the last child deleted)
  both arrival orders             the deletion reaches the device whose bird names the placeholder (it puts it back
                                  from the copy it held); the bird reaches the device that deleted the placeholder
                                  (it puts it back from the record its own tombstone kept)
  the chain                       a placeholder that went with its own placeholder parent comes back with it
  convergence                     both devices hold the same records, integrity empty, no sync anomaly
  no ping-pong                    three more sync rounds on each device log no operation and send no row
  placeholders only               a fancier's deliberate deletion of an ordinary bird is never undone by this

A sync cycle runs only when the suite asks for one: the coordinator's own triggers (a change, coming online, the
heartbeat) are switched off with the harness's test-only switch, and only the device being driven is online. So the
order in which things arrive is the one each scenario names, and "in that cycle" means one cycle. Fixture names are
invented. The backend is a stub; THE NET is armed beneath it.

    python3 tests/e2e/screens/placeholder_devices.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import json, os, re, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net, no_bucket              # noqa: E402  THE NET (RULED 2026-10-08): armed beneath the stub, asserted at the end
NET = Net(); PAGES = []
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:560]) if not ok and d != '' else ''}")
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))

STUB = 'https://stub.example.test'
# ── the stub project: owner rows, one global server_seq, deletes as deleted=true (docs/SYNC-DESIGN.md §1) ──
class Server:
    def __init__(self): self.rows = {}; self.seq = 0; self.pushed = []
    def upsert(self, o, r): self.seq += 1; row = dict(r, server_seq=self.seq, owner=o); self.rows[(o, r['store'], r['record_id'])] = row; self.pushed.append((o, r['record_id'], bool(r['deleted']))); return row
    def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
    def row(self, o, rid): return self.rows.get((o, 'birds', rid))
    def ever_deleted(self, o, rid): return any(w == o and i == rid and d for (w, i, d) in self.pushed)
srv = Server()
def handler(route, request):
    if no_bucket(route, request): return          # this suite's project has no photo bucket (tests/e2e/_net.py)
    if '/auth/v1/token' in request.url:
        body = json.loads(request.post_data or '{}'); who = (body.get('email') or 'a@').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}})); return
    who = 'user-' + (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in rows])); return
    c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); rows = srv.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

# device 1's register: a placeholder father and his one child; with `chain`, the father's own placeholder mother too
SEED = """async (db, chain) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت الجهازين' }); const loftId = db.currentLoft().id;
    const q = chain ? (await db.saveBird(db.newBird({ name: 'أم غير معروفة', sex: 'hen', placeholder: true }))).id : null;
    const p = (await db.saveBird(db.newBird({ name: 'أب غير معروف', sex: 'cock', placeholder: true, damId: q }))).id;
    const c1 = (await db.saveBird(db.newBird({ name: 'الأول', sex: 'cock', loftId, sireId: p }))).id;
    return { p, q, c1 }; }"""
# device 1's register for the ordinary case: a reference bird a fancier recorded himself, and its one child
SEED_ORDINARY = """async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت الجهازين' }); const loftId = db.currentLoft().id;
    const p = (await db.saveBird(db.newBird({ name: 'فحل مرجعي', sex: 'cock', external: true }))).id;
    const c1 = (await db.saveBird(db.newBird({ name: 'الأول', sex: 'cock', loftId, sireId: p }))).id;
    return { p, q: null, c1 }; }"""
CAUSE = {  # what device 1 does, offline
    'B4': "async (db, ids) => { await db.saveBird({ ...db.getBird(ids.c1), sireId: null }); }",       # the first child's father cleared: the placeholder has no child left there
    'item 6': "async (db, ids) => { await db.deleteBird(ids.c1); }",                                    # the first child deleted: the placeholder goes with it
    'deliberate': "async (db, ids) => { await db.deleteBird(ids.p); }",                                # the fancier deletes the bird itself
}
STATE = """async (db, ids) => { const e = window.__zajilEngine; const out = {};
    for (const k of ['p', 'q']) { const id = ids[k]; if (!id) { out[k] = null; continue; } const b = db.getBird(id); const t = await db.idbGet('tombstones', 'birds:' + id);
      out[k] = b ? { here: true, flag: b.placeholder === true, id: b.id === id } : { here: false, tomb: !!t, kept: !!(t && t.kept), keptFlag: !!(t && t.kept && t.kept.placeholder === true), keptId: !!(t && t.kept && t.kept.id === id) }; }
    const c1 = db.getBird(ids.c1), c2 = ids.c2 ? db.getBird(ids.c2) : null;
    out.c1 = c1 ? { here: true, father: c1.sireId === ids.p ? 'p' : c1.sireId } : { here: false };
    out.c2 = c2 ? { here: true, father: c2.sireId === ids.p ? 'p' : c2.sireId } : { here: false };
    out.integrity = e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents, lofts: db.state.lofts }).map(x => x.key);
    out.anomalies = (await db.listSyncAnomalies()).length; out.ops = db.state.settings.opSeq || 0;
    out.birds = JSON.stringify(db.allBirds().slice().sort((a, b) => a.id.localeCompare(b.id)));
    return out; }"""
def sync(pg): run(pg, "async (db) => { await db.syncNow(); }"); pg.wait_for_timeout(150)

srvp, H = serve()
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        def device(email):
            """A configured device, signed in through the stub."""
            ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 390, 'height': 844}))
            ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }}; globalThis.__ZAJIL_TEST_NO_AUTOSYNC = true;"); ctx.route(f'{STUB}/**', handler)
            pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
            pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email); return ctx, pg
        def two(tag, seed, *args):
            """Two devices of one account that hold the same register; both end OFFLINE, device 2 with a second child of the father."""
            who = 'user-' + tag.upper()
            c1, d1 = device(f'{tag}@zajil.test'); ids = run(d1, seed, *args); sync(d1)
            c2, d2 = device(f'{tag}@zajil.test'); sync(d2)
            try: d2.wait_for_function("async (n) => (await window.__zajilDb).allBirds().length >= n", arg=3 if ids.get('q') else 2, timeout=15000)
            except Exception: pass
            c1.set_offline(True); c2.set_offline(True)
            ids['c2'] = run(d2, "async (db, pid) => (await db.saveBird(db.newBird({ name: 'الثاني', sex: 'hen', sireId: pid }))).id", ids['p'])
            return who, c1, d1, c2, d2, ids
        def one_cycle(ctx, pg):
            """This device alone goes online, runs one sync cycle, and goes offline again."""
            ctx.set_offline(False); sync(pg); ctx.set_offline(True)
        def rounds(c1, d1, c2, d2, n):
            c1.set_offline(False); c2.set_offline(False)
            for _ in range(n): sync(d1); sync(d2)

        def scenario(tag, cause, order, chain):
            who, c1, d1, c2, d2, ids = two(tag, SEED, chain)
            both = ['p', 'q'] if chain else ['p']
            run(d1, CAUSE[cause], ids); gone = run(d1, STATE, ids)
            what = 'the placeholder father and his own placeholder mother are' if chain else 'the placeholder father is'
            check(f'[C1 · {cause} · {order} · setup] offline, device 2 records a second child of the placeholder father and device 1 leaves him with no child: on device 1 {what} deleted, and each tombstone KEEPS the record, flag and id',
                  all(gone[k] == {'here': False, 'tomb': True, 'kept': True, 'keptFlag': True, 'keptId': True} for k in both), {k: gone[k] for k in both})
            if order == 'the deletion arrives':
                one_cycle(c1, d1)                                   # device 1 pushes the deletion
                deleted_on_server = bool(srv.row(who, ids['p']) and srv.row(who, ids['p'])['deleted'])
                one_cycle(c1, d1); echoed = run(d1, STATE, ids)     # …and, a cycle later, pulls its own rows back
                check(f'[C1 · {cause} · its own echo · M-c1-echo fails here] device 1 pulls back the deletion it pushed itself: its tombstone still keeps the record',
                      all(echoed[k] == {'here': False, 'tomb': True, 'kept': True, 'keptFlag': True, 'keptId': True} for k in both), {k: echoed[k] for k in both})
                one_cycle(c2, d2); seen = run(d2, STATE, ids); where = 'device 2'
                check(f'[C1 · {cause} · the deletion arrives · M-c1-x fails here] device 2 pulls the deletion of a placeholder its own bird names: in that same cycle it puts {"both records" if chain else "the record"} back — the same id, the flag set — and pushes {"them" if chain else "it"}',
                      deleted_on_server and all(seen[k] == {'here': True, 'flag': True, 'id': True} for k in both) and seen['c2'] == {'here': True, 'father': 'p'}
                      and all(srv.row(who, ids[k]) and srv.row(who, ids[k])['deleted'] is False for k in both), ({k: seen[k] for k in both}, deleted_on_server, [srv.row(who, ids[k]) and srv.row(who, ids[k])['deleted'] for k in both]))
            else:
                one_cycle(c2, d2)                                   # device 2 pushes the second child; the deletion has not been sent
                one_cycle(c1, d1); seen = run(d1, STATE, ids); where = 'device 1'
                check(f'[C1 · {cause} · the bird arrives · M-c1-y fails here] device 1 pulls a bird naming the placeholder it deleted: in that same cycle it puts {"both records" if chain else "the record"} back from what its tombstone kept — the same id, the flag set — and the deletion never reaches the server',
                      all(seen[k] == {'here': True, 'flag': True, 'id': True} for k in both) and seen['c2'] == {'here': True, 'father': 'p'}
                      and all(srv.row(who, ids[k]) and srv.row(who, ids[k])['deleted'] is False and not srv.ever_deleted(who, ids[k]) for k in both), ({k: seen[k] for k in both}, [srv.ever_deleted(who, ids[k]) for k in both]))
            if chain:
                check(f'[C1 · {cause} · {order} · the chain · M-c1-chain fails here] …the father\'s own placeholder mother came back in that same cycle on {where}, and he names her', seen['q'] == {'here': True, 'flag': True, 'id': True} and not seen['integrity'], (seen['q'], seen['integrity']))
            rounds(c1, d1, c2, d2, 2); s1 = run(d1, STATE, ids); s2 = run(d2, STATE, ids)
            first = {'here': True, 'father': None} if cause == 'B4' else {'here': False}
            check(f'[C1 · {cause} · {order} · convergence · M-c1-off fails here] after two rounds both devices hold THE SAME records: the placeholder with its flag, the second child naming it, the first child as device 1 left it',
                  s1['birds'] == s2['birds'] and all(s[k] == {'here': True, 'flag': True, 'id': True} for s in (s1, s2) for k in both) and all(s['c2'] == {'here': True, 'father': 'p'} and s['c1'] == first for s in (s1, s2)),
                  ({k: s1[k] for k in both + ['c1', 'c2']}, {k: s2[k] for k in both + ['c1', 'c2']}, s1['birds'] == s2['birds']))
            check(f'[C1 · {cause} · {order}] …no bird names a record that is not there, and no sync anomaly was recorded — on either device', s1['integrity'] == [] and s2['integrity'] == [] and s1['anomalies'] == 0 and s2['anomalies'] == 0, (s1['integrity'], s2['integrity'], s1['anomalies'], s2['anomalies']))
            before = (s1['ops'], s2['ops'], srv.seq); rounds(c1, d1, c2, d2, 3); q1 = run(d1, STATE, ids); q2 = run(d2, STATE, ids); after = (q1['ops'], q2['ops'], srv.seq)
            check(f'[C1 · {cause} · {order} · no ping-pong · M-c1-loop fails here] three more sync rounds on each device: no operation logged on either, no row sent, and the records are as they were',
                  after == before and q1['birds'] == s1['birds'] and q2['birds'] == s2['birds'], (before, after))
            c1.close(); c2.close()

        scenario('a', 'B4', 'the deletion arrives', False)
        scenario('b', 'B4', 'the bird arrives', False)
        scenario('c', 'item 6', 'the deletion arrives', True)
        scenario('d', 'item 6', 'the bird arrives', True)

        # ══ PLACEHOLDERS ONLY: a fancier's deliberate deletion of an ordinary bird is not undone ══
        for tag, order in (('e', 'the deletion arrives'), ('f', 'the bird arrives')):
            who, c1, d1, c2, d2, ids = two(tag, SEED_ORDINARY)
            run(d1, CAUSE['deliberate'], ids); gone = run(d1, STATE, ids)
            check(f'[C1 · placeholders only · {order} · M-c1-all fails here] device 1 deletes an ORDINARY reference bird that device 2, offline, has given a second child: its tombstone keeps NO record',
                  gone['p'] == {'here': False, 'tomb': True, 'kept': False, 'keptFlag': False, 'keptId': False}, gone['p'])
            if order == 'the deletion arrives': one_cycle(c1, d1); one_cycle(c2, d2)
            else: one_cycle(c2, d2); one_cycle(c1, d1)
            rounds(c1, d1, c2, d2, 2); s1 = run(d1, STATE, ids); s2 = run(d2, STATE, ids)
            check(f'[C1 · placeholders only · {order}] …and after both have synced the bird is still deleted on both devices, with no record kept: the deletion was not undone (the second child names a bird that is gone, as it did before this rule)',
                  all(s['p'] == {'here': False, 'tomb': True, 'kept': False, 'keptFlag': False, 'keptId': False} for s in (s1, s2)) and bool(srv.row(who, ids['p'])) and srv.row(who, ids['p'])['deleted'] is True and s1['birds'] == s2['birds'], (s1['p'], s2['p'], srv.row(who, ids['p']) and srv.row(who, ids['p'])['deleted']))
            c1.close(); c2.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(pg.errs for pg in PAGES), [e[:160] for pg in PAGES for e in pg.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
