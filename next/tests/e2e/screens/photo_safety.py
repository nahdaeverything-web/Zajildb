"""THE PHOTO INVARIANT (RULED 2026-11-16): a media record that holds bytes is never replaced by one that does not.

Photos have no server copy (DF-4), so the bytes on a device are the only ones.

  RF-23  a sync cycle used to remove the bytes of every photo from the device that took it: the device's own pushed
         media row came back in the pull, metadata only (§7), and was written over the stored record.

Two devices on one stub project that models the table. Harness build, the net armed. All shapes are CONSTRUCTED.

    python3 tests/e2e/screens/photo_safety.py
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET
from _typography import SCAN                  # noqa: E402
NET = Net()
PAGES = []
STUB = 'https://stub.example.test'

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

class Server:
    """sync_records as docs/SYNC-DESIGN.md §1 describes it: upsert on (owner, store, record_id), a server_seq per write, §4 LWW."""
    def __init__(self): self.rows = {}; self.seq = 0; self.log = []
    def upsert(self, r):
        key = (r['store'], r['record_id']); old = self.rows.get(key); row = dict(r)
        if old is not None and (row['updated_at'], str(row.get('device_id') or '')) <= (old['updated_at'], str(old.get('device_id') or '')): row = dict(old)
        self.seq += 1; row['server_seq'] = self.seq; self.rows[key] = row; return row
    def page(self, c): return sorted((r for r in self.rows.values() if r['server_seq'] > c), key=lambda r: r['server_seq'])
    def media(self): return [r for (s, _), r in self.rows.items() if s == 'media']
def make_handler(srv):
    def handler(route, request):
        if '/auth/v1/token' in request.url:
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-A', 'refresh_token': 'REFRESH-A', 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-A', 'email': 'a@zajil.test'}})); return
        if request.method == 'POST':
            rows = json.loads(request.post_data or '[]'); out = [srv.upsert(r) for r in rows]; srv.log.append(('POST', [r['store'] for r in out]))
            route.fulfill(status=200, content_type='application/json', body=json.dumps(out)); return
        c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); rows = srv.page(c); srv.log.append(('GET', [r['store'] for r in rows]))
        route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))
    return handler

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s)
MEDIA = "async (db) => (await db.idbGetAll('media')).map(m => [m.name, m.blob ? m.blob.size : 'NO BYTES']).sort()"
def media(pg): return run(pg, MEDIA)
ADD = """async (db, bird, file, body) => { let x = db.allBirds().find(y => y.name === bird); if (!x) { await db.saveBird(db.newBird({ name: bird, sex: 'cock' })); x = db.allBirds().find(y => y.name === bird); }
  await db.addMedia(x.id, 'photo', 'body', file, new Blob([body], { type: 'image/png' })); }"""
SYNC = "async (db) => { await db.syncNow(); }"

def device(b, H, srv, signed=True):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}, accept_downloads=True))
    if srv is not None:
        ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', make_handler(srv))
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady')
    if srv is not None and signed: run(pg, "async (db) => { await db.signIn('a@zajil.test', 'pw'); }")
    return ctx, pg

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ RF-23 — the device that took the photo keeps its bytes through a sync cycle ═══
        srv = Server(); c1, ONE = device(b, H, srv)
        run(ONE, ADD, 'طير', 'photo.png', 'xyz'); before = media(ONE)
        run(ONE, SYNC); after1 = media(ONE); run(ONE, SYNC); run(ONE, SYNC); after3 = media(ONE)
        came_back = any(k == 'GET' and 'media' in stores for k, stores in srv.log)
        check('[RF-23] the photo is pushed as metadata only, and the device\'s own row comes back in the pull — the case under test', before == [['photo.png', 3]] and len(srv.media()) == 1 and 'blob' not in srv.media()[0]['data'] and came_back, (before, srv.log))
        check('[RF-23 · M-rf23 fails here] after «مزامنة الآن» the photo still has its bytes on the device that took it', after1 == [['photo.png', 3]], after1)
        check('[RF-23] …and after three cycles', after3 == [['photo.png', 3]], after3)

        # the automatic cycle: no button, the coordinator's 3-second cycle after a change
        srv.log.clear(); ONE.goto(ROOT + 'birds/', wait_until='load'); ONE.wait_for_function('window.__zajilDb'); ONE.wait_for_timeout(1500); srv.log.clear()
        run(ONE, ADD, 'طير', 'auto.png', 'abcde')
        def wait_log(pred, secs=25):
            for _ in range(secs * 2):
                if pred(): return True
                ONE.wait_for_timeout(500)
            return False
        pushed = wait_log(lambda: ('POST', ['media']) in srv.log)
        # the coordinator pulls BEFORE it pushes, so the row comes back on the NEXT automatic cycle: another change brings one, 3 seconds later
        run(ONE, "async (db) => { await db.saveBird(db.newBird({ name: 'طير آخر', sex: 'hen' })); }")
        pulled = wait_log(lambda: any(k == 'GET' and 'media' in stores for k, stores in srv.log))
        ONE.wait_for_timeout(800); auto = media(ONE)
        check('[RF-23 · auto] with no press, the coordinator pushed the new photo\'s row, and its next automatic cycle pulled that row back', pushed and pulled, srv.log)
        check('[RF-23 · auto · M-rf23 fails here] …and both photos still have their bytes after those automatic cycles', auto == [['auto.png', 5], ['photo.png', 3]], auto)

        # a second device: the row arrives without bytes, as designed — and what it sends back never costs ONE its bytes
        c2, TWO = device(b, H, srv); run(TWO, SYNC); two = media(TWO)
        check('[RF-23] a second device receives the rows without bytes (§7, unchanged)', two == [['auto.png', 'NO BYTES'], ['photo.png', 'NO BYTES']], two)
        old = next(r for r in srv.media() if r['data']['name'] == 'photo.png')
        srv.upsert({**old, 'data': {**old['data'], 'name': 'renamed.png'}, 'updated_at': '2099-01-01T00:00:00.000Z', 'device_id': 'another-device'})   # as a device with no bytes would push it
        run(ONE, SYNC); one = media(ONE)
        check('[RF-23 · M-rf23 fails here] a NEWER row for the same photo, written by a device that has no bytes, updates the metadata on ONE and leaves its bytes', one == [['auto.png', 5], ['renamed.png', 3]], one)
        c1.close(); c2.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
