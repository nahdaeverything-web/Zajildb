#!/usr/bin/env python3
"""THE PHOTO VIEWER (ORDERED 2026-11-20, found by Samir on both devices: a tap on a photo did nothing).

A tap on a photo's tile — the profile, or a thumbnail in the edit form's strip — opens it full screen; a swipe moves
between the bird's photos (right-to-left), two fingers zoom, and a tap, a swipe down or the back button closes it. The
delete button stays the delete control, and a tap on the photo never reaches it. A document opens in the browser's own
viewer. A phone's screen (390 px) with touch: every gesture is a real touch sequence sent to the browser, not a click.
The no-bytes case (the fetching state, then the photo) needs the storage stub: tests/e2e/screens/photo_sync.py.
Local only: no sync configuration, nothing leaves the page.

    python3 tests/e2e/screens/photo_viewer.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import os, re, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _typography import SCAN                 # noqa: E402
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:400]) if not ok and d != '' else ''}")
def digits(s_): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s_ or '')
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))

SETUP = """async (db) => {
    const bird = await db.saveBird(db.newBird({ name: 'طير العارض', sex: 'cock', loftId: db.currentLoft() && db.currentLoft().id }));
    const shot = async (w, h, hue) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d');
        for (let i = 0; i < 200; i++) { x.fillStyle = `hsl(${(hue + i * 9) % 360} 60% 50%)`; x.fillRect((i * 37) % w, (i * 23) % h, 40, 30); }
        return new Promise(r => c.toBlob(r, 'image/jpeg', 0.85)); };
    for (const [w, h, hue, name] of [[300, 200, 10, 'wide.jpg'], [200, 300, 120, 'tall.jpg'], [240, 240, 220, 'square.jpg']])
        await db.addMedia(bird.id, 'photo', 'body', name, await shot(w, h, hue));
    const pdf = '%PDF-1.4\\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\\ntrailer<</Root 1 0 R>>\\n%%EOF';
    await db.addMedia(bird.id, 'document', 'other', 'papers.pdf', new Blob([pdf], { type: 'application/pdf' }));
    return bird.id; }"""
COUNT = "async (db, id) => (await db.mediaForBird(id)).length"
VIEW = """() => { const v = document.querySelector('[data-testid=viewer]'); if (!v) return null; const i = v.querySelector('[data-testid=viewer-img]'); const r = v.getBoundingClientRect();
    const c = v.querySelector('[data-testid=viewer-count]');
    return { index: +v.dataset.index, count: c ? c.innerText : '', countDir: c ? getComputedStyle(c).direction : '', natural: i && i.naturalWidth ? [i.naturalWidth, i.naturalHeight] : null,
             scale: +v.querySelector('[data-testid=viewer-stage]').dataset.scale, full: Math.round(r.width) === innerWidth && Math.round(r.height) === innerHeight }; }"""
TILES = "() => [...document.querySelectorAll('[data-testid=media-open]')].map(t => { const i = t.querySelector('img'); return i && i.naturalWidth ? [i.naturalWidth, i.naturalHeight] : null; })"

class Touch:
    """Real touch sequences through the browser's input layer (CDP), so the page sees touch → pointer events."""
    def __init__(self, ctx, pg): self.cdp = ctx.new_cdp_session(pg); self.pg = pg
    def send(self, typ, pts): self.cdp.send('Input.dispatchTouchEvent', {'type': typ, 'touchPoints': [{'x': x, 'y': y, 'id': k} for k, (x, y) in enumerate(pts)]})
    def drag(self, x0, y0, x1, y1, steps=10):
        self.send('touchStart', [(x0, y0)])
        for k in range(1, steps + 1): self.send('touchMove', [(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps)]); self.pg.wait_for_timeout(16)
        self.send('touchEnd', []); self.pg.wait_for_timeout(350)
    def pinch(self, cx, cy, d0, d1, steps=10):
        self.send('touchStart', [(cx - d0 / 2, cy), (cx + d0 / 2, cy)])
        for k in range(1, steps + 1):
            d = d0 + (d1 - d0) * k / steps; self.send('touchMove', [(cx - d / 2, cy), (cx + d / 2, cy)]); self.pg.wait_for_timeout(16)
        self.send('touchEnd', []); self.pg.wait_for_timeout(350)

