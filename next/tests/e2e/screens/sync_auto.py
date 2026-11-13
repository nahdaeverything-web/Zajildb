"""AUTOMATIC SYNC AND ITS LAWS (RULED 2026-11-13; ROOT-FINDINGS RF-19, RF-20).

  § THE RE-ENQUEUE LAW — the first-login enqueue runs once: a cycle that cannot reach the server does not re-log every
    record as new work.
  § THE COORDINATOR — one owner for every trigger: the app opening, a change (debounced 3 s), online, foreground,
    background, the heartbeat, the button. Single flight. 60 s while unsent or failing, backing off to a 15-minute cap
    that the online event resets; 5 minutes idle; nothing while backgrounded or signed out.

One stub project whose behaviour the suite switches (accept · refuse 403 · unreachable), modelling the real table (owner
rows, one server_seq, the §4 trigger). Harness build, the net armed. Every shape is CONSTRUCTED.

    python3 tests/e2e/screens/sync_auto.py
"""
import json
import os
import re
import sys
import time

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
    def __init__(self): self.rows = {}; self.seq = 0; self.mode = 'ok'; self.log = []; self.delay = 0
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
        if srv.delay: time.sleep(srv.delay)          # a slow server, so that requests made 'at once' really overlap a cycle
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

LOOP = "(db) => db.syncLoopState()"
SYNC = "async (db) => { await db.syncNow(); }"
def wait_until(pg, cond, seconds):
    """poll a Python-side condition while the page keeps running; bounded, non-raising"""
    for _ in range(int(seconds * 5)):
        if cond(): return True
        pg.wait_for_timeout(200)
    return bool(cond())
def settle(pg, seconds=10):
    """until no cycle is in flight or queued; bounded, non-raising"""
    for _ in range(int(seconds * 5)):
        st = run(pg, LOOP)
        if not st['inFlight'] and not st['queued'] and not st['debouncing']: return st
        pg.wait_for_timeout(200)
    return run(pg, LOOP)
def set_visibility(pg, value):
    pg.evaluate("(v) => { Object.defineProperty(document, 'visibilityState', { value: v, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }", value)
