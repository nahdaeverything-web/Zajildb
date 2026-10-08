#!/usr/bin/env python3
"""The sign-in gate — RULED 2026-10-07, built on exactly two things the device has.

  session present             -> through, online or offline
  no session, no records      -> the sign-in screen; sign-in required
  no session, records present -> the sign-in screen showing THE LOFT — its name, and the
                                 breeder's name if recorded — never an account; with export
                                 on the gate itself and the existing help line. No way into
                                 the loft without signing in: export is the escape hatch, not
                                 a bypass.

A wrong address is two different problems, and the gate says which: an address that is not
this device's owner («هذا الجهاز يحمل بيانات حساب آخر», RF-13) and credentials that are simply
wrong («بيانات الدخول غير صحيحة»). Neither attempt changes the device or either account.

Nothing re-arms on the collision CLEAR: CLEAR leaves no data and stores a session. A build with
no sync configuration has nothing to sign into and does not gate (raised in the order's
report); the test-harness route is a test surface and stands outside it.

Binds to data-testid only. Provisions its own server (R6)."""
import hashlib
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve, OUT                 # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET (RULED 2026-10-08): armed beneath the stub, asserted at the end
NET = Net()

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


STUB = 'https://stub.example.test'
KNOWN = {'A', 'B'}


class Server:
    def __init__(self):
        self.rows = {}; self.seq = 0; self.log = []

    def upsert(self, owner, r):
        self.seq += 1; row = dict(r, server_seq=self.seq, owner='user-' + owner); self.rows[(owner, r['store'], r['record_id'])] = row; return row

    def page(self, owner, cursor, limit):
        return sorted((r for (o, _, _), r in self.rows.items() if o == owner and r['server_seq'] > cursor), key=lambda r: r['server_seq'])[:limit]

    def digest(self, owner):
        rows = sorted((s, rid, r['server_seq'], json.dumps(r['data'], sort_keys=True, ensure_ascii=False)) for (o, s, rid), r in self.rows.items() if o == owner)
        return f"{len(rows)} rows {hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()[:12]}"

    def calls(self, who, since=0):
        return [(m, d) for w, m, d in self.log[since:] if w == who]


srv = Server()


def handler(route, request):
    url = request.url
    if '/auth/v1/token' in url:
        body = json.loads(request.post_data or '{}')
        who = (body.get('email') or '').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        srv.log.append((who, 'TOKEN', ''))
        if who not in KNOWN or (body.get('password') and body.get('password') != 'pw'):
            route.fulfill(status=400, content_type='application/json', body='{"error":"invalid_grant","error_description":"Invalid login credentials"}'); return
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600,
            'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}}))
        return
    who = (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
    if request.method == 'POST':
        body = json.loads(request.post_data or '[]'); srv.log.append((who, 'POST', len(body)))
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in body])); return
    cursor = int(re.search(r'server_seq=gt\.(\d+)', url).group(1)); rows = srv.page(who, cursor, int(re.search(r'limit=(\d+)', url).group(1)))
    srv.log.append((who, 'GET', f'cursor>{cursor}: {len(rows)}')); route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))


RUN = "async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }"


def run(pg, fn, arg=None):
    return pg.evaluate(RUN % fn, arg)


CENSUS = """async () => {
  const idb = await new Promise((res, rej) => { const r = indexedDB.open('zajil'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
  const out = {}; for (const n of [...idb.objectStoreNames]) out[n] = await new Promise((res) => { const q = idb.transaction(n).objectStore(n).getAll(); q.onsuccess = () => res(q.result); });
  idb.close(); const st = {}; for (const r of out.settings) st[r.key] = r.value; const acked = st.lastAckedSeq || 0;
  return { counts: Object.fromEntries(Object.entries(out).filter(([k]) => k !== 'settings').map(([k, v]) => [k, v.length])), birds: out.birds.map(b => b.name).sort(),
           unpushed: out.oplog.filter(o => o.seq > acked).length, signedIn: !!st.authRefreshToken, owner: st.dataOwnerId || null }; }"""
