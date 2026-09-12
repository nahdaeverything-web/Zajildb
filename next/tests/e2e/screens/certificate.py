#!/usr/bin/env python3
"""Certificate (/cert?id=) — every control certificate-v1 designs and every claim the
sheet makes, checked against the ENGINE and the record rather than against a
transcription: the COI and the ancestor count come from coi.js, the tree from
pedigreeGrid, the branding block from the loft fields RULING 2 added, and the photo
states from the media store's own "are the bytes on this device" answer.

Also proved here: the certificate's language is independent of the app's (vanilla
cert.js:44, and the spec's «مستقلة عن لغة التطبيق»), the @page rule is restored and
follows the format, and the print rules leave the sheet unscaled.

Binds to data-testid only. Provisions its own server (R6)."""
import base64
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
sys.path.insert(0, HERE)
from _serve import serve                       # noqa: E402
from _layout import check_clearance, check_toast_clear, wait_toasts_clear   # noqa: E402

FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'certificate')); os.makedirs(FID, exist_ok=True)
passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def run(pg, fn, arg=None):
    return pg.evaluate("async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }" % fn, arg)


def shots(pg, name, widths=(430, 900, 1400)):
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(350)
        pg.screenshot(path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(250)


# what the sheet must say, computed here from the engine
EXPECT = """(db, a) => {
  const e = window.__zajilEngine;
  const anc = a.depth - 1;                      // the certificate counts the subject as generation 1
  const grid = e.pedigree.pedigreeGrid(db.getBird, a.id, anc);
  const { coi } = e.coi.inbreeding(db.getBird, a.id, anc);
  const loss = e.coi.ancestorLoss(db.getBird, a.id, anc);
  const names = [];
  for (let g = 1; g <= anc; g++) for (const s of grid[g]) if (s && s.bird) names.push(s.bird.name);
  const seen = new Map();
  for (let g = 1; g <= anc; g++) for (const s of grid[g]) if (s) seen.set(s.id, (seen.get(s.id) || 0) + 1);
  return { coi, filled: loss.filled, total: loss.total, names,
           slots: grid.slice(1, anc + 1).reduce((n, row) => n + row.length, 0),
           common: [...seen.values()].filter(n => n > 1).length };
}"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 900})
        boot = ctx.new_page(); boot.goto(HARNESS, wait_until='load'); boot.wait_for_timeout(600)
        boot.evaluate("async () => { await window.__zajilReady; }")
        boot.evaluate("""async () => { const db = await window.__zajilDb;
            await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge'); }""")
        # RULING 2's fields, filled the way the الأدوات card fills them
        boot.evaluate("""async (logo) => { const db = await window.__zajilDb; const l = db.currentLoft();
            const bytes = Uint8Array.from(atob(logo), c => c.charCodeAt(0));
            const m = await db.addMedia(l.id, 'document', 'logo', 'logo.png', new Blob([bytes], { type: 'image/png' }));
            await db.Lofts.save({ ...l, name: 'لوفت الفحيص', location: 'الفحيص',
                breederName: 'خالد الحدّاد', phone: '+962795123344', website: 'fuheis-loft.jo', logoMediaId: m.id }); }""",
            base64.b64encode(PNG).decode())
        # a subject with a deep pedigree, so 5 generations really has something in them
        target = boot.evaluate("""async () => { const db = await window.__zajilDb;
            const deep = db.allBirds().filter(b => b.sireId && b.damId)
              .map(b => { const s = db.getBird(b.sireId), d = db.getBird(b.damId);
                          return { id: b.id, name: b.name, score: (s && s.sireId ? 1 : 0) + (d && d.damId ? 1 : 0) }; })
              .sort((x, y) => y.score - x.score);
            return deep[0]; }""")
        CERT = f'{ROOT}cert.html?id={target["id"]}'

        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(CERT, wait_until='load'); pg.wait_for_selector('[data-testid=sheet]', timeout=10000)

        # ── the screen's own shape ──
        check('the options panel and the preview are both there, with the bird named in the crumb',
              pg.locator('[data-testid=panel]').count() == 1 and pg.locator('[data-testid=stage]').count() == 1
              and target['name'] in pg.locator('[data-testid=crumb]').inner_text(),
              pg.locator('[data-testid=crumb]').inner_text().replace('\n', ' '))
        check('[spec: "app screen, no tab bar"] the tab bar is gone and the panel\'s own bar takes its place',
              pg.locator('nav[data-bottom-chrome=tabbar]').count() == 0
              and pg.evaluate("() => !!document.querySelector('[data-bottom-chrome=cert-cta]')"))
        check('a wide screen opens on A4, which is the format the certificate is designed for',
              pg.locator('[data-testid=sheet]').get_attribute('data-format') == 'a4')
        check('…and every control the spec draws is present: format, depth, language, three photo rows, the loft block',
              all(pg.locator(f'[data-testid={x}]').count() == 1 for x in
                  ['sec-format', 'sec-depth', 'sec-lang', 'sec-photos', 'sec-brand', 'row-bird', 'row-sire', 'row-dam', 'fields']))
        check('…and the two CTAs, «مشاركة» and «طباعة»',
              pg.locator('[data-testid=share]').inner_text().strip() == 'مشاركة'
              and pg.locator('[data-testid=print]').inner_text().strip() == 'طباعة')

        # ── the sheet's numbers come from the engine ──
        for depth in (5, 4, 3):
            pg.click(f'[data-testid=depth-{depth}]'); pg.wait_for_timeout(500)
            exp = run(pg, EXPECT, {'id': target['id'], 'depth': depth})
            shown = pg.locator('[data-testid=coi]').inner_text()
            pct = f"{exp['coi'] * 100:.1f}".rstrip('0').rstrip('.')
            check(f'[{depth} gens] the COI on the sheet is the engine\'s, at the depth the certificate states',
                  (pct + '%') in shown.replace('٫', '.') or f"{exp['coi'] * 100:.1f}%" in shown,
                  f"engine {exp['coi'] * 100:.1f}% vs sheet {shown.splitlines()[0]}")
            check(f'[{depth} gens] …and the ancestor count under it is ancestorLoss at the SAME depth',
                  str(exp['filled']) in shown and str(exp['total']) in shown,
                  f"{exp['filled']}/{exp['total']} vs «{' '.join(shown.split()[-6:])}»")
            visible = pg.evaluate("""() => [...document.querySelectorAll('[data-testid=sheet-node]')]
                .filter(n => n.checkVisibility({contentVisibilityAuto:true})).length""")
            check(f'[{depth} gens] …and the tree shows exactly the slots that depth has, no more',
                  visible == exp['slots'], f'{visible} drawn vs {exp["slots"]} in the grid')

        pg.click('[data-testid=depth-5]'); pg.wait_for_timeout(500)
        exp5 = run(pg, EXPECT, {'id': target['id'], 'depth': 5})
        sheet = pg.locator('[data-testid=sheet]').inner_text()
        missing = [n for n in exp5['names'] if n and n not in sheet]
        check('every recorded ancestor in the chosen depth is printed, by the name the record holds',
              not missing, f'{len(missing)} missing: {missing[:3]}')
        unrecorded = pg.locator('[data-testid=sheet-node][data-recorded=no]').count()
        check('…and every slot the record cannot fill says «غير معروف» rather than being left blank',
              unrecorded == exp5['slots'] - len(exp5['names']) and (unrecorded == 0 or 'غير معروف' in sheet),
              f"{unrecorded} labelled vs {exp5['slots'] - len(exp5['names'])} empty slots")

        # ── RULING 2: the branding block reads the loft record ──
        loft = pg.locator('[data-testid=loft-block]').inner_text()
        check('[RULING 2] the branding block prints the loft name, the breeder, the phone and the website from the record',
              all(x in loft for x in ['لوفت الفحيص', 'خالد الحدّاد', '+962795123344', 'fuheis-loft.jo']),
              loft.replace('\n', ' '))
        check('[RULING 2] …and the logo is the image on this device, not a placeholder',
              pg.locator('[data-testid=loft-block] img').count() == 1)
        check('the QR slot is drawn and says plainly that the page it points to does not exist yet',
              'قريبًا' in pg.locator('[data-testid=qr]').inner_text(), pg.locator('[data-testid=qr]').inner_text().replace('\n', ' '))
        pg.click('[data-testid=sw-brand]'); pg.wait_for_timeout(400)
        check('turning the loft block off removes it from the sheet — that is what the switch is for',
              pg.evaluate("() => { const el = document.querySelector('[data-testid=loft-block]'); return !el || !el.checkVisibility({contentVisibilityAuto:true}); }")
              and pg.locator('[data-testid=fields]').count() == 0)
        pg.click('[data-testid=sw-brand]'); pg.wait_for_timeout(400)

        # the panel edits the ONE loft record
        pg.fill('[data-testid=f-breeder]', 'أبو زاجل'); pg.locator('[data-testid=f-breeder]').blur(); pg.wait_for_timeout(600)
        check('an edit in the panel is an edit to the loft record, not a preview-only value',
              run(pg, "(db) => db.currentLoft().breederName") == 'أبو زاجل'
              and 'أبو زاجل' in pg.locator('[data-testid=loft-block]').inner_text())
        pg.fill('[data-testid=f-breeder]', 'خالد الحدّاد'); pg.locator('[data-testid=f-breeder]').blur(); pg.wait_for_timeout(600)
        shots(pg, 'a4-ar')

        # ── content language, independent of the app language ──
        check('the language control says outright that it is independent of the app language',
              'مستقلة عن لغة التطبيق' in pg.locator('[data-testid=sec-lang]').inner_text())
        pg.click('[data-testid=lang-en]'); pg.wait_for_timeout(600)
        en = pg.locator('[data-testid=sheet]').inner_text()
        check('an English certificate prints in English',
              'Pedigree certificate' in en and 'Inbreeding coefficient' in en and 'Sex' in en,
              en.splitlines()[0] if en else '')
        check('…laid out left-to-right, as its own language requires',
              pg.locator('[data-testid=sheet]').get_attribute('dir') == 'ltr')
        check('…while the APP around it is untouched — still Arabic, still RTL',
              pg.evaluate("() => document.documentElement.dir") == 'rtl'
              and pg.evaluate("() => document.documentElement.lang") == 'ar'
              and 'الأجيال' in pg.locator('[data-testid=panel]').inner_text(),
              f"html dir={pg.evaluate('() => document.documentElement.dir')}")
        check('…and the same numbers, in the same places', str(exp5['filled']) in en and str(exp5['total']) in en)
        shots(pg, 'a4-en', widths=(1400,))
        pg.click('[data-testid=lang-ar]'); pg.wait_for_timeout(600)

        # ── photos: three states, from the media store ──
        d_bird = pg.locator('[data-testid=d-bird]').inner_text()
        check('a bird with no photo says so, and offers to choose one',
              'لا صورة بعد' in d_bird and pg.locator('[data-testid=pick-bird]').inner_text().strip() == 'اختيار صورة', d_bird)
        check('…and with the photo off, the sheet carries none',
              pg.locator('[data-testid=sheet-photo-bird]').count() == 0)
        pg.set_input_files('[data-testid=photo-input]', files=[{'name': 'bird.png', 'mimeType': 'image/png', 'buffer': PNG}])
        pg.wait_for_timeout(900)
        check('choosing a photo here files it on the BIRD, not on the certificate',
              run(pg, "async (db, a) => (await db.mediaForBird(a.id)).filter(m => m.kind === 'photo').length", {'id': target['id']}) == 1)
        check('…the row switches to «من ملف الطائر», and the switch comes on',
              'من ملف الطائر' in pg.locator('[data-testid=d-bird]').inner_text()
              and pg.locator('[data-testid=sw-bird]').get_attribute('aria-pressed') == 'true',
              pg.locator('[data-testid=d-bird]').inner_text())
        check('…and the sheet now carries the image',
              pg.locator('[data-testid=sheet-photo-bird] img').count() == 1)
        # a photo whose bytes live on another device — metadata synced, blob did not
        sire_id = run(pg, "(db, a) => db.getBird(a.id).sireId", {'id': target['id']})
        run(pg, """async (db, a) => { const m = await db.addMedia(a.sire, 'photo', 'body', 'sire.png', new Blob(['x']));
            const row = await db.idbGet('media', m.id); delete row.blob; await db.idbPut('media', row);
            db.emitChange({ type: 'media', id: m.id, birdId: a.sire }); }""", {'sire': sire_id})
        pg.wait_for_timeout(900)
        check('a photo whose bytes are on ANOTHER device says exactly that, and offers to choose one here',
              'الصورة على جهاز آخر' in pg.locator('[data-testid=d-sire]').inner_text()
              and pg.locator('[data-testid=pick-sire]').inner_text().strip() == 'اختيار هنا',
              pg.locator('[data-testid=d-sire]').inner_text().replace('\n', ' '))
        pg.click('[data-testid=sw-sire]'); pg.wait_for_timeout(500)
        check('…and switched on, the sheet draws the empty slot with the same sentence — never a broken image',
              pg.locator('[data-testid=sheet-photo-sire]').count() == 1
              and pg.locator('[data-testid=sheet-photo-sire] img').count() == 0
              and 'الصورة على جهاز آخر' in pg.locator('[data-testid=sheet]').inner_text())
        shots(pg, 'a4-photos', widths=(1400,))

        # ── the 9:16 sheet ──
        pg.click('[data-testid=format-story]'); pg.wait_for_timeout(700)
        check('the phone format is a different sheet, not the same one cropped',
              pg.locator('[data-testid=sheet]').get_attribute('data-format') == 'story'
              and pg.locator('[data-testid=sheet] section').count() >= 2)
        st = pg.locator('[data-testid=sheet]').inner_text()
        check('…and it still carries the whole claim: the subject, every generation, the COI and the branding',
              all(x in st for x in [target['name'], 'معامل التربية الداخلية', 'لوفت الفحيص'])
              and len([n for n in exp5['names'] if n and n in st]) == len([n for n in exp5['names'] if n]),
              st.replace('\n', ' ')[:80])
        check('…in 9:16 — the aspect the caption promises',
              abs(pg.evaluate("() => { const r = document.querySelector('[data-testid=sheet]').getBoundingClientRect(); return r.width / r.height; }") - 405 / 720) < 0.01)
        shots(pg, 'story-ar', widths=(430, 1400))

        # ── the restored @page ──
        check('[restored @page] the phone sheet asks the printer for its own page size',
              pg.locator('[data-testid=pagesize]').inner_text().strip() == '@page{ size:108mm 192mm; margin:0; }',
              pg.locator('[data-testid=pagesize]').inner_text())
        pg.click('[data-testid=format-a4]'); pg.wait_for_timeout(700)
        check('[restored @page] …and A4 asks for A4 landscape, switching with the format as the spec does',
              pg.locator('[data-testid=pagesize]').inner_text().strip() == '@page{ size:A4 landscape; margin:0; }',
              pg.locator('[data-testid=pagesize]').inner_text())

        # ── print rules ──
        pg.emulate_media(media='print'); pg.wait_for_timeout(400)
        printed = pg.evaluate("""() => {
          const vis = (sel) => { const el = document.querySelector(sel); return !!el && el.checkVisibility({contentVisibilityAuto:true}); };
          const sheet = document.querySelector('[data-testid=sheet]');
          return { panel: vis('[data-testid=panel]'), cap: vis('[data-testid=cap]'), sheet: vis('[data-testid=sheet]'),
                   transform: getComputedStyle(sheet).transform, position: getComputedStyle(sheet).position }; }""")
        check('printing drops the options panel and the preview caption — a certificate, not a screenshot of a screen',
              printed['panel'] is False and printed['cap'] is False and printed['sheet'] is True, str(printed))
        check('…and the sheet prints at its true size, unscaled and unpositioned',
              printed['transform'] in ('none', 'matrix(1, 0, 0, 1, 0, 0)') and printed['position'] == 'static', str(printed))
        pg.emulate_media(media='screen'); pg.wait_for_timeout(300)

        # ── the phone: scaled preview and «تكبير» ──
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(700)
        fits = pg.evaluate("""() => { const st = document.querySelector('[data-testid=stage]');
            return { stage: Math.round(st.getBoundingClientRect().width), doc: Math.round(document.documentElement.scrollWidth),
                     vw: innerWidth }; }""")
        check('on a phone the A4 sheet is scaled to fit — the page never scrolls sideways',
              fits['doc'] <= fits['vw'] + 1, str(fits))
        check('…and «تكبير» is offered, because a scaled A4 is not readable',
              pg.locator('[data-testid=zoom-open]').is_visible()
              and pg.locator('[data-testid=zoom-open]').inner_text().strip().endswith('تكبير'))
        pg.click('[data-testid=zoom-open]'); pg.wait_for_selector('[data-testid=zoom]', timeout=5000)
        check('…which opens a full-screen reading mode with the spec\'s three levels',
              pg.locator('[data-testid=zoom] [data-testid=sheet]').count() == 1
              and all(pg.locator(f'[data-testid="zoom-{z}"]').count() == 1 for z in ['1', '0.7', 'fit']))
        at70 = pg.evaluate("() => document.querySelector('[data-testid=zscroll] [data-testid=sheet]').getBoundingClientRect().width")
        pg.click('[data-testid="zoom-1"]'); pg.wait_for_timeout(400)
        at100 = pg.evaluate("() => document.querySelector('[data-testid=zscroll] [data-testid=sheet]').getBoundingClientRect().width")
        check('…and the levels really change the size', at100 > at70 * 1.3, f'{round(at70)} -> {round(at100)}')
        pg.screenshot(path=f'{FID}/zoom-430.png', full_page=False)
        pg.click('[data-testid=zoom-close]'); pg.wait_for_timeout(400)
        check('…and closing it gives the page back', pg.locator('[data-testid=zoom]').count() == 0
              and pg.evaluate("() => document.body.style.overflow") == '')

        # ── ruling C ──
        # The spec declares `.cta{ position:fixed }` inside the <=700px block and
        # `.cta{ position:sticky }` AFTER it, so at one-class specificity the sticky rule
        # wins and the prototype's bar is sticky at every width. The port renders what the
        # spec renders; what matters for ruling C is that the bar reaches the fancier and
        # hides nothing, and that is asserted rather than assumed.
        pg.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(350)
        cta = pg.evaluate("""() => { const el = document.querySelector('[data-bottom-chrome=cert-cta]');
            const r = el.getBoundingClientRect();
            return { top: Math.round(r.top), bottom: Math.round(r.bottom), vh: innerHeight,
                     pos: getComputedStyle(el).position }; }""")
        check('the panel\'s own action bar is on screen at the phone width, not scrolled off the end',
              cta['bottom'] <= cta['vh'] + 1 and cta['top'] < cta['vh'], str(cta))
        check_clearance(pg, check, 'certificate')
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(300)
        # LAYER DEFECT (raised in the 4D report): exportBirdWithAncestry with includeMedia
        # reads every media row through blobToDataURL (db/io.js:237), and by now the sire's
        # photo is metadata-only — the ordinary state after a sync, where the bytes stayed on
        # the other device. readAsDataURL(undefined) throws, so the share rejects. What is
        # asserted here is the UI's contract, which holds either way: a share ALWAYS answers.
        layer = pg.evaluate("""async (id) => { const db = await window.__zajilDb;
            try { await db.exportBirdWithAncestry(id, { includeRaces: true, includeMedia: true }); return 'ok'; }
            catch (e) { return 'rejects: ' + e.message; } }""", target['id'])
        pg.click('[data-testid=share]')
        pg.wait_for_selector('[data-testid=toast]', timeout=8000)
        said = pg.locator('[data-testid=toast]').last.inner_text()
        check('a share always answers — the file, or the reason it could not be made',
              ('تعذّر' in said) == layer.startswith('rejects'), f'layer {layer[:60]} · toast «{said}»')
        check_toast_clear(pg, check, 'certificate')
        wait_toasts_clear(pg)

        # ── a bird that is not there ──
        gone = ctx.new_page()
        gone.goto(f'{ROOT}cert.html?id=no-such-bird', wait_until='load'); gone.wait_for_timeout(1500)
        check('a certificate for a record that is not here goes back to the loft rather than showing an empty sheet',
              '/birds' in gone.url, gone.url.split('/')[-1])

        check('zero page errors', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
