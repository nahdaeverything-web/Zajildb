"""PHOTO SYNC, STAGE 1 (RULED 2026-11-18): a photo taken on one device appears on the other when that bird is opened.

Up: after a record cycle the coordinator starts a pass that uploads, one at a time, every media record that holds
bytes and is not marked `stored`; record sync never waits for it. Down: the other device fetches the bytes when the
bird's profile first draws the row, and keeps them. A failed, refused or bucket-less upload leaves the bytes on the
device exactly as they were, and never loops hot. Harness build; the table AND the storage API are stubs; the net armed.

    python3 tests/e2e/screens/photo_sync.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import hashlib
import time
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402
from _typography import SCAN                 # noqa: E402
NET = Net()
PAGES = []

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

STUB = 'https://stub.example.test'
OBJ = re.compile(r'/storage/v1/object/(authenticated/)?photos/([^/]+)/([^/?]+)')

class Server:
    """The table (owner rows, one server_seq) and the storage bucket (objects by owner/id), with switchable faults."""
    def __init__(self):
        self.rows = {}; self.seq = 0; self.objects = {}; self.posts = []; self.gets = []; self.held = []; self.deletes = []
        self.stub_errors = []
        self.mode = {}       # owner -> 'ok' | 'nobucket' | 'abort' | 'hold' | 'toolarge' | 'badmime' | 'getfail' | 'portal' | 'getportal' | 'gethold'
    def upsert(self, o, r): self.seq += 1; row = dict(r, server_seq=self.seq, owner=o); self.rows[(o, r['store'], r['record_id'])] = row; return row
    def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
    def media_row(self, o, mid): return self.rows.get((o, 'media', mid))
srv = Server()
def err(route, status, code, message): route.fulfill(status=status, content_type='application/json', body=json.dumps({'code': code, 'message': message}))
def store_object(route, request, who, owner, mid):
    srv.objects[(owner, mid)] = {'bytes': request.post_data_buffer or b'', 'type': request.headers.get('content-type'), 'upsert': request.headers.get('x-upsert')}
    route.fulfill(status=200, content_type='application/json', body=json.dumps({'Key': f'photos/{owner}/{mid}'}))
def handler(route, request):
    try: _handler(route, request)
    except Exception as e: srv.stub_errors.append(repr(e)[:160])     # a page that left before its answer; counted, shown with the page errors
def _handler(route, request):
    if '/auth/v1/token' in request.url:
        body = json.loads(request.post_data or '{}'); who = (body.get('email') or 'a@').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}})); return
    who = 'user-' + (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
    m = OBJ.search(request.url)
    if m:
        owner, mid = m.group(2), m.group(3); mode = srv.mode.get(who, 'ok')
        if request.method == 'POST':
            srv.posts.append((who, owner, mid, len(request.post_data_buffer or b'')))
            if owner != who: err(route, 403, 'AccessDenied', 'new row violates row-level security policy'); return
            if mode == 'nobucket': err(route, 404, 'NoSuchBucket', 'Bucket not found'); return
            if mode == 'full': err(route, 507, 'InsufficientStorage', 'storage quota exceeded'); return
            if mode == 'toolarge': err(route, 413, 'EntityTooLarge', 'The object exceeded the maximum allowed size'); return
            if mode == 'badmime': err(route, 400, 'InvalidMimeType', 'mime type image/jpeg is not supported'); return
            if mode == 'abort': route.abort('internetdisconnected'); return
            if mode == 'portal': route.fulfill(status=200, content_type='text/html', body='<html>sign in to the wifi</html>'); return
            if mode == 'hold': srv.held.append((route, request, who, owner, mid)); return
            store_object(route, request, who, owner, mid); return
        if request.method == 'GET':
            srv.gets.append((who, owner, mid))
            o = srv.objects.get((owner, mid))
            if owner != who or not m.group(1) or not o or mode == 'getfail': err(route, 404, 'NoSuchKey', 'Object not found'); return
            if mode == 'gethold' or (mode == 'getholdfirst' and not getattr(srv, 'held_first', False)):
                if mode == 'getholdfirst': srv.held_first = True
                srv.held.append((route, o)); return
            if mode == 'getportal': route.fulfill(status=200, content_type='text/html', body='<html>sign in to the wifi</html>'); return
            route.fulfill(status=200, content_type=o['type'], body=o['bytes']); return
        if request.method == 'DELETE':
            srv.deletes.append((who, owner, mid))
            if mode == 'delabort': route.abort('internetdisconnected'); return
            if mode == 'delportal': route.fulfill(status=200, content_type='text/html', body='<html>sign in to the wifi</html>'); return
            if mode == 'nobucket': err(route, 404, 'NoSuchBucket', 'Bucket not found'); return
            if owner != who or (owner, mid) not in srv.objects: err(route, 404, 'NoSuchKey', 'Object not found'); return
            del srv.objects[(owner, mid)]
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'message': 'Successfully deleted'})); return
        err(route, 400, 'InvalidRequest', 'unexpected'); return
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in rows])); return
    c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); rows = srv.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def device(b, H, email, touch=False, width=430):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': width, 'height': 900}, has_touch=touch))
    ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
    ctx.add_init_script(POCKET_INIT)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email); return ctx, pg
# STAGE 3: a device whose app is "in the pocket" reports itself hidden, so its background pass downloads nothing. The
# stage-1 sections below prove the ON-VIEW fetch, so their receiving device is put in the pocket; the switch is per tab
# and survives navigation (sessionStorage), and is off by default.
POCKET_INIT = "Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (sessionStorage.getItem('zajil-test-pocket') === '1' ? 'hidden' : 'visible') });"
def pocket(pg, on): pg.evaluate("(on) => sessionStorage.setItem('zajil-test-pocket', on ? '1' : '0')", on)
def waits(pg, sel, timeout=15000):
    """A wait that answers instead of raising: a mutant must fail AT a check, never in a traceback."""
    try: pg.wait_for_selector(sel, timeout=timeout); return True
    except Exception: return False
def typo(pg): return [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]
def home(pg, H): pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady')
SYNC = "async (db) => { const r = await db.syncNow(); return r && r.ok !== false; }"
# the same, but it gives up after 10 s: a cycle that waits for a held upload must FAIL a check, not hang the suite (a page call has no time limit of its own)
SYNC_BOUNDED = "async (db) => Promise.race([db.syncNow().then(r => r && r.ok !== false), new Promise(r => setTimeout(() => r('STILL WAITING AFTER 10 s'), 10000))])"
PASS = "async (db) => { for (let i = 0; i < 80 && db.photoSyncState().inFlight; i++) await new Promise(r => setTimeout(r, 100)); return db.photoSyncState(); }"
BIRD = "async (db, name) => (await db.saveBird(db.newBird({ name, sex: 'cock', loftId: db.currentLoft().id }))).id"
# a real, decodable JPEG made in the page (so the other device can DRAW it), or raw bytes of a given size and type
PHOTO = """async (db, bird, name) => { const c = document.createElement('canvas'); c.width = 320; c.height = 200; const x = c.getContext('2d');
    for (let i = 0; i < 400; i++) { x.fillStyle = `hsl(${(i * 37) % 360} 70% ${30 + (i * 13) % 50}%)`; x.fillRect((i * 53) % 320, (i * 29) % 200, 40, 30); }
    const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.85)); const m = await db.addMedia(bird, 'photo', 'body', name, blob); return { id: m.id, size: blob.size }; }"""
RAW = "async (db, bird, name, size, type) => { const m = await db.addMedia(bird, 'photo', 'body', name, new Blob([new Uint8Array(size)], { type })); return { id: m.id, size }; }"
LOCAL = """async (db, id) => { const m = await db.idbGet('media', id); if (!m) return null; let sha = null;
    if (m.blob) { const h = new Uint8Array(await crypto.subtle.digest('SHA-256', await m.blob.arrayBuffer())); sha = [...h].map(x => x.toString(16).padStart(2, '0')).join(''); }
    return { size: m.blob ? m.blob.size : null, type: m.blob ? m.blob.type : null, sha, stored: m.stored || null }; }"""
def digits(s_): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s_ or '')
def drop_held():
    """Answer every request still held before forgetting it: a held request the page later abandons (a download now gives
    up after PHOTO_DOWNLOAD_TIMEOUT_MS) otherwise surfaces as a CancelledError traceback from the driver."""
    for h in list(srv.held):
        try: err(h[0], 503, 'Released', 'released by the suite')
        except Exception: pass
    srv.held.clear()
def storage_posts(who): return [p for p in srv.posts if p[0] == who]
def toasts(pg): return ' | '.join(pg.locator('[data-testid=toast]').all_inner_texts()).replace('\n', ' ')

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ UP: the record first, the bytes after it, never holding it up ═══
        ca, da = device(b, H, 'a@zajil.test'); bird = run(da, BIRD, 'طير الصورة')
        srv.mode['user-A'] = 'hold'
        ph = run(da, PHOTO, bird, 'body.jpg'); ok = run(da, SYNC_BOUNDED); da.wait_for_timeout(800)
        row = srv.media_row('user-A', ph['id'])
        check('[up] the record cycle FINISHED while the photo’s upload was still unanswered — bytes never hold records up (M-await fails here)', ok is True and len(srv.held) == 1 and row is not None, (ok, len(srv.held), bool(row)))
        check('[up] the pushed media row is metadata only: no bytes, and no `stored` marker before the upload is acknowledged', row is not None and 'blob' not in row['data'] and not row['data'].get('stored'), row and list(row['data']))
        route, request, who, owner, mid = srv.held.pop(); srv.mode['user-A'] = 'ok'; store_object(route, request, who, owner, mid)
        st = run(da, PASS); loc = run(da, LOCAL, ph['id']); obj = srv.objects.get(('user-A', ph['id']))
        check('[up] the object is at <owner>/<media id>, sent with its own type and as an upsert', obj is not None and obj['type'] == 'image/jpeg' and obj['upsert'] == 'true', obj and (obj['type'], obj['upsert']))
        check('[up] the bytes on the server are the bytes on the device — same length, same sha256', obj is not None and len(obj['bytes']) == loc['size'] == ph['size'] and hashlib.sha256(obj['bytes']).hexdigest() == loc['sha'], (obj and len(obj['bytes']), loc))
        check('[up] the record is marked stored on the device, and still holds its bytes', bool(loc['stored']) and loc['stored']['size'] == ph['size'] and loc['size'] == ph['size'], loc)
        run(da, SYNC); run(da, PASS); row = srv.media_row('user-A', ph['id'])
        check('[up] the marker reaches the server as part of the record', bool(row['data'].get('stored')) and 'blob' not in row['data'], row['data'])
        n = len(storage_posts('user-A')); run(da, SYNC); run(da, PASS); run(da, SYNC); run(da, PASS)
        check('[up] a stored photo is not sent again by later cycles', len(storage_posts('user-A')) == n == 1, (n, len(storage_posts('user-A'))))
        check('[up] …and the pulled-back copy of its own row did not take the bytes away (RF-23 holds)', run(da, LOCAL, ph['id'])['size'] == ph['size'])

        # ═══ DOWN: the other device, on first view of that bird ═══
        cb, dbb = device(b, H, 'a@zajil.test'); pocket(dbb, True); run(dbb, SYNC); before = run(dbb, LOCAL, ph['id'])
        check('[down · setup] the second device has the record, marked stored, without bytes — and has fetched nothing yet', before is not None and before['size'] is None and bool(before['stored']) and not srv.gets, (before, srv.gets))
        dbb.goto(ROOT + 'bird/?id=' + bird, wait_until='load')
        try: dbb.wait_for_selector('[data-testid=media-photo] img', timeout=15000)
        except Exception: pass
        drawn = dbb.evaluate("async () => { const i = document.querySelector('[data-testid=media-photo] img'); if (!i) return null; if (!i.complete) await new Promise(r => { i.onload = i.onerror = r; }); return { w: i.naturalWidth, h: i.naturalHeight }; }")
        check('[down] opening the bird shows the photo, drawn from real pixels (M-nofetch fails here)', drawn == {'w': 320, 'h': 200}, drawn)
        after = run(dbb, LOCAL, ph['id'])
        check('[down] the bytes are KEPT on the second device and are the same bytes: same sha256, the marker intact', after['sha'] == loc['sha'] and after['type'] == 'image/jpeg' and bool(after['stored']), after)
        check('[down] one GET, to the authenticated path of the owner’s own folder', srv.gets == [('user-A', 'user-A', ph['id'])], srv.gets)
        dbb.goto(ROOT + 'bird/?id=' + bird, wait_until='load'); waits(dbb, '[data-testid=media-photo] img'); dbb.wait_for_timeout(800)
        check('[down] opening the bird again fetches nothing: stored once fetched (M-nokeep fails here)', len(srv.gets) == 1, srv.gets)
        ops = run(dbb, "async (db, id) => (await db.listOps()).filter(o => o.recordId === id).length", ph['id'])
        check('[down] keeping fetched bytes logs no operation — there is nothing to tell the server', ops == 0, ops)

        # a photo that is NOT uploaded yet says so on the other device
        srv.mode['user-A'] = 'abort'
        ph2 = run(da, PHOTO, bird, 'second.jpg'); run(da, SYNC); st = run(da, PASS); l2 = run(da, LOCAL, ph2['id'])
        check('[offline] an upload the network drops leaves the bytes on the device and no marker (M-drop fails here)', l2['size'] == ph2['size'] and not l2['stored'] and st['failures'] >= 1 and ('user-A', ph2['id']) not in srv.objects, (l2, st))
        run(dbb, SYNC); dbb.goto(ROOT + 'bird/?id=' + bird, wait_until='load'); waits(dbb, '[data-testid=media-elsewhere]'); dbb.wait_for_timeout(600)
        tile = dbb.evaluate("() => { const e = document.querySelector('[data-testid=media-elsewhere]'); return e && { where: e.dataset.where, text: e.innerText.trim() }; }")
        ty = typo(dbb)
        check('[typography] «الصورة على جهاز آخر ولم تُرفع بعد» is drawn in a face that has Arabic', bool(tile) and not ty, ty[:3])
        check('[offline] the other device says the photo is on another device and not uploaded yet — and asks the server for nothing', tile == {'where': 'pending', 'text': 'الصورة على جهاز آخر ولم تُرفع بعد'} and len(srv.gets) == 1, (tile, len(srv.gets)))
        # the wait: automatic cycles do not hammer
        n = len(storage_posts('user-A'))
        for _ in range(5): run(da, "async (db) => { await db.runSyncCycle(); }"); run(da, PASS)
        st = run(da, PASS)
        check('[offline] five more automatic cycles send it ZERO more times — the pass is waiting out its backoff', len(storage_posts('user-A')) == n and st['waitMs'] > 30000, (n, len(storage_posts('user-A')), st['waitMs']))
        srv.mode['user-A'] = 'ok'; run(da, SYNC); run(da, PASS); run(da, SYNC); l2 = run(da, LOCAL, ph2['id'])
        check('[offline] «مزامنة الآن» retries at once, and with the network back the photo is stored', bool(l2['stored']) and l2['size'] == ph2['size'] and ('user-A', ph2['id']) in srv.objects, l2)
        run(dbb, SYNC); dbb.goto(ROOT + 'bird/?id=' + bird, wait_until='load')
        try: dbb.wait_for_function("() => document.querySelectorAll('[data-testid=media-photo] img').length === 2", timeout=15000)
        except Exception: pass
        check('[offline] …and now the other device shows both photos', dbb.locator('[data-testid=media-photo] img').count() == 2, dbb.locator('[data-testid=media-photo] img').count())
        ca.close(); cb.close()

        # ═══ NO BUCKET YET: bytes stay, nothing loops ═══
        cc, dc = device(b, H, 'c@zajil.test'); srv.mode['user-C'] = 'nobucket'; birdc = run(dc, BIRD, 'بلا حاوية')
        p1 = run(dc, PHOTO, birdc, 'one.jpg'); p2 = run(dc, PHOTO, birdc, 'two.jpg'); ok = run(dc, SYNC); st = run(dc, PASS)
        check('[no bucket] record sync still succeeds, and both media records are on the server', ok is True and srv.media_row('user-C', p1['id']) and srv.media_row('user-C', p2['id']), ok)
        check('[no bucket] the pass stopped at the FIRST refusal: one request, not one per photo', len(storage_posts('user-C')) == 1 and st['last']['failed'] and st['last']['failed']['code'] == 'NoSuchBucket', (storage_posts('user-C'), st['last']))
        for _ in range(6): run(dc, "async (db) => { await db.runSyncCycle(); }"); run(dc, PASS)
        dc.wait_for_timeout(1500); st = run(dc, PASS)
        check('[no bucket] six more automatic cycles: still ONE request in all — it never loops hot (M-hot fails here)', len(storage_posts('user-C')) == 1 and st['waitMs'] > 30000, (len(storage_posts('user-C')), st['waitMs']))
        l1, l2 = run(dc, LOCAL, p1['id']), run(dc, LOCAL, p2['id'])
        check('[no bucket] both photos still hold every byte on the device, unmarked', l1['size'] == p1['size'] and l2['size'] == p2['size'] and not l1['stored'] and not l2['stored'], (l1, l2))
        srv.mode['user-C'] = 'ok'; run(dc, SYNC); run(dc, PASS); run(dc, SYNC); l1, l2 = run(dc, LOCAL, p1['id']), run(dc, LOCAL, p2['id'])
        check('[no bucket] once the bucket exists, a sync stores both — nothing was lost by waiting', bool(l1['stored']) and bool(l2['stored']) and ('user-C', p1['id']) in srv.objects and ('user-C', p2['id']) in srv.objects, (l1['stored'], l2['stored']))
        cc.close()

        # ═══ REFUSED FILES are said, and stay ═══
        cd, dd = device(b, H, 'd@zajil.test'); birdd = run(dd, BIRD, 'مرفوض')
        big = run(dd, RAW, birdd, 'huge.jpg', 5 * 1024 * 1024 + 1, 'image/jpeg'); gif = run(dd, RAW, birdd, 'anim.gif', 2048, 'image/gif'); fine = run(dd, PHOTO, birdd, 'fine.jpg')
        run(dd, SYNC); st = run(dd, PASS); dd.wait_for_timeout(500); said = toasts(dd); ty = typo(dd)
        check('[refused] neither the file over 5 MiB nor the type outside the allow-list is ever sent', not any(p_[2] in (big['id'], gif['id']) for p_ in srv.posts), [p_[2] for p_ in srv.posts][-4:])
        check('[refused] two refusals in one pass are said in ONE notice that counts them — a notice each would lose one behind the two-toast cap (M-each fails here)', said.count('لم تُرفع') == 1 and ': 2.' in said and 'على هذا الجهاز فقط' in said, said[:300])
        check('[typography] the counted refusal notice is drawn in a face that has Arabic', 'لم تُرفع' in said and not ty, ty[:3])
        lb, lg, lf = run(dd, LOCAL, big['id']), run(dd, LOCAL, gif['id']), run(dd, LOCAL, fine['id'])
        check('[refused] both refused files keep every byte on the device, unmarked (M-drop fails here too)', lb['size'] == big['size'] and lg['size'] == 2048 and not lb['stored'] and not lg['stored'], (lb, lg))
        check('[refused] …and the photo behind them in the queue was still stored: a refusal does not stop the pass', bool(lf['stored']), lf)
        n = len(srv.posts); run(dd, SYNC); run(dd, PASS); run(dd, SYNC); run(dd, PASS); dd.wait_for_timeout(400)
        check('[refused] a refused file is not tried, or announced, again', len(srv.posts) == n and toasts(dd).count('لم تُرفع') <= 1, (n, len(srv.posts)))
        # …and not after the app is opened again either: the refusal is remembered on the device (M-forget fails here)
        home(dd, H); run(dd, SYNC); run(dd, PASS); run(dd, SYNC); run(dd, PASS); dd.wait_for_timeout(600)
        check('[refused · M-forget fails here] after the app is opened again, two more syncs send neither refused file and say nothing more about them',
              len(srv.posts) == n and 'لم تُرفع' not in toasts(dd) and 'غير مسموح' not in toasts(dd), (n, len(srv.posts), toasts(dd)[:200]))
        lb, lg = run(dd, LOCAL, big['id']), run(dd, LOCAL, gif['id'])
        check('[refused] …and both still hold every byte', lb['size'] == big['size'] and lg['size'] == 2048, (lb, lg))
        # ONE file of a type the browser could not decode (so it was stored as picked): named, said once, kept
        heic = run(dd, RAW, birdd, 'IMG_0001.HEIC', 4096, 'image/heic'); run(dd, SYNC); run(dd, PASS); dd.wait_for_timeout(500); said = toasts(dd); ty = typo(dd)
        check('[refused · type] a file of a type storage does not take is named in the notice: «نوع الملف «IMG_0001.HEIC» غير مسموح برفعه — بقي محفوظًا على هذا الجهاز فقط»',
              'نوع الملف «IMG_0001.HEIC» غير مسموح برفعه — بقي محفوظًا على هذا الجهاز فقط' in said, said[-260:])
        check('[typography] the named type-refusal notice is drawn in a face that has Arabic', 'IMG_0001.HEIC' in said and not ty, ty[:3])
        lh_ = run(dd, LOCAL, heic['id'])
        check('[refused · type] …it was never sent, and its bytes stay', not any(p_[2] == heic['id'] for p_ in srv.posts) and lh_['size'] == 4096 and not lh_['stored'], lh_)
        srv.mode['user-D'] = 'toolarge'; srvbig = run(dd, PHOTO, birdd, 'server-says-no.jpg'); run(dd, SYNC); run(dd, PASS); dd.wait_for_timeout(500)
        ls = run(dd, LOCAL, srvbig['id']); ty = typo(dd)
        check('[typography] the named refusal notice («الملف «…» أكبر من الحد…») is drawn in a face that has Arabic', 'server-says-no.jpg' in toasts(dd) and not ty, ty[:3])
        check('[refused] a file the SERVER refuses for size (413) is said too, and stays', 'server-says-no.jpg' in toasts(dd) and ls['size'] == srvbig['size'] and not ls['stored'], (toasts(dd)[-200:], ls))
        cd.close()

        # ═══ A 200 THAT IS NOT STORAGE'S ANSWER (a captive portal) stores nothing and keeps nothing ═══
        cg, dg = device(b, H, 'g@zajil.test'); birdg = run(dg, BIRD, 'بوابة'); srv.mode['user-G'] = 'portal'
        pg_ = run(dg, PHOTO, birdg, 'g.jpg'); run(dg, SYNC); st = run(dg, PASS); lg_ = run(dg, LOCAL, pg_['id'])
        check('[portal] an upload answered 200 by something that is not storage is NOT marked stored — bytes kept, a retry owed (M-anyok fails here)', not lg_['stored'] and lg_['size'] == pg_['size'] and st['failures'] >= 1 and st['last']['failed'] and st['last']['failed']['code'] == 'Unacknowledged', (lg_, st['last']))
        srv.mode['user-G'] = 'ok'; run(dg, SYNC); run(dg, PASS); run(dg, SYNC)
        ch, dh = device(b, H, 'g@zajil.test'); run(dh, SYNC); srv.mode['user-G'] = 'getportal'
        dh.goto(ROOT + 'bird/?id=' + birdg, wait_until='load'); saidfail = waits(dh, '[data-testid=media-elsewhere][data-where=failed]')
        lh = run(dh, LOCAL, pg_['id'])
        check('[portal] a download answered 200 with a page of another length is NOT kept as the photo (M-anylen fails here)', saidfail and lh is not None and lh['size'] is None and bool(lh['stored']), (saidfail, lh))
        srv.mode['user-G'] = 'ok'; cg.close(); ch.close()

        # ═══ A DOWNLOAD THAT FAILS says so, once ═══
        ce, de = device(b, H, 'e@zajil.test'); birde = run(de, BIRD, 'تنزيل'); pe = run(de, PHOTO, birde, 'e.jpg'); run(de, SYNC); run(de, PASS); run(de, SYNC)
        cf, df = device(b, H, 'e@zajil.test'); pocket(df, True); run(df, SYNC); srv.mode['user-E'] = 'getfail'; g0 = len(srv.gets)
        df.goto(ROOT + 'bird/?id=' + birde, wait_until='load'); waits(df, '[data-testid=media-elsewhere][data-where=failed]')
        text = (df.locator('[data-testid=media-elsewhere]').all_inner_texts() or [''])[0].strip(); ty = typo(df)
        run(df, "async (db, id) => { for (let i = 0; i < 5; i++) await db.fetchPhotoBytes(id); }", pe['id'])
        check('[down · failed] a download that fails says so on the tile', text == 'تعذّر تنزيل الصورة — ستُعاد المحاولة عند فتحها', text)
        check('[typography] «تعذّر تنزيل الصورة…» is drawn in a face that has Arabic', bool(text) and not ty, ty[:3])
        check('[down · failed] …and five more asks in the same visit send nothing: one GET in all', len(srv.gets) - g0 == 1, srv.gets[g0:])
        check('[down · failed] the record on that device is untouched: marker there, no bytes, nothing removed', (lambda x: x and x['size'] is None and bool(x['stored']))(run(df, LOCAL, pe['id'])))
        drop_held(); srv.mode['user-E'] = 'gethold'; df.goto(ROOT + 'bird/?id=' + birde, wait_until='load')
        got = waits(df, '[data-testid=media-elsewhere][data-where=fetching]'); text = (df.locator('[data-testid=media-elsewhere]').all_inner_texts() or [''])[0].strip(); ty = typo(df)
        check('[down · fetching] while the bytes are on their way the tile says «جارٍ تنزيل الصورة…», in a face that has Arabic', got and text == 'جارٍ تنزيل الصورة…' and not ty, (got, text, ty[:3]))
        srv.mode['user-E'] = 'ok'
        for route, o in srv.held: route.fulfill(status=200, content_type=o['type'], body=o['bytes'])
        drop_held()
        try: df.wait_for_selector('[data-testid=media-photo] img', timeout=15000)
        except Exception: pass
        check('[down · failed] opening the bird again retries, and the photo arrives', df.locator('[data-testid=media-photo] img').count() == 1)
        ce.close(); cf.close()

        # ═══ A DOCUMENT (not a photo) says the same three things in its own words — the …File strings ═══
        DOC = "async (db, bird, name) => { const blob = new Blob([new TextEncoder().encode('%PDF-1.4 synthetic ' + 'x'.repeat(600))], { type: 'application/pdf' }); const m = await db.addMedia(bird, 'document', 'other', name, blob); return { id: m.id, size: blob.size }; }"
        def tile_text(pg, where):
            ok_ = waits(pg, f'[data-testid=media-elsewhere][data-where={where}]'); pg.wait_for_timeout(300)
            return ok_, (pg.locator('[data-testid=media-elsewhere]').all_inner_texts() or [''])[0].strip(), typo(pg)
        ck, dk = device(b, H, 'k@zajil.test'); birdk = run(dk, BIRD, 'وثيقة'); srv.mode['user-K'] = 'abort'
        pk = run(dk, DOC, birdk, 'pedigree.pdf'); run(dk, SYNC); run(dk, PASS)
        cl, dl = device(b, H, 'k@zajil.test'); pocket(dl, True); run(dl, SYNC); dl.goto(ROOT + 'bird/?id=' + birdk, wait_until='load')
        got, text, ty = tile_text(dl, 'pending')
        check('[file · not uploaded] a document on another device and not uploaded yet says «الملف على جهاز آخر ولم يُرفع بعد», in a face that has Arabic',
              got and text == 'الملف على جهاز آخر ولم يُرفع بعد' and not ty, (got, text, ty[:3]))
        srv.mode['user-K'] = 'ok'; run(dk, SYNC); run(dk, PASS); run(dk, SYNC)
        check('[file · setup] the document is stored: a PDF is on the allow-list', ('user-K', pk['id']) in srv.objects and srv.objects[('user-K', pk['id'])]['type'] == 'application/pdf', list(srv.objects)[-1:])
        # off the profile first: since stage 3 an OPEN profile follows the pull and would fetch the document at once
        home(dl, H); run(dl, SYNC); drop_held(); srv.mode['user-K'] = 'gethold'; dl.goto(ROOT + 'bird/?id=' + birdk, wait_until='load')
        got, text, ty = tile_text(dl, 'fetching')
        check('[file · fetching] while a document is on its way the tile says «جارٍ تنزيل الملف…», in a face that has Arabic',
              got and text == 'جارٍ تنزيل الملف…' and not ty, (got, text, ty[:3]))
        srv.mode['user-K'] = 'getfail'
        for route, o in srv.held: err(route, 404, 'NoSuchKey', 'Object not found')
        drop_held()
        got, text, ty = tile_text(dl, 'failed')
        check('[file · failed] a document whose download fails says «تعذّر تنزيل الملف — ستُعاد المحاولة عند فتحه», in a face that has Arabic',
              got and text == 'تعذّر تنزيل الملف — ستُعاد المحاولة عند فتحه' and not ty, (got, text, ty[:3]))
        srv.mode['user-K'] = 'ok'; dl.goto(ROOT + 'bird/?id=' + birdk, wait_until='load'); arrived = waits(dl, '[data-testid=media-file]')
        lk = run(dl, LOCAL, pk['id'])
        check('[file] opening the bird again fetches the document, and its bytes are kept', arrived and lk is not None and lk['size'] == pk['size'] and lk['type'] == 'application/pdf', (arrived, lk))
        ck.close(); cl.close()

        # ══════════════════════ STAGE 2 (RULED 2026-11-19) ══════════════════════
        # ═══ A DELETED PHOTO'S OBJECT IS REMOVED — by the device that deleted it, after the undo has passed ═══
        AGE = "async (db) => { await db.setSetting('photoRemovals', (db.state.settings.photoRemovals || []).map(q => ({ ...q, at: new Date(Date.now() - db.PHOTO_REMOVE_GRACE_MS - 1000).toISOString() }))); }"
        QUEUE = "async (db) => (db.photoSyncState().removals || []).map(q => q.id)"
        def cycle(pg): run(pg, SYNC); return run(pg, PASS)
        cm, dm = device(b, H, 'm@zajil.test'); birdm = run(dm, BIRD, 'حذف'); pm = run(dm, PHOTO, birdm, 'm1.jpg'); cycle(dm); run(dm, SYNC)
        cn, dn = device(b, H, 'm@zajil.test'); run(dn, SYNC)
        check('[remove · setup] the photo is stored, and the second device has its record', ('user-M', pm['id']) in srv.objects and run(dn, LOCAL, pm['id']) is not None)
        run(dm, "async (db, id) => { window.__m = await db.deleteMedia(id); }", pm['id']); q = run(dm, QUEUE); cycle(dm)
        check('[remove] deleting a stored photo queues its object for removal, on the device that deleted it', q == [pm['id']], q)
        check('[remove · M-nograce fails here] while an undo is still possible NOTHING is removed: no DELETE is sent and the object is there',
              not srv.deletes and ('user-M', pm['id']) in srv.objects and run(dm, QUEUE) == [pm['id']], (srv.deletes, run(dm, QUEUE)))
        srv.mode['user-M'] = 'delabort'; run(dm, AGE); st = cycle(dm); n = len(srv.deletes)
        check('[remove · offline · M-dropqueue fails here] a removal the network drops stays queued, and the object stays',
              n == 1 and run(dm, QUEUE) == [pm['id']] and ('user-M', pm['id']) in srv.objects and st['last']['failed'] is not None, (n, run(dm, QUEUE), st['last']))
        for _ in range(5): run(dm, "async (db) => { await db.runSyncCycle(); }"); run(dm, PASS)
        st = run(dm, PASS)
        check('[remove · offline] five more automatic cycles send it ZERO more times — it waits out the same backoff as uploads', len(srv.deletes) == n and st['waitMs'] > 30000, (len(srv.deletes), st['waitMs']))
        srv.mode['user-M'] = 'delportal'; st = cycle(dm)
        check('[remove · portal · M-anydel fails here] a 200 that is not storage\'s answer removes nothing from the queue',
              run(dm, QUEUE) == [pm['id']] and st['last']['failed'] and st['last']['failed']['code'] == 'Unacknowledged', (run(dm, QUEUE), st['last']))
        srv.mode['user-M'] = 'ok'; st = cycle(dm)
        check('[remove · M-noremove fails here] with the network back the object is REMOVED from the owner\'s own folder, and the queue is empty',
              ('user-M', pm['id']) not in srv.objects and srv.deletes[-1] == ('user-M', 'user-M', pm['id']) and run(dm, QUEUE) == [] and st['last']['removed'] == 1, (srv.deletes[-1:], run(dm, QUEUE), st['last']))
        n = len(srv.deletes); cycle(dm); cycle(dm)
        check('[remove] …and it is not asked for again', len(srv.deletes) == n, len(srv.deletes) - n)
        run(dn, SYNC); stn = cycle(dn)
        check('[remove] the OTHER device takes the deletion and sends no DELETE of its own: one device removes an object',
              run(dn, LOCAL, pm['id']) is None and not any(d[0] == 'user-M' and d is not srv.deletes[n - 1] for d in srv.deletes[n:]) and run(dn, QUEUE) == [], (srv.deletes[n:], run(dn, QUEUE)))
        # an undo inside the grace: the record is back, so the object must never go
        pu = run(dm, PHOTO, birdm, 'undo.jpg'); cycle(dm); run(dm, SYNC)
        run(dm, "async (db, id) => { const m = await db.deleteMedia(id); await db.restoreMedia(m); }", pu['id']); run(dm, AGE); n = len(srv.deletes); st = cycle(dm)
        check('[remove · undo · M-noundo fails here] a deletion that was undone removes NOTHING: no DELETE, the object is there, the queue is cleared',
              len(srv.deletes) == n and ('user-M', pu['id']) in srv.objects and run(dm, QUEUE) == [], (srv.deletes[n:], run(dm, QUEUE)))
        # never stored: there is no object to remove
        srv.mode['user-M'] = 'abort'; pz = run(dm, PHOTO, birdm, 'never-up.jpg'); cycle(dm); run(dm, "async (db, id) => { await db.deleteMedia(id); }", pz['id'])
        check('[remove] deleting a photo that was never uploaded queues nothing', run(dm, QUEUE) == [], run(dm, QUEUE))
        srv.mode['user-M'] = 'ok'
        # the object is already gone (removed by hand, or never arrived): that is the end of it, not a retry forever
        pg2 = run(dm, PHOTO, birdm, 'gone.jpg'); cycle(dm); run(dm, SYNC); del srv.objects[('user-M', pg2['id'])]
        run(dm, "async (db, id) => { await db.deleteMedia(id); }", pg2['id']); run(dm, AGE); st = cycle(dm)
        check('[remove] an object that is already gone (404 NoSuchKey) ends the matter: the queue is empty and nothing failed', run(dm, QUEUE) == [] and not st['last']['failed'], (run(dm, QUEUE), st['last']))
        # deleting the BIRD removes its photos' objects too
        bird2 = run(dm, BIRD, 'طير يُحذف'); pc = run(dm, PHOTO, bird2, 'c.jpg'); cycle(dm); run(dm, SYNC)
        run(dm, "async (db, id) => { await db.deleteBird(id); }", bird2); q = run(dm, QUEUE); run(dm, AGE); cycle(dm)
        check('[remove · M-nocascade fails here] deleting a bird queues and removes the objects of its photos', q == [pc['id']] and ('user-M', pc['id']) not in srv.objects and run(dm, QUEUE) == [], (q, run(dm, QUEUE)))
        check('[remove] every DELETE in this run was addressed to the signed-in user\'s own folder', all(d[0] == d[1] for d in srv.deletes), srv.deletes[:3])
        cm.close(); cn.close()

        # ═══ THE STATUS COUNTS PHOTOS WAITING TO UPLOAD ═══
        STATUS = "async (db) => { await db.refreshSyncStatus(); const s = db.syncStatus(); return { state: s.state, waiting: s.photosWaiting, full: s.storageFull }; }"
        # a phone's width (390 px): the badge is judged where fanciers see it
        cs, ds = device(b, H, 's@zajil.test', touch=True, width=390); birds_ = run(ds, BIRD, 'ينتظر'); srv.mode['user-S'] = 'nobucket'
        run(ds, PHOTO, birds_, 'w1.jpg'); run(ds, PHOTO, birds_, 'w2.jpg'); run(ds, RAW, birds_, 'too-big.jpg', 5 * 1024 * 1024 + 1, 'image/jpeg'); cycle(ds); st = run(ds, STATUS)
        check('[status · M-nocount fails here] the status counts the files waiting to upload: 3 before any verdict (records are in step, photos are not)', st['state'] == 'synced' and st['waiting'] == 3, st)
        ds.goto(ROOT + 'tools/sync/', wait_until='load'); waits(ds, '[data-testid=sync-detail]'); got = waits(ds, '[data-testid=photos-waiting]'); ds.wait_for_timeout(400)
        line = (ds.locator('[data-testid=photos-waiting]').all_inner_texts() or [''])[0].strip(); ty = typo(ds)
        check('[status] the sync screen in الأدوات says «صور وملفات بانتظار الرفع: 3» (in the device\'s numerals), in a face that has Arabic', got and digits(line) == 'صور وملفات بانتظار الرفع: 3' and not ty, (got, line, ty[:3]))
        ds.goto(ROOT + 'birds/', wait_until='load'); got = waits(ds, '[data-testid=sync-row][data-state=photos]'); row_ = (ds.locator('[data-testid=sync-row]').all_inner_texts() or [''])[0].replace('\n', ' ').strip(); ty = typo(ds)
        check('[status · M-rowsilent fails here] the status row above the register says it too — silence would have claimed everything is sent', got and 'صور وملفات بانتظار الرفع' in row_ and not ty, (got, row_, ty[:3]))
        home(ds, H); srv.mode['user-S'] = 'ok'; cycle(ds); cycle(ds); st = run(ds, STATUS)
        check('[status] once the two photos are stored the count is 0: the file over the limit was refused, and a refused file is not waiting', st['waiting'] == 0, st)
        ds.goto(ROOT + 'birds/', wait_until='load'); ds.wait_for_timeout(1500)
        check('[status] …and the row is silent again', ds.locator('[data-testid=sync-row]').count() == 0, (ds.locator('[data-testid=sync-row]').all_inner_texts() or [''])[0])

        # ═══ A REFUSED FILE IS MARKED ON ITS OWN TILE — a small corner badge (RULED 2026-11-20), at 390 px ═══
        ds.goto(ROOT + 'bird/?id=' + birds_, wait_until='load'); got = waits(ds, '[data-testid=media-refused]'); ds.wait_for_timeout(400)
        marks = ds.evaluate("() => [...document.querySelectorAll('[data-testid=media-tile]')].map(t => { const r = t.querySelector('[data-testid=media-refused]'); return r ? { text: r.innerText.trim(), reason: r.dataset.reason, title: r.title } : null; })")
        ty = typo(ds)
        check('[tile · M-nomark fails here] the refused file\'s own tile carries the badge «لم يُرفع»; the two stored photos\' tiles carry nothing',
              got and len(marks) == 3 and [m_ for m_ in marks if m_] == [{'text': 'لم يُرفع', 'reason': 'size', 'title': 'الملف «too-big.jpg» أكبر من الحد المسموح للرفع — بقي محفوظًا على هذا الجهاز فقط'}], marks)
        check('[typography] the tile mark is drawn in a face that has Arabic', got and not ty, ty[:3])
        # where it sits: rectangles read off the page, on the refused tile
        geo = ds.evaluate("""() => { const r = document.querySelector('[data-testid=media-refused]'); if (!r) return null; const t = r.closest('[data-testid=media-tile]');
            const box = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom }; };
            return { tile: box(t), badge: box(r), del: box(t.querySelector('[data-testid=media-delete]')), name: box(t.querySelector('[data-testid=media-photo] span')) }; }""")
        def meets(a, b_): return bool(a and b_) and a['l'] < b_['r'] and b_['l'] < a['r'] and a['t'] < b_['b'] and b_['t'] < a['b']
        def area(a): return max(0, a['r'] - a['l']) * max(0, a['b'] - a['t'])
        share = round(area(geo['badge']) / area(geo['tile']), 3) if geo and geo['tile'] else None
        check('[tile · M-bigmark fails here] at 390 px the badge sits in the tile\'s top corner: inside the tile, over neither the file\'s name nor the delete button, and under a sixth of the photo',
              bool(geo) and bool(geo['name']) and geo['badge']['l'] >= geo['tile']['l'] and geo['badge']['r'] <= geo['tile']['r'] and geo['badge']['t'] - geo['tile']['t'] <= 10
              and not meets(geo['badge'], geo['name']) and not meets(geo['badge'], geo['del']) and share < 1 / 6, (share, geo))
        # RULED 2026-11-20: hover does not exist on a phone, where fanciers work — a TAP on the mark says the full sentence
        def tapped(pg, sel):
            """Tap the mark on a touch device; answer the notices shown within 5 s (never raise: a mutant fails AT a check)."""
            try: pg.locator(sel).first.tap(timeout=5000)
            except Exception as e_: return f'TAP FAILED: {e_}'[:200]
            try: pg.wait_for_function("() => [...document.querySelectorAll('[data-testid=toast]')].some(x => x.innerText.includes('too-big.jpg'))", timeout=5000)
            except Exception: pass
            return toasts(pg)
        said = tapped(ds, '[data-testid=media-refused]'); ty = typo(ds)
        check('[tile · M-notap fails here] a TAP on the mark says the full sentence: «الملف «too-big.jpg» أكبر من الحد المسموح للرفع — بقي محفوظًا على هذا الجهاز فقط»', 'الملف «too-big.jpg» أكبر من الحد المسموح للرفع — بقي محفوظًا على هذا الجهاز فقط' in said, said[:300])
        check('[typography] the sentence a tap shows is drawn in a face that has Arabic', not ty, ty[:3])
        # …and the edit form's strip carries the same badge ON the refused thumbnail, also said in full on a tap
        ds.goto(ROOT + 'bird/edit/?id=' + birds_, wait_until='load'); got = waits(ds, '[data-testid=strip-refused]'); ds.wait_for_timeout(400)
        strip = ds.evaluate("() => [...document.querySelectorAll('[data-testid=strip-saved]')].map(x => { const r = x.querySelector('[data-testid=strip-refused]'); return r ? { text: r.innerText.trim(), reason: r.dataset.reason } : null; })")
        ty = typo(ds)
        check('[strip · M-nostripmark fails here] the edit form\'s strip carries the same badge «لم يُرفع» on the refused file, and on no other',
              got and len(strip) == 3 and [x for x in strip if x] == [{'text': 'لم يُرفع', 'reason': 'size'}], strip)
        check('[typography] the strip mark is drawn in a face that has Arabic', got and not ty, ty[:3])
        sgeo = ds.evaluate("""() => { const box = (e) => { const b = e.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: Math.round(b.width), h: Math.round(b.height) }; };
            const items = [...document.querySelectorAll('[data-testid=photo-strip] > *')].map(box).sort((a, b) => a.l - b.l);
            const r = document.querySelector('[data-testid=strip-refused]'); const th = r && r.closest('[data-testid=strip-saved]');
            return { sizes: items.map(i => [i.w, i.h]), gaps: items.slice(1).map((i, k) => Math.round(i.l - items[k].r)), badge: r && box(r), thumb: th && box(th) }; }""")
        inside = bool(sgeo['badge']) and sgeo['badge']['l'] >= sgeo['thumb']['l'] and sgeo['badge']['r'] <= sgeo['thumb']['r'] and sgeo['badge']['t'] >= sgeo['thumb']['t'] and sgeo['badge']['b'] <= sgeo['thumb']['b']
        check('[strip · M-stripout fails here] at 390 px every thumbnail keeps 56 × 56 and the strip its even 8 px spacing; the badge sits inside the refused thumbnail',
              sgeo['sizes'] == [[56, 56]] * 3 and sgeo['gaps'] == [8, 8] and inside, sgeo)
        said = tapped(ds, '[data-testid=strip-refused]'); ty = typo(ds)
        check('[strip · M-nostriptap fails here] a TAP on the strip\'s mark says the same full sentence', 'الملف «too-big.jpg» أكبر من الحد المسموح للرفع — بقي محفوظًا على هذا الجهاز فقط' in said, said[:300])
        check('[typography] …in a face that has Arabic', not ty, ty[:3])
        cs.close()

        # ═══ STORAGE THAT IS FULL is said, once, and the bytes stay ═══
        ct, dt = device(b, H, 't@zajil.test'); birdt = run(dt, BIRD, 'ممتلئ'); srv.mode['user-T'] = 'full'
        f1 = run(dt, PHOTO, birdt, 'f1.jpg'); f2 = run(dt, PHOTO, birdt, 'f2.jpg'); st = cycle(dt); dt.wait_for_timeout(500); said = toasts(dt); ty = typo(dt)
        check('[full · M-fullsilent fails here] storage that answers "full" is SAID: «امتلأت مساحة التخزين على الخادم — لم تُرفع الصور، وهي محفوظة على هذا الجهاز»',
              'امتلأت مساحة التخزين على الخادم — لم تُرفع الصور، وهي محفوظة على هذا الجهاز' in said, said[-200:])
        check('[typography] the full-storage notice is drawn in a face that has Arabic', 'امتلأت' in said and not ty, ty[:3])
        l1, l2 = run(dt, LOCAL, f1['id']), run(dt, LOCAL, f2['id'])
        check('[full · M-fullrefuse fails here] nothing is marked refused and every byte stays: a full store is not a verdict on the file',
              l1['size'] == f1['size'] and l2['size'] == f2['size'] and not l1['stored'] and not l2['stored'] and not run(dt, "async (db) => Object.keys(db.photoSyncState().refused).length"), (l1, l2))
        check('[full] the pass stopped at the first refusal — one request, not one per photo — and waits', len(storage_posts('user-T')) == 1 and st['last']['failed']['code'] == 'StorageFull' and st['waitMs'] > 30000, (storage_posts('user-T'), st['last']))
        cycle(dt); dt.wait_for_timeout(400)
        check('[full] a second pass that meets the same answer does not say it a second time', toasts(dt).count('امتلأت') <= 1, toasts(dt)[-200:])
        st2 = run(dt, STATUS)
        check('[full] the status carries it, with the two photos still counted as waiting', st2['full'] is True and st2['waiting'] == 2, st2)
        dt.goto(ROOT + 'tools/sync/', wait_until='load'); waits(dt, '[data-testid=sync-detail]'); got = waits(dt, '[data-testid=storage-full]')
        check('[full] الأدوات shows the same sentence while it lasts', got and 'امتلأت مساحة التخزين' in (dt.locator('[data-testid=storage-full]').all_inner_texts() or [''])[0], got)
        home(dt, H); srv.mode['user-T'] = 'ok'; cycle(dt); cycle(dt); st3 = run(dt, STATUS); l1 = run(dt, LOCAL, f1['id'])
        check('[full] when storage takes uploads again both photos are stored and the status is clear', bool(l1['stored']) and st3['full'] is False and st3['waiting'] == 0, (l1['stored'], st3))
        ct.close()

        # ══════════════════════ STAGE 3 (ORDERED 2026-11-20) ══════════════════════
        # ═══ EVERY STORED PHOTO COMES DOWN IN THE BACKGROUND — one at a time, online and in front, never holding records up ═══
        HELD_ = "async (db, ids) => { const out = []; for (const id of ids) { const m = await db.idbGet('media', id); out.push(!!(m && m.blob)); } return out; }"
        DSTATE = "async (db) => { const s = db.photoSyncState(); return { inFlight: s.inFlight, failures: s.failures, waitMs: s.waitMs, last: s.last }; }"
        held_gets = lambda: [h for h in srv.held if len(h) == 2]
        def release_gets():
            for h in held_gets(): srv.held.remove(h); h[0].fulfill(status=200, content_type=h[1]['type'], body=h[1]['bytes'])
        cu1, du1 = device(b, H, 'u@zajil.test'); bu = run(du1, BIRD, 'ينزل وحده')
        ups = [run(du1, PHOTO, bu, f'u{k}.jpg') for k in range(3)]; cycle(du1); cycle(du1)
        check('[setup] the first device stored three photos', all(run(du1, LOCAL, u_['id'])['stored'] for u_ in ups), [run(du1, LOCAL, u_['id'])['stored'] for u_ in ups])
        def wait_held(ms=6000):
            t_ = 0
            while t_ < ms and not held_gets(): du2.wait_for_timeout(200); t_ += 200
            return len(held_gets())
        srv.mode['user-U'] = 'gethold'; drop_held(); g0 = len(srv.gets)
        cu2, du2 = device(b, H, 'u@zajil.test')          # the same account on a second device, the app in front
        run(du2, SYNC_BOUNDED); first = wait_held()      # its cycle pulls the rows; the pass after it asks for the first photo
        ok_ = run(du2, SYNC_BOUNDED)
        check('[down · never in the way] while a download hangs unanswered, a record cycle still completes', first >= 1 and ok_ is True, (first, ok_))
        most = first
        for _ in range(6):
            du2.wait_for_timeout(1200); most = max(most, len(held_gets()))     # time enough for a parallel pass to ask for more
            if not held_gets(): break
            release_gets(); wait_held(4000)
        mine = [g for g in srv.gets[g0:] if g[0] == 'user-U']
        check('[down · one at a time · M-parallel fails here] three photos to bring down, ONE request out at a time — the next asked only when the last is answered',
              most == 1 and len(mine) == 3, (most, len(mine)))
        got = run(du2, HELD_, [u_['id'] for u_ in ups]); same = [run(du2, LOCAL, u_['id'])['sha'] == run(du1, LOCAL, u_['id'])['sha'] for u_ in ups]
        check('[down · M-nodown fails here] with the bird\'s profile never opened, all three photos are on the second device, byte for byte', got == [True] * 3 and all(same), (got, same))
        exp = run(du2, "async (db, bird) => { let missing = null; const f = await db.exportAll({ onMissing: (n) => { missing = n; } }); return { missing, here: f.media.filter(m => m.birdId === bird).length }; }", bu)
        check('[down] an export on the second device is now complete: it carries the three photos, and none is missing', exp == {'missing': 0, 'here': 3}, exp)
        # in the background, nothing comes down
        u3 = run(du1, PHOTO, bu, 'u3.jpg'); cycle(du1); cycle(du1); n_ = len(srv.gets)
        pocket(du2, True); run(du2, SYNC_BOUNDED); du2.wait_for_timeout(2500)
        check('[down · M-hiddendown fails here] with the app in the background, a cycle pulls the new photo\'s row and NOTHING is downloaded', len(srv.gets) == n_ and run(du2, HELD_, [u3['id']]) == [False], (len(srv.gets) - n_))
        pocket(du2, False)
        # offline, nothing is even tried
        cu2.set_offline(True); n_ = len(srv.gets)
        off_ = du2.evaluate("() => navigator.onLine")
        st_ = run(du2, "async (db) => { await Promise.race([db.runPhotoPass({ manual: true }), new Promise(r => setTimeout(r, 10000))]); return db.photoSyncState(); }")
        check('[down · M-offlinedown fails here] offline (navigator.onLine false), the pass does not even try: no request, nothing left hanging, no failure counted, no backoff',
              off_ is False and len(srv.gets) == n_ and st_['inFlight'] is False and st_['failures'] == 0 and not st_['last']['failed'] and st_['last']['downloaded'] == 0,
              (off_, len(srv.gets) - n_, st_['inFlight'], st_['failures'], st_['last']))
        cu2.set_offline(False)
        run(du2, SYNC_BOUNDED); wait_held(4000)
        for _ in range(4):
            release_gets(); du2.wait_for_timeout(700)
        check('[down] back in front and online, it comes down', run(du2, HELD_, [u3['id']]) == [True], run(du2, HELD_, [u3['id']]))
        # a failed download: the pass stops on the photo backoff
        srv.mode['user-U'] = 'getfail'; u4 = run(du1, PHOTO, bu, 'u4.jpg'); cycle(du1); cycle(du1)
        run(du2, SYNC_BOUNDED); du2.wait_for_timeout(2500); st_ = run(du2, DSTATE); n_ = len(srv.gets)
        again = run(du2, "async (db) => { await Promise.race([db.runPhotoPass({}), new Promise(r => setTimeout(r, 10000))]); return db.photoSyncState().last; }")
        check('[down · same backoff · M-downnoback fails here] a failed download stops the pass on the photo backoff, and the next automatic pass waits',
              st_['failures'] >= 1 and st_['waitMs'] > 0 and again['skipped'] == 'backoff' and len(srv.gets) == n_ and run(du2, HELD_, [u4['id']]) == [False], (st_, again))
        # ═══ THE VIEWER ON A DEVICE WITHOUT THE BYTES: the fetching state, then the photo ═══
        srv.mode['user-U'] = 'gethold'; drop_held(); u5 = run(du1, PHOTO, bu, 'u5.jpg'); cycle(du1); cycle(du1)
        run(du2, SYNC_BOUNDED); wait_held(4000)          # its background download is held
        du2.goto(ROOT + 'bird/?id=' + bu, wait_until='load'); waits(du2, '[data-testid=media-open]'); du2.wait_for_timeout(800)
        k5 = du2.evaluate("(name) => [...document.querySelectorAll('[data-testid=media-tile]')].findIndex(t => (t.querySelector('[data-testid=media-elsewhere]') || {}).dataset?.where === 'fetching')", 'u5.jpg')
        if k5 >= 0: du2.locator('[data-testid=media-tile]').nth(k5).locator('[data-testid=media-open]').click()
        waits(du2, '[data-testid=viewer]'); du2.wait_for_timeout(500)
        st5 = du2.evaluate("() => { const e = document.querySelector('[data-testid=viewer-state]'); return e ? { where: e.dataset.where, text: e.innerText.split('\\n')[0].trim() } : null; }"); ty = typo(du2)
        check('[viewer · bytes not here] a photo whose bytes are not on this device opens saying «جارٍ تنزيل الصورة…», in a face that has Arabic',
              k5 >= 0 and st5 == {'where': 'fetching', 'text': 'جارٍ تنزيل الصورة…'} and not ty, (k5, st5, ty[:3]))
        release_gets()
        try: du2.wait_for_function("() => { const i = document.querySelector('[data-testid=viewer-img]'); return i && i.naturalWidth > 0; }", timeout=8000); shown = True
        except Exception: shown = False
        check('[viewer · bytes not here] …and becomes the photo when its bytes land', shown)
        du2.keyboard.press('Escape'); du2.wait_for_timeout(300)
        # ═══ AN OPEN PROFILE FOLLOWS A PULL (measured 2026-11-20: it did not) ═══
        tiles0 = du2.locator('[data-testid=media-tile]').count()
        u6 = run(du1, PHOTO, bu, 'u6.jpg'); cycle(du1); cycle(du1)
        run(du2, SYNC_BOUNDED); du2.wait_for_timeout(2500)
        tiles1 = du2.locator('[data-testid=media-tile]').count()
        check('[open profile · M-nosyncload fails here] a photo pulled while the bird\'s profile is open appears on it, without reopening', tiles1 == tiles0 + 1, (tiles0, tiles1))
        release_gets()
        # ═══ A STUCK DOWNLOAD DOES NOT HOLD THE QUEUE (RULED 2026-11-20): given up after PHOTO_DOWNLOAD_TIMEOUT_MS ═══
        TMO = run(du2, "async (db) => db.PHOTO_DOWNLOAD_TIMEOUT_MS")
        # first let the second device finish whatever it still had to bring down, so the pass below starts with the two
        # new photos at the head of its queue (a file still inside its own backoff is passed over, as designed)
        home(du2, H); srv.mode['user-U'] = 'ok'; drop_held(); run(du2, SYNC_BOUNDED); run(du2, PASS)
        srv.mode['user-U'] = 'getholdfirst'; srv.held_first = False
        s1 = run(du1, PHOTO, bu, 's1.jpg'); s2 = run(du1, PHOTO, bu, 's2.jpg'); cycle(du1); cycle(du1)
        run(du2, PASS); run(du2, SYNC_BOUNDED); t0 = time.time(); got = None
        while time.time() - t0 < TMO / 1000 + 25:
            du2.wait_for_timeout(1000); got = run(du2, HELD_, [s1['id'], s2['id']])
            if got == [False, True]: break
        took = round(time.time() - t0)
        check(f'[down · stuck · M-notimeout fails here] a download that never answers is given up after {TMO // 1000} s, and the next photo comes down without it',
              got == [False, True] and TMO / 1000 - 5 <= took <= TMO / 1000 + 25, (got, took, TMO, [g[2][:8] for g in srv.gets if g[0] == 'user-U'][-4:], s1['id'][:8], s2['id'][:8], len(held_gets())))
        st_ = run(du2, DSTATE)
        check('[down · stuck] the pass did not stop for it: one download given up, the other done, no failure counted against the pass',
              st_['failures'] == 0 and (st_['last'] or {}).get('timedOut') == 1 and (st_['last'] or {}).get('downloaded') == 1, st_)
        for h in held_gets():
            srv.held.remove(h)
            try: h[0].fulfill(status=200, content_type=h[1]['type'], body=h[1]['bytes'])
            except Exception: pass            # the page gave up on it already
        srv.mode['user-U'] = 'ok'
        cu1.close(); cu2.close()

        # ═══ NEVER ANOTHER ACCOUNT'S FOLDER, and nothing without an account ═══
        check('[owner] every upload and download in this run was addressed to the signed-in user’s own folder', all(p_[0] == p_[1] for p_ in srv.posts) and all(g[0] == g[1] for g in srv.gets), [x for x in srv.posts if x[0] != x[1]][:2])
        cg = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900})); cg.route(f'{STUB}/**', handler)
        cg.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
        dg = cg.new_page(); dg.errs = []; dg.on('pageerror', lambda e, _p=dg: dg.errs.append(perr(e, _p))); PAGES.append(dg); home(dg, H)
        n = len(srv.posts); bg = run(dg, BIRD, 'بلا حساب'); run(dg, PHOTO, bg, 'x.jpg'); st = run(dg, "async (db) => { await db.runPhotoPass(); return db.photoSyncState(); }")
        check('[signed out] a device with no session sends no photo anywhere', len(srv.posts) == n and st['last']['skipped'] == 'hidden', st['last'])
        cg.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