STATE = """() => { const g = document.querySelector('[data-testid=signin-screen]'); const gate = g ? g.getAttribute('data-gate') : null;
  return { path: location.pathname, gate, loft: document.querySelector('[data-testid=gate-loft]')?.textContent || null,
           breeder: document.querySelector('[data-testid=gate-breeder]')?.textContent || null, exportBtn: !!document.querySelector('[data-testid=gate-export]'),
           help: document.querySelector('[data-testid=signin-help]')?.textContent || null, navLinks: document.querySelectorAll('[data-testid=nav-link]').length,
           birdRows: document.querySelectorAll('[data-testid=bird-row]').length, h1: document.querySelector('h1')?.textContent || null,
           text: document.body.innerText }; }"""


def census(pg):
    return pg.evaluate(CENSUS)


def state(pg):
    return pg.evaluate(STATE)


def device(b, configured=True, downloads=False):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}, accept_downloads=downloads))
    if configured:
        ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(500); pg.evaluate("async () => { await window.__zajilReady; }")
    return ctx, pg


def seed(pg):
    run(pg, """async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت أبو خالد', location: 'إربد', breederName: 'خالد العمري', phone: '+962790000000' });
        for (const n of ['أ-1', 'أ-2']) await db.saveBird(db.newBird({ name: n, sex: 'cock', loftId: db.currentLoft().id })); }""")


def open_(pg, route):
    pg.goto(ROOT + route, wait_until='load'); pg.wait_for_timeout(1800)


def sign_in(pg, email, pw='pw'):
    pg.fill('[data-testid=f-email]', email); pg.fill('[data-testid=f-password]', pw); pg.click('[data-testid=signin-submit]')
    try:
        pg.wait_for_function("() => document.querySelector('[data-testid=dialog]') || document.querySelector('[data-testid=msg-cred]') || !document.querySelector('[data-testid=signin-screen][data-gate]')", timeout=15000)
    except Exception:
        pass
    pg.wait_for_timeout(1200)


# the routes the export wrote, derived
ROUTES = sorted(('' if os.path.relpath(d, OUT) == '.' else os.path.relpath(d, OUT).replace(os.sep, '/')) for d, _, files in os.walk(OUT) if 'index.html' in files)
ROUTES = [r for r in ROUTES if not r.startswith(('test-harness', '404', '_not-found', '_next'))]