def wait_view(pg, want=True, timeout=4000):
    try: pg.wait_for_selector('[data-testid=viewer]', state='visible' if want else 'detached', timeout=timeout); return True
    except Exception: return False
def wait_img(pg, timeout=4000):
    try: pg.wait_for_function("() => { const i = document.querySelector('[data-testid=viewer-img]'); return i && i.naturalWidth > 0; }", timeout=timeout); return True
    except Exception: return False
def tap(loc):
    """Scroll the element to the middle of the screen and tap it; never raise (a mutant must fail AT a check)."""
    try: loc.evaluate("e => e.scrollIntoView({ block: 'center' })"); loc.page.wait_for_timeout(150); loc.tap(timeout=5000); return True
    except Exception: return False
def close_if_open(pg):
    if pg.locator('[data-testid=viewer]').count():
        try: pg.locator('[data-testid=viewer-close]').click(timeout=3000)
        except Exception: pg.keyboard.press('Escape')        # no close button (a mutant): never a traceback
        wait_view(pg, False)

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        # the full Chromium in its new headless mode: it has the browser's own PDF viewer, which the headless shell lacks
        # (there a PDF can only download, measured 2026-11-20) — and the document check is about that viewer
        b = p.chromium.launch(channel='chromium')
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e, _p=pg: errs.append(perr(e, _p)))
        downloads = []; pg.on('download', lambda d: downloads.append(d.suggested_filename))
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_function('window.__zajilReady')
        bird = run(pg, SETUP); T = Touch(ctx, pg)
        run(pg, "async (db) => { await db.setSetting('numerals', 'eastern'); }")   # the counter must stay Western on a device set to Eastern numerals
        PROFILE = ROOT + 'bird/?id=' + bird
        pg.goto(PROFILE, wait_until='load')
        try: pg.wait_for_function("() => [...document.querySelectorAll('[data-testid=media-open] img')].filter(i => i.naturalWidth > 0).length === 3", timeout=8000)
        except Exception: pass
        tiles = pg.evaluate(TILES)
        check('[setup] the profile shows three photos and one document', len(tiles) == 3 and all(tiles) and pg.locator('[data-testid=media-file]').count() == 1, tiles)

        # ── OPEN ON A TAP ──
        tap(pg.locator('[data-testid=media-open]').nth(1))
        opened = wait_view(pg) and wait_img(pg); v = pg.evaluate(VIEW)
        check('[open · M-noopen fails here] a tap on the second photo\'s tile opens THAT photo full screen',
              opened and v and v['natural'] == tiles[1] and v['full'], (v, tiles))
        check('[counter · M-countnumerals fails here] the counter reads «2 / 3» — Western digits, left to right — on a device set to Eastern numerals',
              bool(v) and v['count'] == '2 / 3' and v['countDir'] == 'ltr', v)
        ty = [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]
        check('[typography] the viewer\'s count is drawn in a face that has Arabic', opened and not ty, ty[:3])

        # ── SWIPE BETWEEN THE BIRD'S PHOTOS (right-to-left: the next photo comes from the left) ──
        T.drag(110, 420, 300, 430); wait_img(pg); v1 = pg.evaluate(VIEW)
        T.drag(300, 420, 110, 430); wait_img(pg); v2 = pg.evaluate(VIEW)
        check('[swipe · M-noswipe fails here] a swipe to the right brings the next photo, a swipe to the left the previous one',
              bool(v1 and v2) and v1['index'] == 2 and v1['natural'] == tiles[2] and v2['index'] == 1 and v2['natural'] == tiles[1], (v1, v2))

        # ── PINCH TO ZOOM ──
        T.pinch(195, 420, 80, 260); v3 = pg.evaluate(VIEW)
        check('[pinch · M-nopinch fails here] two fingers spread apart zoom the photo in (×1.5 or more), and it stays open', bool(v3) and v3['scale'] >= 1.5, v3)
        # RULED 2026-11-20: zoomed in, a tap does nothing; a double tap returns to 1×; at 1× a tap closes
        pg.touchscreen.tap(195, 600); pg.wait_for_timeout(600); v4 = pg.evaluate(VIEW)
        check('[zoomed · M-zoomtapclose fails here] zoomed in, a tap does NOT close the viewer — and it stays zoomed', bool(v4) and v4['scale'] == v3['scale'], (v3 and v3['scale'], v4))
        pg.touchscreen.tap(195, 600); pg.wait_for_timeout(110); pg.touchscreen.tap(195, 600); pg.wait_for_timeout(600); v5 = pg.evaluate(VIEW)
        check('[zoomed · M-nodoubletap fails here] a double tap returns it to 1×, still open', bool(v5) and v5['scale'] == 1, v5)

        # ── CLOSE: a tap · a swipe down · the back button ──
        pg.touchscreen.tap(195, 600); gone = wait_view(pg, False)
        check('[close · tap] a tap closes it; the profile is still there', gone and pg.url == PROFILE and pg.locator('[data-testid=gallery]').count() == 1, pg.url)
        tap(pg.locator('[data-testid=media-open]').nth(0)); wait_view(pg); wait_img(pg)
        T.drag(195, 300, 200, 560); gone = wait_view(pg, False)
        check('[close · swipe down] a swipe down closes it', gone)
        tap(pg.locator('[data-testid=media-open]').nth(2)); wait_view(pg); wait_img(pg)
        try: pg.go_back(wait_until='commit', timeout=5000)
        except Exception: pass
        gone = wait_view(pg, False); pg.wait_for_timeout(600)
        check('[close · back · M-noback fails here] the back button closes it — and the profile stays, nothing navigates',
              gone and pg.url == PROFILE and pg.locator('[data-testid=gallery]').count() == 1, pg.url)
        # the close button: there in the top corner, on a phone and on a desktop screen (RULED 2026-11-20)
        def close_btn():
            b_ = pg.locator('[data-testid=viewer-close]'); bb = b_.bounding_box() if b_.count() else None
            return bb and b_.is_visible() and bb['width'] >= 44 and bb['height'] >= 44 and bb['y'] <= 60 and (bb['x'] <= 80 or bb['x'] + bb['width'] >= pg.viewport_size['width'] - 80) and [round(bb['x']), round(bb['y']), round(bb['width'])]
        tap(pg.locator('[data-testid=media-open]').nth(0)); wait_view(pg); phone = close_btn(); close_if_open(pg)
        pg.set_viewport_size({'width': 1280, 'height': 800}); pg.wait_for_timeout(300)
        try: pg.locator('[data-testid=media-open]').nth(0).click(timeout=5000)
        except Exception: pass
        wait_view(pg); desk = close_btn(); close_if_open(pg); pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(300)
        check('[close button · M-noclosebtn fails here] a close button, 44 px or more, in the top corner — on a phone (390 px) and on a desktop screen (1280 px)', bool(phone) and bool(desk), (phone, desk))
        tap(pg.locator('[data-testid=media-open]').nth(0)); wait_view(pg); close_if_open(pg); wait_view(pg, False); pg.wait_for_timeout(300)
        try: pg.go_back(wait_until='commit', timeout=5000)
        except Exception: pass
        pg.wait_for_timeout(800)
        check('[close · back] closed by its own button, the viewer leaves no history behind: the next back leaves the profile', pg.url != PROFILE, pg.url)
        pg.goto(PROFILE, wait_until='load'); pg.wait_for_selector('[data-testid=media-open]')
        try: pg.wait_for_function("() => [...document.querySelectorAll('[data-testid=media-open] img')].filter(i => i.naturalWidth > 0).length === 3", timeout=8000)
        except Exception: pass

        # ── A TAP ON THE PHOTO NEVER DELETES ──
        n0 = run(pg, COUNT, bird); results = []
        tile = pg.locator('[data-testid=media-tile]', has=pg.locator('[data-testid=media-open]')).nth(0)   # a PHOTO's tile: the order follows the ids
        def steady_boxes():
            # read the tile and its delete button where they ARE: scrolled to the middle, and the page done moving — a
            # banner that appears late above the gallery moves everything down after a first reading (seen under a gate)
            tile.evaluate("e => e.scrollIntoView({ block: 'center' })"); last = None
            for _ in range(30):
                pg.wait_for_timeout(120); now = (tile.bounding_box(), tile.locator('[data-testid=media-delete]').bounding_box())
                if now == last: return now
                last = now
            return last
        tb, db_ = steady_boxes()
        # the corners 8 px in (the tile's corners are rounded: a point nearer is outside the photo); the top corner at the
        # delete button's end is the button itself, so the points beside and under the button stand in for it
        points = {'centre': (tb['x'] + tb['width'] / 2, tb['y'] + tb['height'] / 2),
                  'corner, foot (start)': (tb['x'] + tb['width'] - 8, tb['y'] + tb['height'] - 8), 'corner, foot (end)': (tb['x'] + 8, tb['y'] + tb['height'] - 8),
                  'corner, top (start)': (tb['x'] + tb['width'] - 8, tb['y'] + 8),
                  'beside the delete button': (db_['x'] + db_['width'] + 3, db_['y'] + db_['height'] / 2), 'under the delete button': (db_['x'] + db_['width'] / 2, db_['y'] + db_['height'] + 3)}
        for name in list(points):
            tb, db_ = steady_boxes()          # again before every tap: closing the viewer may have moved the page
            x, y = {'centre': (tb['x'] + tb['width'] / 2, tb['y'] + tb['height'] / 2),
                    'corner, foot (start)': (tb['x'] + tb['width'] - 8, tb['y'] + tb['height'] - 8), 'corner, foot (end)': (tb['x'] + 8, tb['y'] + tb['height'] - 8),
                    'corner, top (start)': (tb['x'] + tb['width'] - 8, tb['y'] + 8),
                    'beside the delete button': (db_['x'] + db_['width'] + 3, db_['y'] + db_['height'] / 2), 'under the delete button': (db_['x'] + db_['width'] / 2, db_['y'] + db_['height'] + 3)}[name]
            pg.touchscreen.tap(x, y); opened = wait_view(pg, timeout=2500); pg.wait_for_timeout(200)
            asked = pg.locator('[data-testid=dialog]').count() > 0          # the delete button asks before it deletes
            if asked: pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(200)
            results.append((name, opened, asked, run(pg, COUNT, bird))); close_if_open(pg)
        said = ' '.join(pg.locator('[data-testid=toast]').all_inner_texts())
        check('[delete · M-delcover fails here] a tap anywhere on the photo — its centre, three corners, beside and under the delete button — opens the viewer, and never deletes nor even asks to',
              all(o and not a for _, o, a, _ in results) and all(c == n0 for _, _, _, c in results) and 'تم الحذف' not in said and 'تراجع' not in said, (n0, results, said[:120]))
        tap(tile.locator('[data-testid=media-delete]')); pg.wait_for_timeout(400)
        asked = pg.locator('[data-testid=dialog]').count() > 0
        if asked: pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(600)
        undo = pg.locator('[data-testid=toast] button').count() >= 1
        check('[delete] the X is still the delete control: a tap on it asks, and on «حذف» deletes that photo with the undo offered', asked and run(pg, COUNT, bird) == n0 - 1 and undo, (asked, run(pg, COUNT, bird), undo))
        if undo: pg.locator('[data-testid=toast] button').first.click(); pg.wait_for_timeout(600)
        check('[delete] …and the undo puts it back', run(pg, COUNT, bird) == n0, run(pg, COUNT, bird))

        # ── A DOCUMENT OPENS IN THE BROWSER'S OWN VIEWER ──
        pg.goto(PROFILE, wait_until='load'); pg.wait_for_selector('[data-testid=media-file]')
        dt = pg.evaluate("() => { const a = document.querySelector('[data-testid=media-file]'), t = a.closest('[data-testid=media-tile]'); const r = a.getBoundingClientRect(), q = t.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(q.width), Math.round(q.height)]; }")
        check('[document · M-doctiny fails here] the document\'s whole tile is its tap target, not only the 📄 (it was 22 × 21 px)', dt[0] == dt[2] and dt[1] == dt[3], dt)
        opened_doc = None
        try:
            with ctx.expect_page(timeout=5000) as newp: tap(pg.locator('[data-testid=media-file]'))
            opened_doc = newp.value; opened_doc.wait_for_load_state('load', timeout=5000)
        except Exception: pass
        pg.wait_for_timeout(800)
        shown_as = opened_doc.evaluate("() => { const e = document.querySelector('embed'); return e ? e.type : document.contentType; }") if opened_doc else None
        check('[document · M-nodoc fails here] a tap on the document opens it in the browser\'s own viewer — a page of its own showing the PDF — and nothing is downloaded',
              bool(opened_doc) and opened_doc.url.startswith('blob:') and shown_as == 'application/pdf' and not downloads and pg.locator('[data-testid=viewer]').count() == 0, (opened_doc and opened_doc.url, shown_as, downloads))
        if opened_doc: opened_doc.close()

        # ── THE EDIT FORM'S STRIP ──
        pg.goto(ROOT + 'bird/edit/?id=' + bird, wait_until='load'); pg.wait_for_selector('[data-testid=photo-strip]')
        try: pg.wait_for_function("() => [...document.querySelectorAll('[data-testid=strip-saved] img')].filter(i => i.naturalWidth > 0).length === 3", timeout=8000)
        except Exception: pass
        strip = pg.evaluate("() => [...document.querySelectorAll('[data-testid=strip-saved]')].map(t => { const i = t.querySelector('img'); return i && i.naturalWidth ? [i.naturalWidth, i.naturalHeight] : 'doc'; })")
        k = next((n for n, x in enumerate(strip) if x != 'doc'), 0)
        tap(pg.locator('[data-testid=strip-saved]').nth(k)); opened = wait_view(pg) and wait_img(pg); v = pg.evaluate(VIEW)
        check('[strip · M-nostripopen fails here] a tap on a thumbnail in the edit form\'s strip opens that photo full screen', opened and v and v['natural'] == strip[k], (v, strip))
        close_if_open(pg)
        check('[strip] closing it leaves the form as it was', pg.url.startswith(ROOT + 'bird/edit/') and pg.locator('[data-testid=bird-form]').count() == 1, pg.url)
        fin = pg.locator('[data-testid=bird-form] input[type=file]').first
        fin.set_input_files(os.path.join(HERE, '..', 'fixtures', 'picked-second.png')); pg.wait_for_timeout(500)
        tap(pg.locator('[data-testid=strip-pending]').first); opened = wait_view(pg) and wait_img(pg); v = pg.evaluate(VIEW)
        check('[strip] a photo just picked, not yet saved, opens too — the last of the strip\'s photos', opened and v and v['natural'] == [8, 6] and v['index'] == 3, v)
        close_if_open(pg)
        check('[strip] …and nothing was stored by opening it', run(pg, COUNT, bird) == n0, run(pg, COUNT, bird))

        check('zero page errors overall', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
