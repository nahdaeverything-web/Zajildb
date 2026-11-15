"""AUTOMATIC SYNC AND ITS LAWS (RULED 2026-11-13; ROOT-FINDINGS RF-19, RF-20).

  § THE RE-ENQUEUE LAW — the first-login enqueue runs once: a cycle that cannot reach the server does not re-log every
    record as new work.
  § THE COORDINATOR — one owner for every trigger: the app opening, a change (debounced 3 s), online, foreground,
    background, the heartbeat, the button. Single flight. 60 s while unsent or failing, backing off to a 15-minute cap
    that the online event resets; 5 minutes idle; nothing while backgrounded or signed out.
  § HONEST STATUS — «متزامن» only when nothing is unsent, no error, online; unknown until the op log is counted after a
    load; unsent work in a fancier's words, no count; the destructive questions warn; every new string typography-scanned.
  § THE FORM — a record that changed underneath an open form asks before saving: save anyway, or reload. No merge.

One stub project whose behaviour the suite switches (accept · refuse 403 · unreachable), modelling the real table (owner
rows, one server_seq, the §4 trigger). Harness build, the net armed. Every shape is CONSTRUCTED.

    python3 tests/e2e/screens/sync_auto.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12: a page error is recorded with its stack, address, device and step
import datetime
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
from _typography import SCAN                  # noqa: E402
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
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
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

UNSENT = 'تغييراتك محفوظة على هذا الجهاز ولم تُرسل بعد'
STATUS = """async (db) => { const S = Object.fromEntries((await db.idbGetAll('settings')).map(r => [r.key, r.value])); const ops = await db.idbGetAll('oplog');
  return { state: db.syncStatus().state, pendingInLog: ops.filter(o => o.seq > (S.lastAckedSeq || 0) && !o.superseded).length }; }"""
# installed before any app script: every text the tools sync row's value ever holds, in order
SEEN = """window.__seen = []; new MutationObserver(() => { const el = document.querySelector('[data-row=sync] [data-testid=row-value]'); if (!el) return;
  const v = el.textContent; if (window.__seen[window.__seen.length - 1] !== v) window.__seen.push(v); }).observe(document, { subtree: true, childList: true, characterData: true });"""
def open_row(pg, row):
    r = pg.locator(f'[data-row={row}]')
    if r.get_attribute('open') is None: r.locator('summary').click(); pg.wait_for_timeout(300)
def tools_row(pg, ROOT, goto=True):
    if goto: pg.goto(ROOT + 'tools/', wait_until='load'); pg.wait_for_selector('[data-testid=tools-list]', timeout=15000); pg.wait_for_timeout(1200); settle(pg)
    r = pg.locator('[data-row=sync]'); return r.locator('[data-testid=row-value]').inner_text().strip(), r.locator('[data-testid=row-help]').inner_text().strip()
def row_text(pg, ROOT):
    pg.goto(ROOT + 'birds/', wait_until='load'); pg.wait_for_selector('[data-testid=count-line]', timeout=15000); pg.wait_for_timeout(1200); settle(pg)
    return pg.locator('[data-testid=sync-row]').inner_text().strip() if pg.locator('[data-testid=sync-row]').count() else ''
FILE1 = {'format': 'zajil-export', 'version': 1, 'exportedAt': '2026-11-01T00:00:00.000Z', 'tombstones': [], 'pairs': [], 'raceResults': [], 'healthEvents': [], 'media': [], 'lofts': [],
         'birds': [{'id': 'status-file-1', 'name': 'من-ملف', 'sex': 'cock', 'rings': [], 'status': 'stock', 'loftId': None, 'notes': [], 'updatedAt': '2026-11-01T00:00:00.000Z', 'createdAt': '2026-11-01T00:00:00.000Z'}]}
def replace_question(pg, ROOT, confirm=False):
    """the replace-import's question, read and (by default) cancelled; '' if none appeared"""
    f = dict(FILE1, lofts=run(pg, "(db) => [...db.state.lofts.values()]"))                 # the device's own lofts stay, so the question is about birds only
    pg.goto(ROOT + 'tools/import/', wait_until='load'); pg.wait_for_selector('[data-testid=import-mode]', timeout=15000); pg.click('[data-testid=import-mode] [data-value=replace]')
    pg.set_input_files('[data-testid=file-input]', files=[{'name': 'f.json', 'mimeType': 'application/json', 'buffer': json.dumps(f).encode()}]); pg.click('[data-testid=import-file]')
    try: pg.wait_for_selector('[data-testid=dialog]', timeout=8000)
    except PWTimeout: return ''
    text = pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' '); pg.click('[data-testid=dialog-confirm]' if confirm else '[data-testid=dialog-cancel]'); pg.wait_for_timeout(2500 if confirm else 400)
    return text

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
        tp = ctx3.new_page(); tp.errs = []; tp.on('pageerror', lambda e, _p=tp: tp.errs.append(perr(e, _p))); PAGES.append(tp); tp.clock.install()
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

        # ═══ § HONEST STATUS — «متزامن» means synced; unsent work is said in words, never as a count; it survives a reload ═══
        srv = Server(); ctx5 = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
        ctx5.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};" + SEEN); ctx5.route(f'{STUB}/**', make_handler(srv))
        hs = ctx5.new_page(); hs.errs = []; hs.on('pageerror', lambda e, _p=hs: hs.errs.append(perr(e, _p))); PAGES.append(hs)
        hs.goto(H, wait_until='load'); hs.wait_for_function('window.__zajilReady'); run(hs, "async (db) => { await db.signIn('a@zajil.test', 'pw'); await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت الحالة' }); await db.syncNow(); }"); settle(hs)
        v, h = tools_row(hs, ROOT)
        check('[status] synced: the tools row says «متزامن» with the last successful sync, and the list row is silent', v == 'متزامن' and 'آخر مزامنة ناجحة' in h and row_text(hs, ROOT) == '', (v, h))
        text = replace_question(hs, ROOT)
        check('[confirm] with nothing unsent, a destructive question carries no unsent warning', text != '' and 'لم تُرسل بعد' not in text, text[:200])

        # RELOAD WITH A CHANGE THAT NO CYCLE HAS YET ATTEMPTED — so there is no failure on record for the status to answer
        # from, and the FIRST thing drawn after boot is the test. (TF-11: with a refused cycle already recorded this check
        # could not fail — mutant H1 survived it.) Everything the tools row ever displays is recorded by an observer installed
        # before the app's own scripts.
        srv.mode = 'refuse'; run(hs, "async (db) => { await db.saveBird(db.newBird({ name: 'قبل-إعادة-التحميل', sex: 'hen' })); }")
        hs.goto(ROOT + 'tools/', wait_until='load'); hs.wait_for_selector('[data-testid=tools-list]'); hs.wait_for_timeout(2500); settle(hs)
        seen0 = hs.evaluate("() => window.__seen"); sr = run(hs, STATUS)
        check('[invariant · H1 fails here] IT SURVIVES A RELOAD: from the first frame after boot the tools row never displays «متزامن» while a change is unsent', 'متزامن' not in seen0 and sr['pendingInLog'] >= 1 and len(seen0) >= 1, (seen0, sr))

        hs.goto(ROOT + 'birds/', wait_until='load'); hs.wait_for_selector('[data-testid=count-line]'); settle(hs)
        run(hs, "async (db) => { await db.saveBird(db.newBird({ name: 'غير-مرسل', sex: 'cock' })); }")
        s0 = run(hs, STATUS)
        check('[invariant] with unsent changes on the device the status is «unsent»', s0['pendingInLog'] >= 2 and s0['state'] == 'pending', s0)
        hs.wait_for_timeout(600); row = hs.locator('[data-testid=sync-row]').inner_text().strip() if hs.locator('[data-testid=sync-row]').count() else ''
        check('[status] the row says it in a fancier\'s words, with since-when', UNSENT in row and 'منذ' in row, row)
        check('[status] …and carries NO count of operations', not re.search(r'[0-9٠-٩]+\s*(تغيير|معلّق)', row) and 'بانتظار المزامنة' not in row, row)
        hs.wait_for_timeout(4500); settle(hs); s1 = run(hs, STATUS)                           # the debounced cycle ran and was refused
        check('[invariant] after a refused cycle: still unsent, never synced', s1['pendingInLog'] >= 1 and s1['state'] == 'pending', s1)

        # RELOAD — everything the tools row ever displays is recorded by an observer installed before the app's own scripts
        hs.goto(ROOT + 'tools/', wait_until='load'); hs.wait_for_selector('[data-testid=tools-list]'); hs.wait_for_timeout(2500); settle(hs)
        seen = hs.evaluate("() => window.__seen"); v, h = tools_row(hs, ROOT, goto=False); s2 = run(hs, STATUS)
        check('[invariant] …and again after a refused cycle and another reload', 'متزامن' not in seen and s2['pendingInLog'] >= 1, (seen, s2))
        check('[status] …and settles on «لم تُرسل بعد»', v == 'لم تُرسل بعد', (v, seen))
        check('[status] the list row says unsent after the reload too', UNSENT in row_text(hs, ROOT), row_text(hs, ROOT))
        hs.goto(ROOT + 'tools/sync/', wait_until='load'); hs.wait_for_selector('[data-testid=sync-detail]'); hs.wait_for_timeout(800); body = hs.locator('[data-testid=card-sync]').inner_text().replace('\n', ' ')
        check('[status] the sync screen says the same words and shows no number: the op count is gone from the app', UNSENT in body and hs.locator('[data-testid=sync-pending]').count() == 0 and not re.search(r'بانتظار المزامنة\s*:?\s*[0-9٠-٩]', body), body[:200])
        typo = hs.evaluate(SCAN)

        # THE DESTRUCTIVE QUESTIONS say so when this device holds unsent changes: replace · restore · the example removal · the clear
        text = replace_question(hs, ROOT, confirm=True)                                       # confirmed: it also leaves the snapshot the restore needs
        check('[confirm · H3 fails here] REPLACE warns that changes on this device are unsent', 'لم تُرسل بعد إلى أجهزتك الأخرى' in text, text[:300])
        hs.goto(ROOT + 'tools/restore/', wait_until='load'); hs.wait_for_selector('[data-testid=snap-list]'); hs.click('[data-testid=snap-row] [data-testid=snap-restore]'); hs.wait_for_selector('[data-testid=dialog]')
        text = hs.locator('[data-testid=dialog]').inner_text().replace('\n', ' '); typo += hs.evaluate(SCAN); hs.click('[data-testid=dialog-cancel]')
        check('[confirm · H3 fails here] RESTORE warns', 'لم تُرسل بعد إلى أجهزتك الأخرى' in text, text[:300])
        hs.goto(ROOT + 'tools/', wait_until='load'); hs.wait_for_selector('[data-testid=tools-list]'); hs.wait_for_timeout(600); open_row(hs, 'teaching'); hs.click('[data-testid=load-large]'); hs.wait_for_timeout(4000)
        hs.goto(ROOT + 'tools/', wait_until='load'); hs.wait_for_selector('[data-row=example-remove]'); open_row(hs, 'example-remove'); hs.click('[data-testid=example-remove]'); hs.wait_for_selector('[data-testid=dialog]')
        text = hs.locator('[data-testid=dialog]').inner_text().replace('\n', ' '); hs.click('[data-testid=dialog-cancel]')
        check('[confirm · H3 fails here] THE EXAMPLE REMOVAL warns', 'لم تُرسل بعد إلى أجهزتك الأخرى' in text, text[-200:])

        # OFFLINE is its own calm words, and still never «synced»
        srv.mode = 'down'; run(hs, SYNC); settle(hs); s3 = run(hs, STATUS); row = row_text(hs, ROOT)
        check('[status] unreachable: «دون اتصال — تغييراتك محفوظة وستُرسل عند عودة الاتصال», and not synced', s3['state'] == 'offline' and row.endswith('دون اتصال — تغييراتك محفوظة وستُرسل عند عودة الاتصال'), (s3, row))
        typo += hs.evaluate(SCAN)

        # THE CLEAR: signed out, another account signs in — the second question says the unsent changes will be lost
        srv.mode = 'ok'
        hs.goto(ROOT + 'tools/', wait_until='load'); hs.wait_for_selector('[data-testid=tools-list]'); hs.wait_for_timeout(600)
        run(hs, "async (db) => { await db.saveBird(db.newBird({ name: 'قبل-الخروج', sex: 'hen' })); }"); open_row(hs, 'account'); hs.click('[data-testid=sign-out]'); hs.wait_for_selector('[data-testid=dialog]'); hs.click('[data-testid=dialog-confirm]')
        hs.wait_for_selector('[data-testid=signin-form]', timeout=10000); hs.fill('[data-testid=f-email]', 'b@zajil.test'); hs.fill('[data-testid=f-password]', 'pw'); hs.click('[data-testid=signin-submit]')
        hs.wait_for_selector('[data-testid=dialog]', timeout=10000); hs.click('[data-testid=dialog-confirm]'); hs.wait_for_timeout(500); hs.wait_for_selector('[data-testid=dialog]')
        text = hs.locator('[data-testid=dialog]').inner_text().replace('\n', ' '); typo += hs.evaluate(SCAN); hs.click('[data-testid=dialog-cancel]'); hs.wait_for_timeout(400)
        if hs.locator('[data-testid=dialog]').count(): hs.click('[data-testid=dialog-cancel]')
        check('[confirm · H3 fails here] THE CLEAR warns that the unsent changes will be LOST', 'لم تُرسل بعد، وستضيع بالمسح' in text, text[:300])
        check('[typography] every new string, where it is drawn — the row, the tools row, the sync screen, the questions — is in a face that has Arabic, and unspaced', not typo, [(x['why'], x['text']) for x in typo][:3])
        ctx5.close()

        # back to synced, on a fresh device: the words go away
        srv = Server(); c6, ok = device(b, H, srv); run(ok, "async (db) => { await db.saveBird(db.newBird({ name: 'يُرسل', sex: 'cock' })); await db.syncNow(); }"); settle(ok); s4 = run(ok, STATUS); v, h = tools_row(ok, ROOT)
        check('[status] once everything is sent: nothing pending in the log, state synced, «متزامن», the list row silent', s4 == {'state': 'synced', 'pendingInLog': 0} and v == 'متزامن' and row_text(ok, ROOT) == '', (s4, v))

        # on a device that IS synced: the moment a change is made, before the debounce and before any cycle, the status says unsent
        run(ok, "async (db) => { await db.saveBird(db.newBird({ name: 'لحظة', sex: 'hen' })); }"); s5 = run(ok, STATUS)
        check('[invariant · H2 fails here] THE MOMENT A CHANGE IS MADE the status is «unsent», never «synced»', s5 == {'state': 'pending', 'pendingInLog': 1}, s5)
        ok.wait_for_timeout(4500); settle(ok)

        # ═══ § THE FORM — a record that changed underneath an open form ═══
        bid = run(ok, "async (db) => { const x = await db.saveBird(db.newBird({ name: 'نموذج', sex: 'cock' })); await db.syncNow(); return x.id; }"); settle(ok)
        def remote_edit(name):
            """another device's edit, landed on the server now; then this device pulls it while its form is open"""
            rec = run(ok, "(db, id) => db.getBird(id)", bid); at = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % 0
            srv.upsert('user-A', {'store': 'birds', 'record_id': bid, 'data': dict(rec, name=name, updatedAt=at, deviceId='00000000-0000-4000-8000-00000000000b'), 'deleted': False, 'updated_at': at, 'device_id': '00000000-0000-4000-8000-00000000000b', 'op_seq': 1})
            run(ok, SYNC); settle(ok)
        def open_form():
            ok.goto(ROOT + 'bird/edit/?id=' + bid, wait_until='load'); ok.wait_for_selector('[data-testid=f-name]'); ok.wait_for_timeout(500)
        open_form(); ok.fill('[data-testid=f-name]', 'بلا-تعارض'); ok.click('[data-testid=save-btn]'); ok.wait_for_timeout(1500)
        check('[form] nothing changed underneath: the save goes through with no question', ok.locator('[data-testid=dialog]').count() == 0 and run(ok, "(db, id) => db.getBird(id).name", bid) == 'بلا-تعارض', run(ok, "(db, id) => db.getBird(id).name", bid))
        run(ok, SYNC); settle(ok); open_form(); ok.wait_for_timeout(1100); remote_edit('عُدّل-على-جهاز-آخر')
        ok.fill('[data-testid=f-name]', 'محلي'); ok.click('[data-testid=save-btn]'); ok.wait_for_timeout(800)
        asked = ok.locator('[data-testid=dialog]').count() == 1; text = ok.locator('[data-testid=dialog]').inner_text().replace('\n', ' ') if asked else ''; typo2 = ok.evaluate(SCAN) if asked else []
        check('[form · W1 fails here] THE RECORD CHANGED ON ANOTHER DEVICE WHILE THE FORM WAS OPEN: saving asks first', asked and 'تغيّر هذا السجل على جهاز آخر' in text and 'حفظ رغم التحذير' in text and 'أعد التحميل' in text, text[:260])
        check('[form] …and until answered nothing is overwritten', run(ok, "(db, id) => db.getBird(id).name", bid) == 'عُدّل-على-جهاز-آخر', run(ok, "(db, id) => db.getBird(id).name", bid))
        if asked: ok.click('[data-testid=dialog-alt]'); ok.wait_for_timeout(600)
        fname = lambda: ok.input_value('[data-testid=f-name]') if ok.locator('[data-testid=f-name]').count() else '(the form is gone)'   # non-raising: a form that saved and left fails the checks, not the suite
        check('[form] «أعد التحميل» puts the other device\'s version in the form, and still nothing was overwritten', fname() == 'عُدّل-على-جهاز-آخر' and ok.locator('[data-testid=dialog]').count() == 0, fname())
        if not ok.locator('[data-testid=f-name]').count(): open_form()
        ok.wait_for_timeout(1100); remote_edit('تعديل-ثانٍ'); ok.fill('[data-testid=f-name]', 'محلي-يُحفظ'); ok.click('[data-testid=save-btn]'); ok.wait_for_timeout(800)
        asked2 = ok.locator('[data-testid=dialog]').count() == 1
        if ok.locator('[data-testid=dialog]').count(): ok.click('[data-testid=dialog-confirm]')
        ok.wait_for_timeout(1500)
        check('[form] «حفظ رغم التحذير» saves the form\'s version — asked, answered, done', asked2 and run(ok, "(db, id) => db.getBird(id).name", bid) == 'محلي-يُحفظ', run(ok, "(db, id) => db.getBird(id).name", bid))
        check('[typography] the form\'s question is drawn in a face that has Arabic', not typo2, [(x['why'], x['text']) for x in typo2][:3])
        c6.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