def birds(pg): return run(pg, "(db) => [...db.state.birds.values()].map(b => b.name).sort()")

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

        # ═══ § THE COORDINATOR ═══
        srv = Server(); c2, pg = device(b, H, srv); run(pg, "async (db) => { await db.saveBird(db.newBird({ name: 'قبل', sex: 'cock' })); await db.syncNow(); }"); settle(pg)

        # OPEN — a reload with a session on the device: a cycle, and nobody pressed anything
        mark = len(srv.log); pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); wait_until(pg, lambda: srv.calls('GET', mark), 8); st = settle(pg)
        check('[open · O1 fails here] the app opening runs a cycle with no press — a pull within 8 s of boot', len(srv.calls('GET', mark)) >= 1, srv.log[mark:])
        check('[open] the coordinator is on and waiting the IDLE interval: 5 minutes, nothing unsent', st['on'] and st['timerArmed'] and st['nextBaseMs'] == 300000 and st['failures'] == 0, st)

        # A CHANGE, debounced — three edits in a burst are ONE push, three seconds after the last, no press
        mark = len(srv.log); run(pg, "async (db) => { for (const n of ['ت1', 'ت2', 'ت3']) await db.saveBird(db.newBird({ name: n, sex: 'hen' })); }")
        pg.wait_for_timeout(1500); early = len(srv.calls('POST', mark))
        wait_until(pg, lambda: srv.calls('POST', mark), 8); pg.wait_for_timeout(1200); settle(pg); posts = srv.calls('POST', mark)
        check('[change] nothing is sent inside the 3-second debounce', early == 0, early)
        check('[change · C1 fails here] the burst is ONE push of the three birds, with no press', len(posts) == 1 and posts[0][2] == 3 and all(n in srv.live('user-A') for n in ('ت1', 'ت2', 'ت3')), (posts, srv.live('user-A')))

        # SINGLE FLIGHT — four requests at once against a slow server: the cycle in flight and ONE follow-up
        srv.delay = 0.4; mark = len(srv.log)
        r = run(pg, "async (db) => { const rs = await Promise.all([db.syncNow(), db.syncNow(), db.syncNow(), db.runSyncCycle()]); return rs.map(x => Boolean(x && x.ok)); }")
        srv.delay = 0; settle(pg); gets = len(srv.calls('GET', mark))
        check('[single flight · F1 fails here] four requests at once make TWO cycles — the one in flight and one follow-up — and every caller is answered', gets == 2 and r == [True] * 4, (gets, r))

        # THE HEARTBEAT WHILE FAILING — one minute, doubling, capped at a quarter of an hour; the online event resets it
        srv.mode = 'down'; bases = []
        for _ in range(7):
            run(pg, "async (db) => { await db.runSyncCycle(); }"); bases.append(run(pg, LOOP)['nextBaseMs'])
        check('[backoff] failing: 60 s, then 2, 4, 8 minutes, then the cap, and it stays there', bases == [60000, 120000, 240000, 480000, 900000, 900000, 900000], bases)
        top = run(pg, "(db) => { const s = Array.from({ length: 400 }, () => db.backoffDelay(9)); return { min: Math.min(...s), max: Math.max(...s), cap: db.BACKOFF_CAP_MS }; }")
        check('[backoff · B1 fails here] THE CAP IS A CAP: 400 delays drawn at the top of the curve, none above 15 minutes', top['cap'] == 900000 and top['max'] <= 900000 and top['min'] >= 675000, top)
        pg.evaluate("() => window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(600); st = settle(pg)
        check('[backoff · B2 fails here] THE ONLINE EVENT RESETS IT: the cycle it starts fails again, and the wait is back to 60 s', st['failures'] == 1 and st['nextBaseMs'] == 60000, st)
        srv.mode = 'ok'; run(pg, SYNC); st = settle(pg)
        check('[backoff] a success clears the failures; idle again', st['failures'] == 0 and st['nextBaseMs'] == 300000, st)

        # SIGN-OUT — the coordinator has nothing to wait for
        before = run(pg, LOOP); run(pg, "async (db) => { await db.signOut(); }"); after = run(pg, LOOP)
        check('[sign-out · S1 fails here] the loop stops with the session: a timer was armed, and none is after sign-out', before['timerArmed'] and not after['timerArmed'] and after['on'], (before, after))
        c2.close()

        # REAL TIMERS, driven: the idle heartbeat fires; the background stops it; the foreground restarts it
        srv = Server(); ctx3 = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
        ctx3.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx3.route(f'{STUB}/**', make_handler(srv))
        tp = ctx3.new_page(); tp.errs = []; tp.on('pageerror', lambda e: tp.errs.append(str(e))); PAGES.append(tp); tp.clock.install()
        tp.goto(H, wait_until='load'); tp.wait_for_function('window.__zajilReady'); run(tp, "async (db) => { await db.signIn('a@zajil.test', 'pw'); await db.syncNow(); }"); settle(tp)
        mark = len(srv.log); tp.clock.fast_forward(299000); tp.wait_for_timeout(600); quiet = len(srv.calls('GET', mark))
        tp.clock.fast_forward(2000); wait_until(tp, lambda: srv.calls('GET', mark), 5); settle(tp)
        check('[heartbeat] idle: nothing for 4 min 59 s, then a pull at 5 minutes — with no press', quiet == 0 and len(srv.calls('GET', mark)) == 1, (quiet, srv.log[mark:]))
        run(tp, "async (db) => { await db.saveBird(db.newBird({ name: 'قبل-الخلفية', sex: 'cock' })); }")       # unsent work, inside the debounce
        mark = len(srv.log); set_visibility(tp, 'hidden'); wait_until(tp, lambda: srv.calls('POST', mark), 5); st = settle(tp)
        check('[background] going to the background sends what is unsent at once, without waiting for the debounce', len(srv.calls('POST', mark)) == 1 and 'قبل-الخلفية' in srv.live('user-A'), srv.log[mark:])
        mark = len(srv.log); tp.clock.fast_forward(3600000); tp.wait_for_timeout(800); st = run(tp, LOOP)
        check('[background · G1 fails here] AN HOUR IN THE BACKGROUND: no timer armed and not one request', not st['timerArmed'] and len(srv.log) == mark, (st, srv.log[mark:]))
        set_visibility(tp, 'visible'); wait_until(tp, lambda: srv.calls('GET', mark), 5); st = settle(tp)
        check('[foreground] coming back runs a cycle at once and re-arms the heartbeat', len(srv.calls('GET', mark)) == 1 and st['timerArmed'] and st['nextBaseMs'] == 300000, (srv.log[mark:], st))
        run(tp, "async (db) => { await db.signOut(); }"); mark = len(srv.log); tp.clock.fast_forward(3600000); tp.wait_for_timeout(800)
        check('[sign-out] an hour signed out: not one request', len(srv.log) == mark, srv.log[mark:])
        ctx3.close()

        # THE TEST-ONLY SWITCH (harness builds only; the postbuild guard fails a normal build that carries it)
        srv = Server(); c4, off = device(b, H, srv, extra_init='globalThis.__ZAJIL_TEST_NO_AUTOSYNC = true;'); mark = len(srv.log)
        run(off, "async (db) => { await db.saveBird(db.newBird({ name: 'بلا-منسّق', sex: 'cock' })); }"); off.wait_for_timeout(4500)
        check('[switch] with the harness-only switch the coordinator does not start: no cycle after a change', run(off, LOOP)['on'] is False and not srv.calls('POST', mark) and not srv.calls('GET', mark), (run(off, LOOP), srv.log[mark:]))
        c4.close()

        # TWO DEVICES, NOBODY PRESSES ANYTHING — the acceptance shape, stub-backed
        srv = Server(); ca, A = device(b, H, srv); run(A, SYNC); cb, B = device(b, H, srv); run(B, SYNC); settle(A); settle(B)
        run(A, "async (db) => { await db.saveBird(db.newBird({ name: 'عابر', sex: 'cock' })); }")
        up = wait_until(A, lambda: 'عابر' in srv.live('user-A'), 8)
        check('[two devices] a bird made on A reaches the server by itself', up, srv.live('user-A'))
        set_visibility(B, 'visible'); got = wait_until(B, lambda: 'عابر' in birds(B), 8)                           # B is opened / brought forward
        check('[two devices] …and is on B as soon as B is brought forward — no press on either', got, birds(B))
        run(B, "async (db) => { const x = [...db.state.birds.values()].find(v => v.name === 'عابر'); if (x) await db.saveBird({ ...x, colour: 'عُدّل على ب' }); }")   # guarded: a bird that never arrived fails the check above, not a traceback here
        wait_until(B, lambda: any(r['data'].get('colour') == 'عُدّل على ب' for r in srv.rows.values()), 8)
        set_visibility(A, 'visible'); back = wait_until(A, lambda: run(A, "(db) => [...db.state.birds.values()].some(v => v.colour === 'عُدّل على ب')"), 8)
        check('[two devices] an edit on B is on A when A is brought forward', back, run(A, "(db) => [...db.state.birds.values()].map(v => [v.name, v.colour])"))
        ca.close(); cb.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
