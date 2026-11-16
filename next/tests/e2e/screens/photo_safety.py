"""THE PHOTO INVARIANT (RULED 2026-11-16): a media record that holds bytes is never replaced by one that does not.

Photos have no server copy (DF-4), so the bytes on a device are the only ones.

  RF-23  a sync cycle used to remove the bytes of every photo from the device that took it: the device's own pushed
         media row came back in the pull, metadata only (§7), and was written over the stored record.

  RF-24  an import used to hand a media row with no dataURL to fetch(), and store what came back — a not-found page —
         over the real photo. Such a row is now rejected: never fetched, never written, counted, and said.

  RF-4   a device holding media rows without bytes could not export or share at all: the export threw on the first
         such row. It now carries the photos it has, and says how many it does not.

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

        # ═══ RF-24 — an import never writes a media row without bytes, and never fetches one ═══
        c3, D = device(b, H, None); run(D, ADD, 'قديم', 'on-old.png', 'xx'); run(D, ADD, 'جديد', 'on-new.png', 'yyy')
        full = run(D, "async (db) => await db.exportAll()")
        fetched = []; D.on('request', lambda r: fetched.append(r.url) if not r.url.startswith(('data:', 'blob:')) and '/_next/' not in r.url and '_rsc=' not in r.url else None)   # the app's own lazy chunks and its route prefetches (…__PAGE__.txt?_rsc=…, fired by links on screen, timing-dependent: gate-21 caught them) are not the subject
        bare = json.loads(json.dumps(full)); kinds = [None, 'undefined']
        for m, k in zip(bare['media'], kinds):
            if k is None: m.pop('dataURL', None)
            else: m['dataURL'] = k
        bare['media'].append({'id': 'media-never-seen', 'birdId': bare['birds'][0]['id'], 'kind': 'photo', 'subtype': 'body', 'name': 'ghost.png', 'addedAt': '2026-01-01T00:00:00.000Z', 'dataURL': 'https://example.invalid/ghost.png'})
        bare['media'].append({'id': 'media-never-seen-2', 'birdId': bare['birds'][0]['id'], 'kind': 'photo', 'subtype': 'body', 'name': 'ghost-2.png', 'addedAt': '2026-01-01T00:00:00.000Z', 'dataURL': 'ghost-2.png'})
        for mode in ('merge', 'replace'):
            fetched.clear(); counts = run(D, "async (db, f, mode) => { try { return await db.importAll(f, mode); } catch (e) { return { error: String(e.message).slice(0, 120) }; } }", bare, mode); got = media(D)   # non-raising: a mutant must fail a named check
            check(f'[RF-24 · M-rf24 fails here] {mode}: a file whose media rows carry no bytes — no dataURL, the text «undefined», a file name, an address — leaves both photos with their bytes and stores nothing new',
                  got == [['on-new.png', 3], ['on-old.png', 2]], got)
            check(f'[RF-24 · M-rf24 fails here] {mode}: …all four rows are rejected and counted, and NOTHING was fetched for them', counts.get('mediaRejected') == 4 and counts.get('media') == 0 and not fetched, (counts, fetched[:3]))
        counts = run(D, "async (db, f) => db.importAll(f, 'replace')", full)
        check('[RF-24] a file whose rows DO carry bytes still imports them', counts['media'] == 2 and counts['mediaRejected'] == 0 and media(D) == [['on-new.png', 3], ['on-old.png', 2]], (counts, media(D)))
        # through the screen: the import says how many it rejected
        D.goto(ROOT + 'tools/import/', wait_until='load'); D.wait_for_selector('[data-testid=import-mode]', timeout=15000)
        D.set_input_files('[data-testid=file-input]', files=[{'name': 'file.json', 'mimeType': 'application/json', 'buffer': json.dumps(bare).encode()}]); D.click('[data-testid=import-file]')
        try: D.wait_for_selector('[data-testid=toast]', timeout=15000)
        except PWTimeout: pass
        said = digits(' '.join(D.locator('[data-testid=toast]').all_inner_texts())); typo = D.evaluate(SCAN)
        check('[RF-24 · wording] the import says so: «عدد الصور والوثائق التي لم تُستورد لأن الملف لا يحمل محتواها: 4.»', 'عدد الصور والوثائق التي لم تُستورد لأن الملف لا يحمل محتواها: 4.' in said, said)
        check('[typography] that message is drawn in a face that has Arabic', bool(said) and not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        # with the photo set's P2: a dropped bird's photo that the file lists WITHOUT bytes is not "carried" — it goes with its bird, and the question counts it
        drop = json.loads(json.dumps(bare)); drop['birds'] = [x for x in drop['birds'] if x['name'] == 'قديم']; drop['media'] = [m for m in drop['media'] if m['name'] in ('on-new.png', 'on-old.png')]
        lost = run(D, "async (db, f) => db.replaceMediaLoss(f)", drop); run(D, "async (db, f) => db.importAll(f, 'replace')", drop)
        check('[RF-24 + P2] a replace that drops «جديد» and lists its photo without bytes: the photo is counted as lost (1) and goes with the bird; the staying bird\'s photo keeps its bytes', lost == 1 and media(D) == [['on-old.png', 2]], (lost, media(D)))
        # SEEN, not ruled: a merge-import skips a media row the device already has — even when the device's row has no bytes and the file's has them
        srv2 = Server(); c4, E = device(b, H, srv2); run(E, ADD, 'طير', 'p.png', 'xyz'); withbytes = run(E, "async (db) => await db.exportAll()")
        c5, F = device(b, H, srv2); run(E, SYNC); run(F, SYNC); f0 = media(F); run(F, "async (db, f) => db.importAll(f, 'merge')", withbytes); f1 = media(F)
        check('[seen · not ruled] a second device holding the row without bytes, merge-importing the first device\'s export WITH the bytes: the row is skipped and the bytes do not arrive', f0 == [['p.png', 'NO BYTES']] and f1 == [['p.png', 'NO BYTES']], (f0, f1))
        c3.close(); c4.close(); c5.close()

        # ═══ RF-4 — a device holding rows without bytes can still export, and says what is not in the file ═══
        srv3 = Server(); c6, G1 = device(b, H, srv3); run(G1, ADD, 'أب', 'sire-1.png', 'aa'); run(G1, ADD, 'أب', 'sire-2.png', 'bbb'); run(G1, SYNC)
        c7, G2 = device(b, H, srv3); run(G2, SYNC)
        run(G2, """async (db) => { const sire = db.allBirds().find(x => x.name === 'أب'); await db.saveBird(db.newBird({ name: 'ابن', sex: 'cock', sireId: sire.id }));
            const kid = db.allBirds().find(x => x.name === 'ابن'); await db.addMedia(kid.id, 'photo', 'body', 'kid.png', new Blob(['cccc'], { type: 'image/png' })); }""")
        check('[RF-4] the second device holds two rows without bytes and one photo of its own', media(G2) == [['kid.png', 4], ['sire-1.png', 'NO BYTES'], ['sire-2.png', 'NO BYTES']], media(G2))
        TRY = """async (db, which) => { let missing = null; const onMissing = (n) => { missing = n; }; try {
            const kid = db.allBirds().find(x => x.name === 'ابن');
            const r = which === 'blob' ? JSON.parse(await (await db.exportAllBlob({ onMissing })).text()) : which === 'share' ? await db.exportBirdWithAncestry(kid.id, { includeRaces: true, includeMedia: true, onMissing }) : await db.exportAll({ onMissing });
            return { ok: true, birds: r.birds.length, media: r.media.map(m => [m.name, typeof m.dataURL === 'string' && m.dataURL.startsWith('data:')]).sort(), missing }; }
          catch (e) { return { ok: false, error: String(e && e.message || e).slice(0, 120) }; } }"""
        WANT = {'ok': True, 'birds': 2, 'media': [['kid.png', True]], 'missing': 2}
        for which, label in (('all', 'exportAll()'), ('blob', 'exportAllBlob() — what «تصدير الكل» writes'), ('share', 'exportBirdWithAncestry() — what «مشاركة» writes')):
            r = run(G2, TRY, which)
            check(f'[RF-4 · M-rf4 fails here] {label}: it answers with a file that carries the one photo this device has, every row in it with its bytes, and reports 2 not here', r == WANT, r)
        G2.goto(ROOT + 'tools/', wait_until='load'); G2.wait_for_selector('[data-testid=tools-list]', timeout=15000); G2.wait_for_timeout(800); G2.locator('[data-row=export] summary').click(); G2.wait_for_selector('[data-testid=export-all]', timeout=8000)
        got = None
        try:
            with G2.expect_download(timeout=10000) as dl: G2.click('[data-testid=export-all]')
            got = json.loads(open(dl.value.path(), encoding='utf-8').read())
        except PWTimeout: pass
        G2.wait_for_timeout(600); said = digits(' '.join(G2.locator('[data-testid=toast]').all_inner_texts())); typo = G2.evaluate(SCAN)
        check('[RF-4 · M-rf4 fails here] «تصدير الكل» on the second device downloads a file: 2 birds, the one photo', bool(got) and len(got['birds']) == 2 and [m['name'] for m in got['media']] == ['kid.png'], said)
        check('[RF-4 · wording] …and says «عدد الصور والوثائق غير الموجودة على هذا الجهاز، وهي لذلك ليست في الملف: 2.»', 'عدد الصور والوثائق غير الموجودة على هذا الجهاز، وهي لذلك ليست في الملف: 2.' in said and 'تعذّر' not in said, said)
        check('[typography] that message is drawn in a face that has Arabic', bool(said) and not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        # the file is a good file: a fresh device imports it with nothing rejected
        c8, G3 = device(b, H, None)
        r = run(G3, "async (db, f) => { try { return await db.importAll(f, 'merge'); } catch (e) { return { error: String(e.message) }; } }", got or {})
        check('[RF-4 + RF-24] the file it wrote imports on a fresh device with no row rejected: it never carries a media row without bytes', r.get('birds') == 2 and r.get('media') == 1 and r.get('mediaRejected') == 0 and media(G3) == [['kid.png', 4]], r)
        # a device with every photo's bytes reports none missing
        r = run(G3, TRY.replace("const kid = db.allBirds().find(x => x.name === 'ابن');", "const kid = db.allBirds()[0];"), 'all'); check('[RF-4] a device that has the bytes of every photo it holds reports 0 not here', r.get('ok') and r.get('missing') == 0 and r.get('media') == [['kid.png', True]], r)
        c6.close(); c7.close(); c8.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