srvp, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # account B exists on the server with a loft of its own
        cb, pb = device(b); run(pb, "async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت ب' }); await db.saveBird(db.newBird({ name: 'ب-1', sex: 'cock', loftId: db.currentLoft().id })); await db.signIn('b@zajil.test', 'pw'); await db.syncNow(); }"); cb.close()

        # ══ STATE 1 — no session, no records ═══════════════════════════════════════════
        ctx, pg = device(b)
        gated = {}
        for r in ROUTES:
            open_(pg, r + ('/' if r else '')); st = state(pg)
            gated[r or '(root)'] = (st['gate'], st['navLinks'], st['birdRows'])
        check(f'[no session, no records] every one of the {len(ROUTES)} exported routes is the sign-in gate — no nav, no content',
              all(v == ('empty', 0, 0) for v in gated.values()), str({k: v for k, v in gated.items() if v != ('empty', 0, 0)}))
        st = state(pg)
        check('[no session, no records] …with nothing about a loft on it: no loft line, no export',
              st['loft'] is None and st['exportBtn'] is False and 'يحمل' not in st['text'])
        open_(pg, 'sign-in/'); sign_in(pg, 'a@zajil.test'); st = state(pg)
        check('[no session, no records] signing in goes through — a gate opened AT /sign-in leaves for الأدوات as before',
              st['gate'] is None and st['path'].endswith('/tools/') and st['navLinks'] > 0, st['path'])
        ctx.close()

        # ══ STATE 2 — no session, records present ══════════════════════════════════════
        ctx, pg = device(b, downloads=True); seed(pg)
        open_(pg, 'birds/'); st = state(pg); before = census(pg); a0, b0 = srv.digest('A'), srv.digest('B')
        check('[no session, records] the gate stands in front of the loft, and shows THE LOFT: its name and the breeder',
              st['gate'] == 'records' and st['loft'] == 'هذا الجهاز يحمل لوفت أبو خالد' and st['breeder'] == 'المربّي: خالد العمري',
              f"{st['loft']} / {st['breeder']}")
        check('[no session, records] …never an account: no id, no address, no masked address on the screen',
              not re.search(r'user-|@|•••', st['text']), st['text'][:80])
        check('[no session, records] …no way in: no nav, no bird rows, no link to any route',
              st['navLinks'] == 0 and st['birdRows'] == 0 and pg.locator('a[href*="/birds"], a[href*="/tools"]').count() == 0)
        check('[no session, records] …export is ON the gate, not behind a menu, and the help line is there',
              st['exportBtn'] and pg.locator('[data-testid=gate-export]').is_visible() and st['help'] and 'إدارة زاجل' in st['help'], st['help'])
        with pg.expect_download(timeout=20000) as dl:
            pg.click('[data-testid=gate-export]')
        ex = json.loads(open(dl.value.path(), encoding='utf-8').read())
        check('[no session, records] «تصدير البيانات» from the gate hands over the whole loft, signed out',
              sorted(x['name'] for x in ex['birds']) == ['أ-1', 'أ-2'] and ex['lofts'][0]['name'] == 'لوفت أبو خالد' and 'user-' not in json.dumps(ex), dl.value.suggested_filename)
        check('[no session, records] …and exporting changes nothing: still gated, device untouched', state(pg)['gate'] == 'records' and census(pg) == before)
        gated = {}
        for r in ROUTES:
            open_(pg, r + ('/' if r else '')); gated[r or '(root)'] = state(pg)['gate']
        check(f'[no session, records] the gate holds on every one of the {len(ROUTES)} routes', all(v == 'records' for v in gated.values()), str({k: v for k, v in gated.items() if v != 'records'}))

        # ── the two wrong attempts, from the gate ──
        open_(pg, 'birds/'); mark = len(srv.log); sign_in(pg, 'a@zajil.test', 'wrong'); st = state(pg)
        check('[wrong credentials] the gate says the credentials are wrong — and says nothing about another account',
              pg.locator('[data-testid=msg-cred]').count() == 1 and 'البريد الإلكتروني أو كلمة المرور غير صحيحة' in st['text'] and 'حساب آخر' not in st['text'] and pg.locator('[data-testid=dialog]').count() == 0,
              pg.locator('[data-testid=msg-cred]').inner_text() if pg.locator('[data-testid=msg-cred]').count() else 'no message')
        check('[wrong credentials] …device and both accounts unchanged', census(pg) == before and srv.digest('A') == a0 and srv.digest('B') == b0 and srv.calls('A', mark) == [('TOKEN', '')], str(srv.calls('A', mark)))
        pg.fill('[data-testid=f-email]', ''); mark = len(srv.log)
        # this device belongs to nobody yet (never signed in); make it A's first, then come back signed out
        sign_in(pg, 'a@zajil.test'); pg.wait_for_timeout(800)
        run(pg, "async (db) => { await db.signOut(); await db.refreshSyncStatus(); }"); pg.wait_for_timeout(800)
        before = census(pg); a0 = srv.digest('A'); open_(pg, 'birds/'); mark = len(srv.log); sign_in(pg, 'b@zajil.test'); st = state(pg)
        check("[another account's data] the gate says THIS device holds another account's data — a different problem, in different words",
              pg.locator('[data-testid=dialog]').count() == 1 and 'هذا الجهاز يحمل بيانات حساب آخر' in pg.locator('[data-testid=dialog]').inner_text() and pg.locator('[data-testid=msg-cred]').count() == 0,
              pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')[:70] if pg.locator('[data-testid=dialog]').count() else 'no dialog')
        pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(400)
        check("[another account's data] …and after cancelling, the gate itself says so too, apart from the credentials message",
              pg.locator('[data-testid=msg-owner]').count() == 1 and pg.locator('[data-testid=msg-cred]').count() == 0 and state(pg)['gate'] == 'records')
        check("[another account's data] …device and both accounts unchanged",
              census(pg) == before and srv.digest('A') == a0 and srv.digest('B') == b0 and srv.calls('B', mark) == [('TOKEN', '')], str(srv.calls('B', mark)))
        # ── the right address goes through to the loft, in place ──
        pg.fill('[data-testid=f-email]', ''); sign_in(pg, 'a@zajil.test'); st = state(pg)
        check('[the owner] signs in and the gate lifts IN PLACE: the route that was opened, the loft intact',
              st['gate'] is None and st['path'].endswith('/birds/') and st['birdRows'] == 2 and st['h1'] == 'لوفت أبو خالد', f"{st['path']} · {st['birdRows']} rows · h1 {st['h1']}")

        # ══ STATE 3 — session present: through, online or offline ═════════════════════
        ctx.set_offline(True); pg.reload(wait_until='load'); pg.wait_for_timeout(2500); st = state(pg)
        check('[session, OFFLINE] a signed-in device is unaffected: through, with its loft, and nothing asked of the network',
              st['gate'] is None and st['birdRows'] == 2 and st['navLinks'] > 0, f"gate={st['gate']} rows={st['birdRows']}")
        open_(pg, 'tools/'); st = state(pg)
        check('[session, OFFLINE] …on every route reached offline too', st['gate'] is None and st['h1'] == 'الأدوات', st['h1'])
        ctx.set_offline(False)
        for r in ROUTES[:6]:
            open_(pg, r + ('/' if r else ''))
        check('[session, ONLINE] …and online', all(state(pg)['gate'] is None for _ in [0]))
        # sign-out brings the gate back, with the loft named
        open_(pg, 'tools/'); pg.wait_for_selector('[data-testid=sign-out]'); pg.click('[data-testid=sign-out]'); pg.wait_for_selector('[data-testid=dialog]'); pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(1500); st = state(pg)
        check('[sign-out] the gate comes back at once, naming the loft, without a reload', st['gate'] == 'records' and st['loft'] == 'هذا الجهاز يحمل لوفت أبو خالد', str(st['gate']))
        check('zero page errors', not pg.errs, '; '.join(pg.errs[:2]))
        ctx.close()

        # ══ the collision CLEAR re-arms nothing: it leaves no data and stores a session ═══
        ctx, pg = device(b); seed(pg); run(pg, "async (db) => { await db.signIn('a@zajil.test', 'pw'); await db.syncNow(); await db.signOut(); }")
        open_(pg, 'birds/'); sign_in(pg, 'b@zajil.test'); pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(400); pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(3000); st = state(pg)
        check('[CLEAR] after export-less clear and sign-in as B the device is through, as B, with B\'s loft', st['gate'] is None and st['h1'] == 'لوفت ب', f"gate={st['gate']} h1={st['h1']}")
        ctx.close()

        # ══ outside the gate ════════════════════════════════════════════════════════════
        ctx, pg = device(b, configured=False); seed(pg); open_(pg, 'birds/'); st = state(pg)
        check('[unconfigured] a build with no sync configuration has nothing to sign into and does not gate (raised)', st['gate'] is None and st['birdRows'] == 2 and st['navLinks'] > 0)
        ctx.close()
        ctx, pg = device(b)
        check('[harness] the test-harness route stands outside the gate', pg.evaluate("() => !!document.querySelector('#harness, [data-testid=harness]') || typeof window.__zajilReady !== 'undefined'"))
        ctx.close()
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
