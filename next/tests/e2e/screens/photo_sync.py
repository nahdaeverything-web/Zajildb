"""PHOTO SYNC, STAGE 1 (RULED 2026-11-18): a photo taken on one device appears on the other when that bird is opened.

Up: after a record cycle the coordinator starts a pass that uploads, one at a time, every media record that holds
bytes and is not marked `stored`; record sync never waits for it. Down: the other device fetches the bytes when the
bird's profile first draws the row, and keeps them. A failed, refused or bucket-less upload leaves the bytes on the
device exactly as they were, and never loops hot. Harness build; the table AND the storage API are stubs; the net armed.

    python3 tests/e2e/screens/photo_sync.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import hashlib
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
        self.rows = {}; self.seq = 0; self.objects = {}; self.posts = []; self.gets = []; self.held = []
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
            if mode == 'gethold': srv.held.append((route, o)); return
            if mode == 'getportal': route.fulfill(status=200, content_type='text/html', body='<html>sign in to the wifi</html>'); return
            route.fulfill(status=200, content_type=o['type'], body=o['bytes']); return
        err(route, 400, 'InvalidRequest', 'unexpected'); return
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in rows])); return
    c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); rows = srv.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def device(b, H, email):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
    ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email); return ctx, pg
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
        cb, dbb = device(b, H, 'a@zajil.test'); run(dbb, SYNC); before = run(dbb, LOCAL, ph['id'])
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
        cf, df = device(b, H, 'e@zajil.test'); run(df, SYNC); srv.mode['user-E'] = 'getfail'; g0 = len(srv.gets)
        df.goto(ROOT + 'bird/?id=' + birde, wait_until='load'); waits(df, '[data-testid=media-elsewhere][data-where=failed]')
        text = (df.locator('[data-testid=media-elsewhere]').all_inner_texts() or [''])[0].strip(); ty = typo(df)
        run(df, "async (db, id) => { for (let i = 0; i < 5; i++) await db.fetchPhotoBytes(id); }", pe['id'])
        check('[down · failed] a download that fails says so on the tile', text == 'تعذّر تنزيل الصورة — ستُعاد المحاولة عند فتحها', text)
        check('[typography] «تعذّر تنزيل الصورة…» is drawn in a face that has Arabic', bool(text) and not ty, ty[:3])
        check('[down · failed] …and five more asks in the same visit send nothing: one GET in all', len(srv.gets) - g0 == 1, srv.gets[g0:])
        check('[down · failed] the record on that device is untouched: marker there, no bytes, nothing removed', (lambda x: x and x['size'] is None and bool(x['stored']))(run(df, LOCAL, pe['id'])))
        srv.held.clear(); srv.mode['user-E'] = 'gethold'; df.goto(ROOT + 'bird/?id=' + birde, wait_until='load')
        got = waits(df, '[data-testid=media-elsewhere][data-where=fetching]'); text = (df.locator('[data-testid=media-elsewhere]').all_inner_texts() or [''])[0].strip(); ty = typo(df)
        check('[down · fetching] while the bytes are on their way the tile says «جارٍ تنزيل الصورة…», in a face that has Arabic', got and text == 'جارٍ تنزيل الصورة…' and not ty, (got, text, ty[:3]))
        srv.mode['user-E'] = 'ok'
        for route, o in srv.held: route.fulfill(status=200, content_type=o['type'], body=o['bytes'])
        srv.held.clear()
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
        cl, dl = device(b, H, 'k@zajil.test'); run(dl, SYNC); dl.goto(ROOT + 'bird/?id=' + birdk, wait_until='load')
        got, text, ty = tile_text(dl, 'pending')
        check('[file · not uploaded] a document on another device and not uploaded yet says «الملف على جهاز آخر ولم يُرفع بعد», in a face that has Arabic',
              got and text == 'الملف على جهاز آخر ولم يُرفع بعد' and not ty, (got, text, ty[:3]))
        srv.mode['user-K'] = 'ok'; run(dk, SYNC); run(dk, PASS); run(dk, SYNC)
        check('[file · setup] the document is stored: a PDF is on the allow-list', ('user-K', pk['id']) in srv.objects and srv.objects[('user-K', pk['id'])]['type'] == 'application/pdf', list(srv.objects)[-1:])
        run(dl, SYNC); srv.held.clear(); srv.mode['user-K'] = 'gethold'; dl.goto(ROOT + 'bird/?id=' + birdk, wait_until='load')
        got, text, ty = tile_text(dl, 'fetching')
        check('[file · fetching] while a document is on its way the tile says «جارٍ تنزيل الملف…», in a face that has Arabic',
              got and text == 'جارٍ تنزيل الملف…' and not ty, (got, text, ty[:3]))
        srv.mode['user-K'] = 'getfail'
        for route, o in srv.held: err(route, 404, 'NoSuchKey', 'Object not found')
        srv.held.clear()
        got, text, ty = tile_text(dl, 'failed')
        check('[file · failed] a document whose download fails says «تعذّر تنزيل الملف — ستُعاد المحاولة عند فتحه», in a face that has Arabic',
              got and text == 'تعذّر تنزيل الملف — ستُعاد المحاولة عند فتحه' and not ty, (got, text, ty[:3]))
        srv.mode['user-K'] = 'ok'; dl.goto(ROOT + 'bird/?id=' + birdk, wait_until='load'); arrived = waits(dl, '[data-testid=media-file]')
        lk = run(dl, LOCAL, pk['id'])
        check('[file] opening the bird again fetches the document, and its bytes are kept', arrived and lk is not None and lk['size'] == pk['size'] and lk['type'] == 'application/pdf', (arrived, lk))
        ck.close(); cl.close()

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
