#!/usr/bin/env python3
"""MANAGING A BIRD'S PHOTOS (RULED 2026-11-24, E1–E5, E7).

Measured before the rulings: a photo could be deleted only on the profile; a picked file could not be un-picked; a
bird's files came back in the order of a random id, so the gallery, the strip and "the first photo" the certificate
drew were chance, and the certificate's «تغيير» added a photo without changing the one drawn.

  E1  the edit form's strip: a saved file has a delete control (the profile's question, the profile's undo); a picked
      one has a remove control that un-picks it, with no question. The thumbnail still opens the viewer.
  E2  the profile's photos card adds photos and documents, several at once, through the form's own path (1600 px),
      stored at once, and says which files failed.
  E3  `mainPhotoId` on the bird, optional; set by a control under a photo on the profile; when it names no photo the
      device holds, the main photo is the earliest by addedAt; deleting the main photo clears the field in the same
      transaction and the undo restores both; a document is never the main photo.
  E4  the order everywhere — gallery, strip, viewer: the main photo first, then by addedAt ascending. Never by id.
  E5  the certificate's three boxes draw that bird's main photo; «تغيير» stores the photo and makes it the main one.
  E7  the profile's ✕ keeps its look inside a target of at least 44 px; so are the new controls.
  G1  (RULED 2026-11-25) a placeholder parent's slot on the certificate takes no file: its button is disabled and the
      slot says why and the way out; a placeholder that already holds a photo keeps it and its box draws it.
  G2  (RULED 2026-11-25) B5: a `mainPhotoId` naming a photo no longer stored is not something a placeholder holds.
  H0  (RULED 2026-11-27) nor does a placeholder take a photo or a document through its own edit form or its profile.
  H7  (RULED 2026-11-27) the control under a photo that is not the main one reads «اجعلها الرئيسية».
  and the field travels between two devices of one account (a stub backend, THE NET armed beneath it).

A phone's screen (390 px) with touch; the sizes are read at 1280 px too. Every file is made here: PNGs told apart by
their width, a one-page PDF. Names are invented words. A check that names a mutant is the one that mutant fails at.

    python3 tests/e2e/screens/photos_manage.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import json, os, re, struct, sys, zlib
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _typography import SCAN                 # noqa: E402
from _net import Net, no_bucket              # noqa: E402  THE NET (RULED 2026-10-08): armed beneath the stub, asserted at the end
NET = Net(); PAGES = []
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:520]) if not ok and d != '' else ''}")
def digits(s_): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s_ or '')
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))
def typo(pg): return [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]

# ── files, made here ──
def png(w, h=40):
    raw = b''.join(b'\x00' + bytes(((w * 7) % 256, 90, 160)) * w for _ in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
def P(name, w): return {'name': name, 'mimeType': 'image/png', 'buffer': png(w)}
PDF = {'name': 'paper.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF'}
BIG = os.path.join(HERE, '..', 'fixtures', 'picked-3000x2000.jpg')

# ── what the page holds ──
ROWS = "async (db, id) => (await db.mediaForBird(id)).map(m => ({ id: m.id, kind: m.kind, subtype: m.subtype, name: m.name, addedAt: m.addedAt, bytes: m.blob ? m.blob.size : 0 }))"
BIRD = "async (db, id) => { const b = db.getBird(id); return b ? { has: 'mainPhotoId' in b, main: b.mainPhotoId || null, colour: b.colour || '', updatedAt: b.updatedAt } : null; }"
# the gallery as drawn: each file's cell, its name, whether it is marked the main photo (null: no control — a document)
GALLERY = """() => [...document.querySelectorAll('[data-testid=media-cell]')].map(c => { const n = c.querySelector('[data-testid=media-photo] span, [data-testid=media-file] span'); const m = c.querySelector('[data-testid=media-main]');
    return { name: n ? n.innerText.trim() : '', main: m ? m.dataset.main : null, pressed: m ? m.getAttribute('aria-pressed') : null }; })"""
STRIP = "() => [...document.querySelectorAll('[data-testid=photo-strip] [data-testid=strip-saved], [data-testid=photo-strip] [data-testid=strip-pending]')].map(x => ({ kind: x.dataset.testid, name: x.title }))"
NATURAL = "async (db, id) => { const m = await db.idbGet('media', id); const b = await createImageBitmap(m.blob); const out = [b.width, b.height]; b.close(); return out; }"
BOX = """(sel) => [...document.querySelectorAll(sel)].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })"""
# a write to the media store refused for ONE named file — the fault a full disk gives, for that file only
ARM = """(bad) => { const P = IDBObjectStore.prototype; if (window.__heal) return; const put = P.put;
    P.put = function (v) { if (this.name === 'media' && v && v.name === bad) throw new DOMException('injected-write-failure', 'QuotaExceededError'); return put.apply(this, arguments); };
    window.__heal = () => { P.put = put; delete window.__heal; }; }"""
# every readwrite transaction the page opens from now on, as the list of stores it WROTE to (put or delete)
WATCH = """() => { window.__tx = []; const D = IDBDatabase.prototype; if (window.__unwatch) return; const open = D.transaction; const S = IDBObjectStore.prototype; const put = S.put, del = S.delete;
    D.transaction = function (stores, mode) { const t = open.apply(this, arguments); if (mode === 'readwrite') { t.__w = new Set(); window.__tx.push(t.__w); } return t; };
    S.put = function () { if (this.transaction.__w) this.transaction.__w.add('put:' + this.name); return put.apply(this, arguments); };
    S.delete = function () { if (this.transaction.__w) this.transaction.__w.add('delete:' + this.name); return del.apply(this, arguments); };
    window.__unwatch = () => { D.transaction = open; S.put = put; S.delete = del; delete window.__unwatch; }; }"""
WATCHED = "() => { const out = (window.__tx || []).map(s => [...s].sort()).filter(x => x.length); if (window.__unwatch) window.__unwatch(); return out; }"

def toasts(pg): return [x.strip().replace('\n', ' ') for x in pg.locator('[data-testid=toast]').all_inner_texts()]
def clear_toasts(pg):
    try: pg.wait_for_function("() => document.querySelectorAll('[data-testid=toast]').length === 0", timeout=14000)
    except Exception: pass
def said(pg, text, timeout=6000):
    """Wait, without raising, for a notice that carries `text`; answer every notice on screen."""
    try: pg.wait_for_function("(t) => [...document.querySelectorAll('[data-testid=toast]')].some(x => x.innerText.includes(t))", arg=text, timeout=timeout)
    except Exception: pass
    return toasts(pg)
def settle(pg, js, arg=None, timeout=8000):
    try: pg.wait_for_function(js, arg=arg, timeout=timeout); return True
    except Exception: return False
def waits(pg, sel, timeout=10000):
    """Wait for an element without raising: a mutant that removes it must fail AT a check."""
    try: pg.wait_for_selector(sel, timeout=timeout); return True
    except Exception: return False
def tap(loc):
    """Scroll the element to the middle of the screen and tap it; never raise (a mutant must fail AT a check)."""
    try: loc.evaluate("e => e.scrollIntoView({ block: 'center' })"); loc.page.wait_for_timeout(150); loc.tap(timeout=5000); return True
    except Exception: return False
def press(loc):
    try: loc.evaluate("e => e.scrollIntoView({ block: 'center' })"); loc.page.wait_for_timeout(120); loc.click(timeout=5000); return True
    except Exception: return False
def pick(pg, sel, files):
    try: pg.locator(sel).set_input_files(files, timeout=5000); return True
    except Exception: return False
def dialog(pg, timeout=4000):
    try: pg.wait_for_selector('[data-testid=dialog]', timeout=timeout)
    except Exception: return ''
    return ' / '.join(x.strip() for x in pg.locator('[data-testid=dialog]').inner_text().split('\n') if x.strip())
def answer(pg, which):
    try: pg.click(f'[data-testid=dialog-{which}]', timeout=4000); pg.wait_for_timeout(350); return True
    except Exception: return False
def viewer_order(pg):
    """Open the first photo of the screen and walk the viewer to its end: the natural width of each photo, in its order."""
    out = []
    if not tap(pg.locator('[data-testid=media-open], [data-testid=strip-saved]:has(img)').first): return out
    for _ in range(12):
        if not settle(pg, "() => { const i = document.querySelector('[data-testid=viewer-img]'); return i && i.naturalWidth > 0; }", timeout=5000): break
        pg.wait_for_timeout(150); out.append(pg.evaluate("() => document.querySelector('[data-testid=viewer-img]').naturalWidth"))
        nxt = pg.locator('[data-testid=viewer-next]')
        if not nxt.count(): break
        idx = pg.evaluate("() => document.querySelector('[data-testid=viewer]').dataset.index"); nxt.click()
        settle(pg, "(i) => document.querySelector('[data-testid=viewer]') && document.querySelector('[data-testid=viewer]').dataset.index !== i", arg=idx, timeout=3000)
    try: pg.locator('[data-testid=viewer-close]').click(timeout=3000)
    except Exception: pg.keyboard.press('Escape')
    settle(pg, "() => !document.querySelector('[data-testid=viewer]')", timeout=3000)
    return out

class Stop(Exception):
    """The rest of the suite has nothing to work on. Its checks above have already failed by name; this is not a traceback."""
srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, locale='ar-JO')
        pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
        pg.set_default_timeout(4000)              # nothing here may wait long for a control a mutant took away
        pg.set_default_navigation_timeout(30000)
        pg.goto(HARNESS, wait_until='load', timeout=30000); pg.wait_for_function('window.__zajilReady', timeout=30000)
        run(pg, "async (db) => { await db.setSetting('numerals', 'western'); }")
        bird = run(pg, "async (db) => (await db.saveBird(db.newBird({ name: 'طير الصور', sex: 'cock', loftId: db.currentLoft() && db.currentLoft().id }))).id")
        PROFILE = ROOT + 'bird/?id=' + bird; EDIT = ROOT + 'bird/edit/?id=' + bird
        def profile(n_photos=None):
            pg.goto(PROFILE, wait_until='load'); waits(pg, '[data-testid=media-add]')
            if n_photos is not None: settle(pg, "(n) => [...document.querySelectorAll('[data-testid=media-photo] img')].filter(i => i.naturalWidth > 0).length === n", arg=n_photos)
            pg.wait_for_timeout(250)
        def names(rows): return [r['name'] for r in rows]

        # ══ E2 — THE PROFILE ADDS PHOTOS AND DOCUMENTS ══
        print('E2 — the profile adds photos and documents')
        profile()
        ins = pg.evaluate("() => ['media-add-photo-input', 'media-add-doc-input'].map(t => { const e = document.querySelector(`[data-testid=${t}]`); return e ? { multiple: e.multiple, accept: e.getAttribute('accept'), capture: e.getAttribute('capture') } : null; })")
        check('[E2 · M-e2-single fails here] the profile\'s photos card has a photo input and a document input, each taking several files at once: image/* and image/*,.pdf',
              ins == [{'multiple': True, 'accept': 'image/*', 'capture': None}, {'multiple': True, 'accept': 'image/*,.pdf', 'capture': None}], ins)
        pick(pg, '[data-testid=media-add-photo-input]', [P('a-w110.png', 110), P('b-w120.png', 120), P('c-w130.png', 130)])
        shown = settle(pg, "() => [...document.querySelectorAll('[data-testid=media-photo] img')].filter(i => i.naturalWidth > 0).length === 3")
        rows = run(pg, ROWS, bird); t1 = said(pg, 'تم الحفظ')
        check('[E2 · M-e2-noadd fails here] three photos picked at once on the profile are stored at once — three photo records — and drawn without the page being reopened',
              shown and [(r['kind'], r['subtype']) for r in rows] == [('photo', 'body')] * 3 and sorted(names(rows)) == ['a-w110.png', 'b-w120.png', 'c-w130.png'] and all(r['bytes'] > 0 for r in rows), (shown, rows))
        check('[E2] …stored in the order they were picked, each with a time of its own, and «تم الحفظ» is said',
              names(sorted(rows, key=lambda r: r['addedAt'])) == ['a-w110.png', 'b-w120.png', 'c-w130.png'] and len({r['addedAt'] for r in rows}) == 3 and any('تم الحفظ' in x for x in t1), (rows, t1))
        clear_toasts(pg)
        pick(pg, '[data-testid=media-add-doc-input]', [PDF, P('scan-w170.png', 170)])
        settle(pg, "() => document.querySelectorAll('[data-testid=media-cell]').length === 5"); rows = run(pg, ROWS, bird)
        check('[E2] a PDF and an image picked at once as documents are stored as two documents',
              sorted((r['kind'], r['name']) for r in rows if r['kind'] == 'document') == [('document', 'paper.pdf'), ('document', 'scan-w170.png')], rows)
        clear_toasts(pg)
        pick(pg, '[data-testid=media-add-photo-input]', BIG)
        settle(pg, "() => document.querySelectorAll('[data-testid=media-cell]').length === 6"); rows = run(pg, ROWS, bird)
        big = next((r for r in rows if r['name'].startswith('picked-3000x2000')), None); nat = run(pg, NATURAL, big['id']) if big else None
        check('[E2 · M-e2-raw fails here] a 3000 × 2000 photo added on the profile goes through the form\'s own path: it is stored at 1600 px on its longest edge',
              nat == [1600, 1067], (nat, big))
        clear_toasts(pg)
        # one file of three is refused by storage: the other two are stored, and the fancier is told which one was not
        pg.evaluate(ARM, 'will-fail.png'); n0 = len(rows)
        pick(pg, '[data-testid=media-add-photo-input]', [P('ok-w140.png', 140), P('will-fail.png', 145), P('ok-w150.png', 150)])
        settle(pg, "(n) => document.querySelectorAll('[data-testid=media-cell]').length === n", arg=n0 + 2)
        t2 = said(pg, 'will-fail.png'); kinds = pg.evaluate("() => [...document.querySelectorAll('[data-testid=toast]')].map(x => x.dataset.kind)"); ty = typo(pg)
        pg.evaluate("() => window.__heal && window.__heal()"); rows = run(pg, ROWS, bird)
        check('[E2 · M-e2-silent fails here] when one file of three cannot be stored, a failure notice names it — «تعذّر حفظ 1 من 3: will-fail.png» — and no «تم الحفظ» is said',
              any('تعذّر حفظ 1 من 3: will-fail.png' in digits(x) for x in t2) and 'error' in kinds and not any('تم الحفظ' in x for x in t2), (t2, kinds))
        check('[E2] …and the other two are stored all the same', len(rows) == n0 + 2 and {'ok-w140.png', 'ok-w150.png'} <= set(names(rows)) and 'will-fail.png' not in names(rows), names(rows))
        check('[typography] the failure notice is drawn in a face that has Arabic', not ty, ty[:3])
        clear_toasts(pg)
        if len(rows) != 8: raise Stop('the eight files the later sections work on are not all stored')

        # ══ E3 — THE MAIN PHOTO ══
        print('E3 — the main photo')
        profile(6); g = pg.evaluate(GALLERY); rows = run(pg, ROWS, bird); bd = run(pg, BIRD, bird)
        by_time = names(sorted(rows, key=lambda r: r['addedAt'])); by_id = names(sorted(rows, key=lambda r: r['id']))
        ID = {r['name']: r['id'] for r in rows}
        check('[fixture] these eight files do not sort by id as they sort by time (else the order checks below would prove nothing)', by_id != by_time and len(rows) == 8, (by_id, by_time))
        check('[E3 · M-e3-nocontrol fails here] under every photo on the profile there is a main-photo control, and under a document there is none',
              len(g) == 8 and all((x['main'] is None) == (x['name'] in ('paper.pdf', 'scan-w170.png')) for x in g), g)
        check('[E3 · M-e3-earliest fails here] with no main photo chosen the bird record carries no `mainPhotoId`, and the photo marked is the EARLIEST one: a-w110.png, alone',
              bd == {**bd, 'has': False, 'main': None} and [x['name'] for x in g if x['main'] == '1'] == ['a-w110.png'] and [x['name'] for x in g if x['pressed'] == 'true'] == ['a-w110.png'], (bd, g))
        cell = pg.locator('[data-testid=media-cell]', has_text='c-w130.png')
        tap(cell.locator('[data-testid=media-main]')); t3 = said(pg, 'صارت هذه الصورة الرئيسية'); ty = typo(pg)
        settle(pg, "() => { const c = [...document.querySelectorAll('[data-testid=media-cell]')][0]; return c && c.innerText.includes('c-w130.png'); }")
        g = pg.evaluate(GALLERY); bd = run(pg, BIRD, bird)
        check('[E3 · M-e3-noset fails here] the control under c-w130.png makes it the main photo: the bird record names it in `mainPhotoId`, and it alone is marked',
              bd['main'] == ID['c-w130.png'] and [x['name'] for x in g if x['main'] == '1'] == ['c-w130.png'], (bd, ID['c-w130.png'], g))
        check('[E3] …and it is said: «صارت هذه الصورة الرئيسية», in a face that has Arabic', any('صارت هذه الصورة الرئيسية' in x for x in t3) and not ty, (t3, ty[:3]))
        ty = typo(pg)
        check('[typography] the profile with its new controls — «الرئيسية», «إضافة صورة», «إضافة وثيقة» — is drawn in faces that have Arabic', not ty, ty[:3])
        other = run(pg, "async (db) => { const b = await db.saveBird(db.newBird({ name: 'طير آخر', sex: 'hen' })); const c = document.createElement('canvas'); c.width = 20; c.height = 20; const blob = await new Promise(r => c.toBlob(r, 'image/png')); const m = await db.addMedia(b.id, 'photo', 'body', 'elsewhere.png', blob); return { bird: b.id, photo: m.id }; }")
        refused = run(pg, "async (db, id, doc, foreign) => [await db.setMainPhoto(id, doc), await db.setMainPhoto(id, foreign), await db.setMainPhoto(id, 'no-such-file')]", bird, ID['paper.pdf'], other['photo'])
        bd = run(pg, BIRD, bird)
        check('[E3 · M-e3-doc fails here] a document is never the main photo: asked for a document, another bird\'s photo and a file that does not exist, the layer refuses all three and the field stays',
              refused == [False, False, False] and bd['main'] == ID['c-w130.png'], (refused, bd))

        # ══ E4 — THE ORDER, EVERYWHERE ══
        print('E4 — the order: the main photo first, then by the time each file was added')
        WANT = ['c-w130.png'] + [n for n in by_time if n != 'c-w130.png']
        check('[E4 · M-e4-byid fails here] the profile\'s gallery: the main photo first, then every file by the time it was added — documents among them',
              [x['name'] for x in g] == WANT, ([x['name'] for x in g], WANT))
        vo = viewer_order(pg); WIDTH = {'a-w110.png': 110, 'b-w120.png': 120, 'c-w130.png': 130, 'ok-w140.png': 140, 'ok-w150.png': 150, 'picked-3000x2000.jpg': 1600}
        check('[E4 · M-e4-viewer fails here] the viewer opened from the gallery walks the photos in that same order', vo == [WIDTH[n] for n in WANT if n in WIDTH], (vo, WANT))
        pg.goto(EDIT, wait_until='load'); waits(pg, '[data-testid=photo-strip]')
        settle(pg, "() => [...document.querySelectorAll('[data-testid=strip-saved] img')].filter(i => i.naturalWidth > 0).length === 6"); st = pg.evaluate(STRIP)
        check('[E4 · M-e4-strip fails here] the edit form\'s strip shows the saved files in that same order', [x['name'] for x in st] == WANT and all(x['kind'] == 'strip-saved' for x in st), st)
        vo = viewer_order(pg)
        check('[E4] …and the viewer opened from the strip walks the photos in it too', vo == [WIDTH[n] for n in WANT if n in WIDTH], vo)

        # ══ E1 — THE STRIP'S TWO CONTROLS ══
        print('E1 — the edit form\'s strip: delete a saved file, un-pick a picked one')
        tiles = pg.evaluate("""() => [...document.querySelectorAll('[data-testid=strip-tile]')].map(t => { const th = t.querySelector('[data-testid=strip-saved], [data-testid=strip-pending]'); const d = t.querySelector('[data-testid=strip-delete], [data-testid=strip-unpick]');
            const box = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
            return { thumb: th && box(th), control: d ? d.dataset.testid : null, box: d && box(d), inside: !!(d && th && th.contains(d)) }; })""")
        apart = all(x['box'] and x['thumb'] and (x['box'][1] >= x['thumb'][3] or x['box'][3] <= x['thumb'][1] or x['box'][0] >= x['thumb'][2] or x['box'][2] <= x['thumb'][0]) for x in tiles)
        check('[E1 · M-e1-nodelete fails here] every saved file in the strip has a delete control of its own — beside its thumbnail, not inside it, and not over it',
              len(tiles) == 8 and all(x['control'] == 'strip-delete' and not x['inside'] for x in tiles) and apart, tiles[:2])
        n0 = len(run(pg, ROWS, bird))
        tap(pg.locator('[data-testid=strip-saved]', has=pg.locator('img')).nth(1)); opened = settle(pg, "() => !!document.querySelector('[data-testid=viewer]')", timeout=4000); asked = pg.locator('[data-testid=dialog]').count()
        try: pg.locator('[data-testid=viewer-close]').click(timeout=3000)
        except Exception: pass
        settle(pg, "() => !document.querySelector('[data-testid=viewer]')", timeout=3000)
        check('[E1 · M-e1-thumbdeletes fails here] a tap on a thumbnail still opens the viewer — it asks nothing and deletes nothing', opened and asked == 0 and len(run(pg, ROWS, bird)) == n0, (opened, asked))
        tile_b = pg.locator('[data-testid=strip-tile]', has=pg.locator('[data-testid=strip-saved][title="b-w120.png"]'))
        tap(tile_b.locator('[data-testid=strip-delete]')); q = dialog(pg)
        check('[E1 · M-e1-noconfirm fails here] the delete control asks the profile\'s own question first: «تأكيد الحذف؟ / إلغاء / حذف»', q == 'تأكيد الحذف؟ / إلغاء / حذف', q)
        answer(pg, 'cancel')
        check('[E1] «إلغاء» deletes nothing', len(run(pg, ROWS, bird)) == n0 and len(pg.evaluate(STRIP)) == 8)
        tap(tile_b.locator('[data-testid=strip-delete]')); dialog(pg); answer(pg, 'confirm')
        settle(pg, "() => document.querySelectorAll('[data-testid=strip-saved]').length === 7"); t4 = said(pg, 'تم الحذف'); rows = run(pg, ROWS, bird)
        check('[E1] on «حذف» the file is gone from the store and from the strip, at once, and «تراجع» is offered',
              'b-w120.png' not in names(rows) and len(rows) == n0 - 1 and 'b-w120.png' not in [x['name'] for x in pg.evaluate(STRIP)] and pg.locator('[data-testid=toast-action]').count() == 1 and any('تم الحذف' in x for x in t4), (names(rows), t4))
        press(pg.locator('[data-testid=toast-action]')); settle(pg, "() => document.querySelectorAll('[data-testid=strip-saved]').length === 8"); rows = run(pg, ROWS, bird)
        check('[E1 · M-e1-noundo fails here] «تراجع» puts it back: in the store, and in the strip at its own place in the order', names(rows) == WANT and [x['name'] for x in pg.evaluate(STRIP)] == WANT, names(rows))
        clear_toasts(pg)
        # picked, not yet saved
        pick(pg, '[data-testid=bird-form] input[type=file] >> nth=0', [P('p-w210.png', 210), P('p-w220.png', 220), P('p-w230.png', 230)])
        settle(pg, "() => document.querySelectorAll('[data-testid=strip-pending]').length === 3"); st = pg.evaluate(STRIP)
        ctl = pg.evaluate("() => [...document.querySelectorAll('[data-testid=strip-tile]')].filter(t => t.querySelector('[data-testid=strip-pending]')).map(t => !!t.querySelector('[data-testid=strip-unpick]') && !t.querySelector('[data-testid=strip-delete]'))")
        check('[E1 · M-e1-nounpick fails here] every picked file has a remove control of its own (and no delete control: nothing of it is stored)', ctl == [True, True, True] and [x['name'] for x in st[8:]] == ['p-w210.png', 'p-w220.png', 'p-w230.png'], (ctl, st[8:]))
        mid = pg.locator('[data-testid=strip-tile]', has=pg.locator('[data-testid=strip-pending][title="p-w220.png"]'))
        tap(mid.locator('[data-testid=strip-unpick]')); pg.wait_for_timeout(400); asked = pg.locator('[data-testid=dialog]').count(); st = pg.evaluate(STRIP)
        line = pg.locator('[data-testid=pending-media]').inner_text() if pg.locator('[data-testid=pending-media]').count() else ''
        check('[E1 · M-e1-unpickwrong fails here] the remove control un-picks THAT file — the middle one of three — with no question; the other two stay, in their order',
              asked == 0 and [x['name'] for x in st[8:]] == ['p-w210.png', 'p-w230.png'] and line == 'p-w210.png · p-w230.png', (asked, st[8:], line))
        check('[E1] …and nothing was stored or deleted by it', names(run(pg, ROWS, bird)) == WANT)
        press(pg.locator('[data-testid=save-btn]')); settle(pg, "() => /\\/bird\\/?\\?id=/.test(location.href)", timeout=8000); pg.wait_for_timeout(500); rows = run(pg, ROWS, bird)
        check('[E1] saving after an un-pick stores only what remained: p-w210.png and p-w230.png, not p-w220.png',
              names(rows) == WANT + ['p-w210.png', 'p-w230.png'], names(rows))
        # the form deletes the bird's MAIN photo, then saves: its own write is not «another device's», and the copy it holds does not put the field back
        pg.goto(EDIT, wait_until='load'); waits(pg, '[data-testid=photo-strip]'); settle(pg, "() => document.querySelectorAll('[data-testid=strip-saved]').length === 10")
        tile_c = pg.locator('[data-testid=strip-tile]', has=pg.locator('[data-testid=strip-saved][title="c-w130.png"]'))
        tap(tile_c.locator('[data-testid=strip-delete]')); dialog(pg); answer(pg, 'confirm'); settle(pg, "() => document.querySelectorAll('[data-testid=strip-saved]').length === 9"); clear_toasts(pg)
        mid_state = run(pg, BIRD, bird)
        try: pg.fill('[data-testid=f-colour]', 'أزرق', timeout=4000)
        except Exception: pass
        press(pg.locator('[data-testid=save-btn]')); went = settle(pg, "() => document.querySelector('[data-testid=dialog]') || /\\/bird\\/?\\?id=/.test(location.href)", timeout=8000); q = dialog(pg, 600) if pg.locator('[data-testid=dialog]').count() else ''
        check('[E1 · M-e1-own fails here] deleting the bird\'s main photo in the form and then saving the form asks nothing: the form\'s own deletion is not «تغيّر هذا السجل على جهاز آخر»',
              went and q == '' and mid_state['has'] is False, (q, mid_state))
        if q: answer(pg, 'confirm')
        settle(pg, "() => /\\/bird\\/?\\?id=/.test(location.href)", timeout=8000); pg.wait_for_timeout(400); bd = run(pg, BIRD, bird)
        check('[E1 · M-e1-stale fails here] …and the saved record carries the edit and NO `mainPhotoId`: the copy the form took when it opened does not put the deleted photo\'s id back',
              bd['colour'] == 'أزرق' and bd['has'] is False, bd)

        # ══ E3, continued — DELETING THE MAIN PHOTO, AND ITS UNDO ══
        print('E3 — deleting the main photo clears the field in the same transaction; the undo restores both')
        run(pg, "async (db, id, m) => { await db.setMainPhoto(id, m); }", bird, ID['ok-w140.png'])
        profile(7); g = pg.evaluate(GALLERY)
        check('[setup] ok-w140.png is the main photo now, first in the gallery', g and g[0]['name'] == 'ok-w140.png' and g[0]['main'] == '1' and run(pg, BIRD, bird)['main'] == ID['ok-w140.png'], g[:2])
        pg.evaluate(WATCH)
        cell = pg.locator('[data-testid=media-cell]', has_text='ok-w140.png')
        tap(cell.locator('[data-testid=media-delete]')); dialog(pg); answer(pg, 'confirm'); settle(pg, "() => document.querySelectorAll('[data-testid=media-photo]').length === 6"); pg.wait_for_timeout(300)
        tx = pg.evaluate(WATCHED); bd = run(pg, BIRD, bird); g = pg.evaluate(GALLERY)
        both = [t for t in tx if 'delete:media' in t and 'put:birds' in t]; alone = [t for t in tx if ('put:birds' in t) != ('delete:media' in t)]
        check('[E3 · M-e3-noclear fails here] deleting the main photo clears `mainPhotoId` — the key is gone from the bird record',
              bd['has'] is False and 'ok-w140.png' not in names(run(pg, ROWS, bird)), bd)
        check('[E3 · M-e3-twotx fails here] …in the SAME transaction: one transaction deleted the photo and wrote the bird, and no other wrote either of them', len(both) == 1 and not alone, tx)
        check('[E3] …and the main photo is then the earliest one left: a-w110.png, marked and first', [x['name'] for x in g if x['main'] == '1'] == ['a-w110.png'] and g[0]['name'] == 'a-w110.png', g[:3])
        press(pg.locator('[data-testid=toast-action]')); settle(pg, "() => document.querySelectorAll('[data-testid=media-photo]').length === 7"); pg.wait_for_timeout(300)
        bd = run(pg, BIRD, bird); g = pg.evaluate(GALLERY)
        check('[E3 · M-e3-noundo fails here] «تراجع» restores both: the photo, and `mainPhotoId` naming it — marked and first again',
              bd['main'] == ID['ok-w140.png'] and g and g[0]['name'] == 'ok-w140.png' and g[0]['main'] == '1', (bd, g[:2]))
        clear_toasts(pg)
        # the named photo is gone WITHOUT the field having been cleared (another device's deletion pulled alone, or an older build's)
        gone = run(pg, """async (db, id) => { const c = document.createElement('canvas'); c.width = 30; c.height = 20; const blob = await new Promise(r => c.toBlob(r, 'image/png'));
            const b = await db.saveBird(db.newBird({ name: 'طير الاحتياط', sex: 'hen' })); const first = await db.addMedia(b.id, 'photo', 'body', 'first.png', blob); const second = await db.addMedia(b.id, 'photo', 'body', 'second.png', blob);
            await db.setMainPhoto(b.id, second.id); await db.idbDelete('media', second.id);
            const rows = await db.mediaForBird(b.id); const main = db.mainPhotoOf(rows, db.getBird(b.id).mainPhotoId);
            return { field: db.getBird(b.id).mainPhotoId === second.id, main: main && main.name, order: rows.map(r => r.name) }; }""", bird)
        check('[E3 · M-e3-fallback fails here] when `mainPhotoId` names a photo the device no longer holds, the main photo is the earliest one by the time it was added',
              gone == {'field': True, 'main': 'first.png', 'order': ['first.png']}, gone)
        # PROPOSED (not ruled): the undo does not take the place back from a main photo chosen since the deletion
        later = run(pg, """async (db, id, m, other) => { const snap = await db.deleteMedia(m); await db.setMainPhoto(id, other); await db.restoreMedia(snap);
            return { main: db.getBird(id).mainPhotoId, back: (await db.mediaForBird(id)).some(r => r.id === m) }; }""", bird, ID['ok-w140.png'], ID['ok-w150.png'])
        check('[E3 · proposed, M-e3-undoover fails here] an undo that comes after another photo was made the main one restores the photo and leaves the later choice',
              later == {'main': ID['ok-w150.png'], 'back': True}, later)

        # ══ E5 — THE CERTIFICATE ══
        print('E5 — the certificate draws each bird\'s main photo; «تغيير» stores the photo and makes it the main one')
        fam = run(pg, """async (db) => { const shot = async (w) => { const c = document.createElement('canvas'); c.width = w; c.height = 40; const x = c.getContext('2d'); x.fillStyle = `hsl(${w % 360} 60% 50%)`; x.fillRect(0, 0, w, 40); return new Promise(r => c.toBlob(r, 'image/png')); };
            const add = async (id, w) => (await db.addMedia(id, 'photo', 'body', `w${w}.png`, await shot(w))).id;
            const sire = (await db.saveBird(db.newBird({ name: 'أب الشهادة', sex: 'cock', external: true }))).id; const dam = (await db.saveBird(db.newBird({ name: 'أم الشهادة', sex: 'hen', external: true }))).id;
            const kid = (await db.saveBird(db.newBird({ name: 'طير الشهادة', sex: 'cock', sireId: sire, damId: dam }), { allowWarnings: true })).id;
            await add(kid, 510); await add(kid, 520); await add(sire, 310); await add(sire, 320); await add(dam, 410); const d2 = await add(dam, 420);
            await db.setMainPhoto(dam, d2); return { kid, sire, dam }; }""")
        pg.goto(ROOT + 'cert/?id=' + fam['kid'], wait_until='load'); waits(pg, '[data-testid=sec-photos]'); pg.wait_for_timeout(500)
        for who in ('bird', 'sire', 'dam'): press(pg.locator(f'[data-testid=sw-{who}]'))
        CERT = """() => Object.fromEntries(['bird', 'sire', 'dam'].map(w => { const t = document.querySelector(`[data-testid=thumb-${w}] img`), s = document.querySelector(`[data-testid=sheet-photo-${w}] img`); return [w, [t && t.naturalWidth, s && s.naturalWidth]]; }))"""
        settle(pg, "() => ['bird', 'sire', 'dam'].every(w => { const s = document.querySelector(`[data-testid=sheet-photo-${w}] img`); return s && s.naturalWidth > 0; })"); c0 = pg.evaluate(CERT)
        check('[E5 · M-e5-notmain fails here] each box draws that bird\'s main photo, in the panel and on the sheet: the bird\'s and the father\'s earliest (510, 310), the mother\'s chosen one (420)',
              c0 == {'bird': [510, 510], 'sire': [310, 310], 'dam': [420, 420]}, c0)
        def change(who, file, want):
            try:
                with pg.expect_file_chooser(timeout=5000) as fc: pg.locator(f'[data-testid=pick-{who}]').click(timeout=5000)
                fc.value.set_files(file)
            except Exception: pass
            settle(pg, "(a) => { const s = document.querySelector(`[data-testid=sheet-photo-${a[0]}] img`); return s && s.naturalWidth === a[1]; }", arg=[who, want], timeout=6000)
            return pg.evaluate(CERT)
        label0 = pg.locator('[data-testid=pick-bird]').inner_text().strip(); n0 = len(run(pg, ROWS, fam['kid']))
        c1 = change('bird', P('w530.png', 530), 530); rows = run(pg, ROWS, fam['kid']); bd = run(pg, BIRD, fam['kid']); new = next((r['id'] for r in rows if r['name'] == 'w530.png'), None)
        check('[E5 · M-e5-nomain fails here] «تغيير» on the bird\'s box stores the new photo AND makes it the bird\'s main photo, so the box changes to it: 510 → 530, in the panel and on the sheet',
              label0 == 'تغيير' and len(rows) == n0 + 1 and new is not None and bd['main'] == new and c1['bird'] == [530, 530], (label0, bd, new, c1))
        c2 = change('sire', P('w330.png', 330), 330); srows = run(pg, ROWS, fam['sire']); sb = run(pg, BIRD, fam['sire']); snew = next((r['id'] for r in srows if r['name'] == 'w330.png'), None)
        check('[E5 · M-e5-parent fails here] the same on the father\'s box: the photo is stored on the FATHER\'s record and becomes HIS main photo — 310 → 330 — and the bird\'s own box stays',
              snew is not None and sb['main'] == snew and c2['sire'] == [330, 330] and c2['bird'] == [530, 530] and run(pg, BIRD, fam['kid'])['main'] == new, (sb, c2))
        check('[E5] …and the list the certificate\'s bird shows elsewhere follows: its gallery order starts with the new main photo', names(rows)[0] == 'w530.png' and names(rows)[1:] == ['w510.png', 'w520.png'], names(rows))

        # ══ G1 — A PLACEHOLDER PARENT'S SLOT TAKES NO PHOTO (RULED 2026-11-25, option b of E5) ══
        print('G1 — on the certificate, a placeholder parent\'s slot accepts no file, says why, and keeps a photo it already holds')
        REASON = 'لإضافة صورة، أعطِ هذا الطائر اسمًا أو رقم حلقة أولًا'
        unk = run(pg, """async (db) => { const c = document.createElement('canvas'); c.width = 450; c.height = 40; c.getContext('2d').fillRect(0, 0, 450, 40); const blob = await new Promise(r => c.toBlob(r, 'image/png'));
            const sire = (await db.saveBird(db.newBird({ name: 'أب غير معروف', sex: 'cock', placeholder: true }), { allowWarnings: true })).id;
            const dam = (await db.saveBird(db.newBird({ name: 'أم غير معروفة', sex: 'hen', placeholder: true }), { allowWarnings: true })).id;
            const old = (await db.addMedia(dam, 'photo', 'body', 'w450.png', blob, { main: true })).id;   // a photo given before this rule
            const kid = (await db.saveBird(db.newBird({ name: 'طير بأبوين مجهولين', sex: 'hen', sireId: sire, damId: dam }), { allowWarnings: true })).id; return { kid, sire, dam, old }; }""")
        pg.goto(ROOT + 'cert/?id=' + unk['kid'], wait_until='load'); waits(pg, '[data-testid=sec-photos]'); pg.wait_for_timeout(500)
        for who in ('sire', 'dam'): press(pg.locator(f'[data-testid=sw-{who}]'))
        SLOT = """(w) => { const b = document.querySelector(`[data-testid=pick-${w}]`), d = document.querySelector(`[data-testid=d-${w}]`), t = document.querySelector(`[data-testid=thumb-${w}] img`), s = document.querySelector(`[data-testid=sheet-photo-${w}] img`);
            return { disabled: b ? b.disabled : null, button: b ? b.innerText.trim() : null, says: d ? d.innerText.trim() : null, describedBy: b && b.getAttribute('aria-describedby') ? (document.getElementById(b.getAttribute('aria-describedby')) || {}).innerText : null,
                     thumb: t ? t.naturalWidth : null, sheet: s ? s.naturalWidth : null }; }"""
        settle(pg, "() => { const s = document.querySelector('[data-testid=sheet-photo-dam] img'); return s && s.naturalWidth > 0; }", timeout=5000)
        g_s, g_d, g_b = pg.evaluate(SLOT, 'sire'), pg.evaluate(SLOT, 'dam'), pg.evaluate(SLOT, 'bird')
        check('[G1 · M-g1-open fails here] a placeholder father\'s slot: its button is disabled and the slot says why, with the way out — «' + REASON + '» — read out with the button',
              g_s['disabled'] is True and g_s['says'] == REASON and g_s['describedBy'] == REASON, g_s)
        check('[G1] …the same on a placeholder mother\'s slot, while the bird\'s own slot, an ordinary bird, still takes a photo',
              g_d['disabled'] is True and g_d['says'] == REASON and g_b['disabled'] is False and g_b['says'] != REASON, (g_d, g_b))
        LOOK = """(w) => { const b = document.querySelector(`[data-testid=pick-${w}]`), probe = document.createElement('span'); probe.style.background = 'var(--line)'; probe.style.color = 'var(--ink-2)'; b.parentElement.appendChild(probe);
            const want = [getComputedStyle(probe).backgroundColor, getComputedStyle(probe).color]; probe.style.background = 'var(--brand-tint)'; const tint = getComputedStyle(probe).backgroundColor; probe.remove();
            const cs = getComputedStyle(b); return { bg: cs.backgroundColor, ink: cs.color, want, tint, rowOn: !b.closest('[data-testid^=row-]').className.includes('off') }; }"""
        lk = pg.evaluate(LOOK, 'sire')
        check('[G1 · M-g1-look fails here] …and, in a row that is on, it looks unavailable: the ruled disabled pattern (--line fill, --ink-2 ink), not the brand tint of an enabled button',
              lk['rowOn'] and [lk['bg'], lk['ink']] == lk['want'] and lk['bg'] != lk['tint'], lk)
        chooser = False
        try:
            with pg.expect_file_chooser(timeout=1500): pg.locator('[data-testid=pick-sire]').evaluate('e => e.click()')
            chooser = True
        except Exception: pass
        n_s = len(run(pg, ROWS, unk['sire'])); rec_s = run(pg, BIRD, unk['sire'])
        check('[G1] …pressing it opens no file chooser, and the placeholder father holds no file and no main photo', chooser is False and n_s == 0 and rec_s['has'] is False, (chooser, n_s, rec_s))
        check('[G1 · M-g1-keep fails here] a placeholder that already holds a photo keeps it and its box still draws it: 450, in the panel and on the sheet',
              g_d['thumb'] == 450 and g_d['sheet'] == 450 and len(run(pg, ROWS, unk['dam'])) == 1 and run(pg, BIRD, unk['dam'])['main'] == unk['old'], g_d)

        # ══ H0 — NOR THROUGH ITS OWN EDIT FORM OR ITS PROFILE (RULED 2026-11-27) ══
        print('H0 — a placeholder takes no photo or document through its own edit form or its profile either')
        pg.goto(ROOT + 'bird/edit/?id=' + unk['sire'], wait_until='load'); waits(pg, '[data-testid=bird-form]'); pg.wait_for_timeout(400)
        FORM = """() => { const b = document.querySelector('[data-testid=photo-btn]'), d = document.querySelector('[data-testid=doc-btn]'), w = document.querySelector('[data-testid=photo-why]');
            return { photo: b ? b.disabled : null, doc: d ? d.getAttribute('aria-disabled') : null, says: w ? w.innerText.trim() : null, describedBy: b && b.getAttribute('aria-describedby') ? (document.getElementById(b.getAttribute('aria-describedby')) || {}).innerText : null }; }"""
        f0 = pg.evaluate(FORM); opened = False
        try:
            with pg.expect_file_chooser(timeout=1500): pg.locator('[data-testid=doc-btn]').evaluate('e => e.click()')
            opened = True
        except Exception: pass
        check('[H0 · M-h0-form fails here] the placeholder father\'s own EDIT FORM: the photo picker is disabled, «إضافة وثيقة» is disabled and opens no chooser, and the form says why — the certificate\'s sentence',
              f0['photo'] is True and f0['doc'] == 'true' and f0['says'] == REASON and f0['describedBy'] == REASON and not opened, (f0, opened))
        try: pg.fill('[data-testid=f-name]', 'نسر الوادي', timeout=4000); pg.wait_for_timeout(200)
        except Exception: pass
        f1 = pg.evaluate(FORM)
        check('[H0] …a name typed (the save would make him an ordinary bird, C3) opens both pickers at once, and the sentence gives way to the usual hint',
              f1['photo'] is False and f1['doc'] in (None, 'false') and f1['says'] is None, f1)
        pg.goto(ROOT + 'bird/?id=' + unk['sire'], wait_until='load'); waits(pg, '[data-testid=media-add]'); pg.wait_for_timeout(400)
        PROF = """() => { const q = (k) => document.querySelector(`[data-testid=${k}]`); const w = q('media-add-why');
            return { photo: q('media-add-photo') ? q('media-add-photo').disabled : null, doc: q('media-add-doc') ? q('media-add-doc').disabled : null, says: w ? w.innerText.trim() : null,
                     describedBy: q('media-add-photo') && q('media-add-photo').getAttribute('aria-describedby') ? (document.getElementById(q('media-add-photo').getAttribute('aria-describedby')) || {}).innerText : null }; }"""
        p0 = pg.evaluate(PROF)
        pick(pg, '[data-testid=media-add-photo-input]', [P('h0-w460.png', 460)]); pg.wait_for_timeout(900)
        n_h0 = len(run(pg, ROWS, unk['sire']))
        check('[H0 · M-h0-profile fails here] his PROFILE: «إضافة صورة» and «إضافة وثيقة» are disabled, the sentence says why, and a file handed to the hidden input is not stored',
              p0['photo'] is True and p0['doc'] is True and p0['says'] == REASON and p0['describedBy'] == REASON and n_h0 == 0, (p0, n_h0))

        # ══ G2 — A mainPhotoId NAMING A PHOTO NO LONGER STORED IS NOT SOMETHING A PLACEHOLDER HOLDS (B5) ══
        print('G2 — B5 does not count a main-photo field that names a photo no longer stored')
        g2 = run(pg, """async (db) => { const c = document.createElement('canvas'); c.width = 24; c.height = 24; const blob = await new Promise(r => c.toBlob(r, 'image/png'));
            const fam = async (tag) => { const ph = await db.saveBird(db.newBird({ name: 'أب غير معروف', sex: 'cock', placeholder: true }), { allowWarnings: true });
                const kid = (await db.saveBird(db.newBird({ name: 'فرخ ' + tag, sex: 'hen', sireId: ph.id }), { allowWarnings: true })).id; return { ph: ph.id, kid }; };
            const stale = await fam('أ'), held = await fam('ب');
            // the shape the old build (4acbf2a) leaves: it deleted the photo and kept the field naming it — saved here as that record
            await db.saveBird({ ...db.getBird(stale.ph), mainPhotoId: 'a-photo-no-longer-stored' }, { allowWarnings: true });
            await db.addMedia(held.ph, 'photo', 'body', 'kept.png', blob, { main: true });
            const before = { stale: db.getBird(stale.ph).mainPhotoId, held: db.getBird(held.ph).mainPhotoId };
            await db.deleteBird(stale.kid); await db.deleteBird(held.kid);
            const tombs = new Set((await db.idbGetAll('tombstones')).map(t => t.key || t.id));
            const look = (id) => { const b = db.getBird(id); return { here: !!b, placeholder: b ? b.placeholder === true : null, main: b ? b.mainPhotoId || null : null }; };
            return { before, stale: { ...look(stale.ph), tomb: tombs.has('birds:' + stale.ph) }, held: { ...look(held.ph), tomb: tombs.has('birds:' + held.ph) } }; }""")
        check('[G2 · M-g2-stale fails here] a placeholder father whose main-photo field names a photo no longer stored goes with his last child, tombstoned — the field is not something he holds',
              g2['before']['stale'] == 'a-photo-no-longer-stored' and g2['stale'] == {'here': False, 'placeholder': None, 'main': None, 'tomb': True}, g2)
        check('[G2] …while one whose main photo IS stored holds it: he stays, his flag cleared, the field kept (B5 as it was)',
              g2['held']['here'] is True and g2['held']['placeholder'] is False and g2['held']['main'] == g2['before']['held'] and g2['held']['tomb'] is False, g2)

        # ══ E7 — TARGETS OF AT LEAST 44 PX ══
        print('E7 — the ✕ keeps its look inside a 44 px target; the new controls are at least 44 px too')
        DEL = """() => [...document.querySelectorAll('[data-testid=media-tile]')].map(t => { const d = t.querySelector('[data-testid=media-delete]'), s = d && d.querySelector('span'); if (!d || !s) return null;
            const T = t.getBoundingClientRect(), D = d.getBoundingClientRect(), S = s.getBoundingClientRect(); const rtl = getComputedStyle(t).direction === 'rtl';
            return { target: [Math.round(D.width), Math.round(D.height)], disc: [Math.round(S.width), Math.round(S.height)], fromTop: Math.round(S.top - T.top), fromEnd: Math.round(rtl ? S.left - T.left : T.right - S.right),
                     discInTarget: S.left >= D.left && S.right <= D.right && S.top >= D.top && S.bottom <= D.bottom, glyph: s.innerText.trim() }; })"""
        for W, H in ((390, 844), (1280, 800)):
            pg.set_viewport_size({'width': W, 'height': H}); profile(7); d = pg.evaluate(DEL)
            check(f'[E7 · M-e7-small fails here] at {W} px the profile\'s ✕ is a target of at least 44 × 44 px on every tile',
                  len(d) == 9 and all(x and x['target'][0] >= 44 and x['target'][1] >= 44 for x in d), d[:2])
            check(f'[E7 · M-e7-look fails here] at {W} px it keeps its look: the same 28 px disc with ✕, 6 px in from the tile\'s top and from its end edge, inside the target',
                  all(x and x['disc'] == [28, 28] and x['fromTop'] == 6 and x['fromEnd'] == 6 and x['discInTarget'] and x['glyph'] == '✕' for x in d), d[:2])
            sizes = {k: pg.evaluate(BOX, f'[data-testid={k}]') for k in ('media-main', 'media-add-photo', 'media-add-doc')}
            check(f'[E7 · M-e7-newsmall fails here] at {W} px the profile\'s new controls are at least 44 × 44 px: the main-photo control under each photo, «إضافة صورة», «إضافة وثيقة»',
                  len(sizes['media-main']) == 7 and all(len(v) >= 1 and all(w >= 44 and h >= 44 for w, h in v) for v in sizes.values()), sizes)
            # H7 (RULED 2026-11-27): the control under a photo that is not the main one says what it does
            LBL = """() => [...document.querySelectorAll('[data-testid=media-main]')].map(b => { const sp = b.querySelector('span'), B = b.getBoundingClientRect(), S = sp.getBoundingClientRect();
                return { main: b.dataset.main, text: sp.innerText.trim(), aria: b.getAttribute('aria-label'), box: [Math.round(B.width), Math.round(B.height)],
                         inside: S.left >= B.left - 0.5 && S.right <= B.right + 0.5 && S.top >= B.top - 0.5 && S.bottom <= B.bottom + 0.5 }; })"""
            lb = pg.evaluate(LBL); on = [x for x in lb if x['main'] == '1']; off = [x for x in lb if x['main'] == '0']
            check(f'[H7 · M-h7-label fails here] at {W} px the control under a photo that is NOT the main one reads «اجعلها الرئيسية» (its aria-label the same), under the main photo «الرئيسية» (aria-label «الصورة الرئيسية») — each pill inside its control',
                  len(on) == 1 and len(off) == 6 and on[0]['text'] == 'الرئيسية' and on[0]['aria'] == 'الصورة الرئيسية'
                  and all(x['text'] == 'اجعلها الرئيسية' and x['aria'] == 'اجعلها الرئيسية' for x in off) and all(x['inside'] and x['box'][1] == 44 for x in lb), lb[:3])
            pg.goto(EDIT, wait_until='load'); waits(pg, '[data-testid=photo-strip]'); pick(pg, '[data-testid=bird-form] input[type=file] >> nth=0', [P('q-w240.png', 240)])
            settle(pg, "() => document.querySelectorAll('[data-testid=strip-pending]').length === 1")
            sizes = {k: pg.evaluate(BOX, f'[data-testid={k}]') for k in ('strip-delete', 'strip-unpick')}; thumbs = pg.evaluate(BOX, '[data-testid=strip-saved], [data-testid=strip-pending]')
            check(f'[E7 · M-e7-stripsmall fails here] at {W} px the strip\'s delete and remove controls are at least 44 × 44 px, and every thumbnail keeps its 56 × 56',
                  len(sizes['strip-delete']) == 9 and len(sizes['strip-unpick']) == 1 and all(w >= 44 and h >= 44 for v in sizes.values() for w, h in v) and thumbs == [[56, 56]] * 10, (sizes, thumbs[:2]))
        pg.set_viewport_size({'width': 390, 'height': 844})
        ctx.close()

        # ══ ACROSS DEVICES — the field travels with the bird record ══
        print('sync — `mainPhotoId` between two devices of one account')
        STUB = 'https://stub.example.test'
        class Server:
            def __init__(self): self.rows = {}; self.seq = 0
            def upsert(self, o, r): self.seq += 1; row = dict(r, server_seq=self.seq, owner=o); self.rows[(o, r['store'], r['record_id'])] = row; return row
            def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
        S = Server()
        def handler(route, request):
            if no_bucket(route, request): return          # this suite's project has no photo bucket: the records travel, the bytes stay
            if '/auth/v1/token' in request.url:
                body = json.loads(request.post_data or '{}'); who = (body.get('email') or 'a@').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
                route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}})); return
            who = 'user-' + (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
            if request.method == 'POST':
                rows = json.loads(request.post_data or '[]'); route.fulfill(status=200, content_type='application/json', body=json.dumps([S.upsert(who, r) for r in rows])); return
            c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); route.fulfill(status=200, content_type='application/json', body=json.dumps(S.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))))
        def device():
            c = NET.arm(check=check, ctx=b.new_context(viewport={'width': 390, 'height': 844}))
            c.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }}; globalThis.__ZAJIL_TEST_NO_AUTOSYNC = true;"); c.route(f'{STUB}/**', handler)
            d = c.new_page(); d.errs = []; d.on('pageerror', lambda e, _p=d: d.errs.append(perr(e, _p))); PAGES.append(d)
            d.goto(HARNESS, wait_until='load', timeout=30000); d.wait_for_function('window.__zajilReady', timeout=30000); run(d, "async (db, e) => { await db.signIn(e, 'pw'); }", 'photos@zajil.test'); return c, d
        def sync(d): run(d, "async (db) => { await db.syncNow(); }"); d.wait_for_timeout(200)
        VIEW2 = """async (db, id) => { const e = window.__zajilEngine; const b = db.getBird(id); const rows = await db.mediaForBird(id); const main = db.mainPhotoOf(rows, b && b.mainPhotoId);
            return { has: !!b && 'mainPhotoId' in b, field: b ? b.mainPhotoId || null : null, order: rows.map(r => r.name), main: main ? main.name : null,
                     integrity: e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents, lofts: db.state.lofts }).length,
                     anomalies: (await db.listSyncAnomalies()).length, record: JSON.stringify(b, (k, v) => (v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map(x => [x, v[x]])) : v)) }; }"""
        c1, d1 = device()
        two = run(d1, """async (db) => { const c = document.createElement('canvas'); c.width = 24; c.height = 24; const blob = await new Promise(r => c.toBlob(r, 'image/png'));
            const bird = (await db.saveBird(db.newBird({ name: 'طير الجهازين', sex: 'cock' }))).id; const one = (await db.addMedia(bird, 'photo', 'body', 'one.png', blob)).id; const two = (await db.addMedia(bird, 'photo', 'body', 'two.png', blob)).id;
            await db.setMainPhoto(bird, two); return { bird, one, two }; }""")
        sync(d1); c2, d2 = device(); sync(d2)
        settle(d2, "async (id) => { const db = await window.__zajilDb; return !!db.getBird(id) && (await db.mediaForBird(id)).length === 2; }", arg=two['bird'], timeout=15000)
        v1 = run(d1, VIEW2, two['bird']); v2 = run(d2, VIEW2, two['bird']); row = S.rows.get(('user-PHOTOS', 'birds', two['bird']))
        check('[sync · M-sync-drop fails here] device 1 chooses a main photo and syncs; device 2 pulls: its bird record names the same photo, which is its main photo and first in its order',
              v2['field'] == two['two'] and v2['main'] == 'two.png' and v2['order'] == ['two.png', 'one.png'] and bool(row) and row['data'].get('mainPhotoId') == two['two'], (v2, row and row['data'].get('mainPhotoId')))
        check('[sync] …and the two devices hold the same bird record', v1['record'] == v2['record'], (v1['record'][:200], v2['record'][:200]))
        run(d2, "async (db, id, m) => { await db.setMainPhoto(id, m); }", two['bird'], two['one']); sync(d2); sync(d1); v1 = run(d1, VIEW2, two['bird'])
        check('[sync] device 2 chooses the other photo and syncs; device 1 pulls it back: its record names that one now', v1['field'] == two['one'] and v1['order'] == ['one.png', 'two.png'], v1)
        run(d2, "async (db, m) => { await db.deleteMedia(m); }", two['one']); sync(d2); sync(d1); sync(d2); sync(d1)
        v1 = run(d1, VIEW2, two['bird']); v2 = run(d2, VIEW2, two['bird']); row = S.rows.get(('user-PHOTOS', 'birds', two['bird']))
        check('[sync] device 2 deletes the main photo and syncs; on device 1 the photo is gone, the field is gone with it, and the photo left is the main one',
              v1['has'] is False and v1['order'] == ['two.png'] and v1['main'] == 'two.png' and 'mainPhotoId' not in row['data'], (v1, sorted(row['data'].keys())[:30]))
        check('[sync] both devices hold the same bird record; integrity is empty and no sync anomaly is recorded on either', v1['record'] == v2['record'] and v1['integrity'] == v2['integrity'] == 0 and v1['anomalies'] == v2['anomalies'] == 0, (v1['integrity'], v2['integrity'], v1['anomalies'], v2['anomalies']))
        c1.close(); c2.close()

        check(f'zero page errors across {len(PAGES)} devices', len(PAGES) == 3 and not any(d.errs for d in PAGES), [e[:160] for d in PAGES for e in d.errs][:3])
        NET.assert_empty(check)
        b.close()
except Stop as why:
    check(f'[stopped] {why} — the sections after this one were not run', False)
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
