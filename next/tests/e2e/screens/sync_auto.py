"""AUTOMATIC SYNC AND ITS LAWS (RULED 2026-11-13; ROOT-FINDINGS RF-19, RF-20).

  § THE RE-ENQUEUE LAW — the first-login enqueue runs once: a cycle that cannot reach the server does not re-log every
    record as new work.

One stub project whose behaviour the suite switches (accept · refuse 403 · unreachable), modelling the real table (owner
rows, one server_seq, the §4 trigger). Harness build, the net armed. Every shape is CONSTRUCTED.

    python3 tests/e2e/screens/sync_auto.py
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout   # noqa: F401

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET: armed beneath the stub, asserted at the end
NET = Net()
PAGES = []

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

STUB = 'https://stub.example.test'

class Server:
    """sync_records as docs/SYNC-DESIGN.md §1 describes it, with a switch: 'ok' · 'refuse' (HTTP 403 on every push) · 'down' (every request aborted)."""
    def __init__(self): self.rows = {}; self.seq = 0; self.mode = 'ok'; self.log = []
    def upsert(self, o, r):
        key = (o, r['store'], r['record_id']); old = self.rows.get(key); row = dict(r)
        if old is not None and (row['updated_at'], str(row.get('device_id') or '')) <= (old['updated_at'], str(old.get('device_id') or '')): row = dict(old)
        self.seq += 1; row['server_seq'] = self.seq; row['owner'] = o; self.rows[key] = row; return row
    def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
    def live(self, o, store='birds'): return sorted((r['data'].get('name') or r['record_id']) for (w, s, _), r in self.rows.items() if w == o and s == store and not r['deleted'])
    def count(self, o): return sum(1 for (w, _, _) in self.rows if w == o)
    def calls(self, kind, since=0): return [e for e in self.log[since:] if e[0] == kind]
def make_handler(srv):
    def handler(route, request):
        if '/auth/v1/token' in request.url:
            body = json.loads(request.post_data or '{}'); who = (body.get('email') or 'a@').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
            srv.log.append(('TOKEN', who))
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}})); return
        who = 'user-' + (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
        kind = 'POST' if request.method == 'POST' else 'GET'
        if srv.mode == 'down': srv.log.append((kind + '-ABORTED', who)); route.abort(); return
        if kind == 'POST':
            rows = json.loads(request.post_data or '[]'); srv.log.append(('POST', who, len(rows)))
            if srv.mode == 'refuse': route.fulfill(status=403, content_type='application/json', body='{"message":"the stub refuses every push"}'); return
            route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in rows])); return
        c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); srv.log.append(('GET', who, c))
        route.fulfill(status=200, content_type='application/json', body=json.dumps(srv.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))))
    return handler

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s or '')
BOOK = """async (db) => { const S = Object.fromEntries((await db.idbGetAll('settings')).map(r => [r.key, r.value])); const ops = await db.idbGetAll('oplog');
  const acked = S.lastAckedSeq || 0; return { oplog: ops.length, pending: ops.filter(o => o.seq > acked && !o.superseded).length, lastSyncAt: S.lastSyncAt || null, acked,
    firstEnqueueSeq: S.firstEnqueueSeq === undefined ? null : S.firstEnqueueSeq, err: S.lastSyncError ? S.lastSyncError.key : null, birds: db.state.birds.size }; }"""
def book(pg): return run(pg, BOOK)
SHAPE13 = """async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت القياس' }); const ids = [];
  for (let i = 1; i <= 10; i++) ids.push((await db.saveBird(db.newBird({ name: 'طير-' + i, sex: i % 2 ? 'cock' : 'hen' }))).id);
  await db.Pairs.save({ sireId: ids[0], damId: ids[1], season: 2026, status: 'active', rounds: [] }); await db.Health.save({ birdId: ids[2], date: '2026-10-01', kind: 'vaccination', note: 'قياس' }); }"""

def device(b, H, srv, email='a@zajil.test', sign_in=True, extra_init=''):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
    ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};" + extra_init); ctx.route(f'{STUB}/**', make_handler(srv))
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady')
    if sign_in: run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email)
    return ctx, pg

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ § THE RE-ENQUEUE LAW — 13 records, a server that refuses every push and has nothing to pull ═══
        srv = Server(); srv.mode = 'refuse'; c1, pg = device(b, H, srv); run(pg, SHAPE13)
        before = book(pg); counts = []
        for _ in range(5):
            run(pg, "async (db) => { await db.syncNow(); }"); counts.append(book(pg)['oplog'])
        after = book(pg)
        check('[law] the first cycle enqueues every record once — 13 ops for 13 records', counts[0] == before['oplog'] + 13, (before['oplog'], counts))
        check('[law · L1 fails here] FOUR MORE FAILED CYCLES LEAVE THE OP COUNT FLAT', counts[1:] == [counts[0]] * 4, counts)
        check('[law] the device knows it has not synced, and why', after['lastSyncAt'] is None and after['err'] == 'sync.err.rejected' and isinstance(after['firstEnqueueSeq'], int), after)
        srv.mode = 'ok'; run(pg, "async (db) => { await db.syncNow(); }"); ok = book(pg)
        check('[law] when the server takes them, the once-enqueued ops carry every record up: 13 rows, nothing pending', srv.count('user-A') == 13 and ok['pending'] == 0 and ok['oplog'] == counts[0], (srv.count('user-A'), ok))
        # the setting describes ONE account's data: the collision CLEAR removes it, so the next account's first login enqueues afresh
        cleared = run(pg, """async (db) => { await db.signOut(); await db.signIn('b@zajil.test', 'pw', { replaceLocalData: true });
            const S = Object.fromEntries((await db.idbGetAll('settings')).map(r => [r.key, r.value])); return S.firstEnqueueSeq === undefined; }""")
        check('[law] the collision CLEAR removes the mark with the data it described', cleared is True, cleared)
        c1.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
