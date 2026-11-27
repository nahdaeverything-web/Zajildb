#!/usr/bin/env python3
"""THE CERTIFICATE ON PAPER (RULED 2026-11-27, H1–H5), through Chromium's own print path.

Measured before the rulings (Chrome on Windows, A4 landscape, 5 generations, Arabic — and here, on every depth and both
languages): the far side of the sheet was cut at the page edge, the print ran to a second page, and every box printed
its ring twice. The cause of the first two: the shell's layout reached the print — at A4 landscape's 1123 px the
≥1100 px rule gives <main> the rail's margin and its children a 960 px cap.

  H1  the A4 certificate prints on exactly ONE page for 3, 4 and 5 generations in both languages; every box lies inside
      the page with a margin; no text outside it.
  H2  no text over other text, in any box, at any depth, with the longest date the app prints; no text out of its box.
  H3  a ring is printed once per box: the title is the name when there is one, otherwise the ring; the ring line is
      printed only under a name.
  H4  the same print from a 390 px phone screen: the print does not depend on the screen width.
  H5  the 9:16 image: one page of 108 × 192 mm, inside the frame, no overlap, the ring once.

Each print is made twice over: page.pdf with the page's own @page rule (the page count and size are read from the PDF),
and the same page with print media emulated at the page's own width (every box and every line of visible text is read
from the layout). Synthetic birds; names are invented words. A check that names a mutant is the one that mutant fails at.

    python3 tests/e2e/screens/cert_print.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import io, os, re, sys, tempfile
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
PAGES = []
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:600]) if not ok and d != '' else ''}")
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))
MM = 96 / 25.4
PAGE = {'a4': (297 * MM, 210 * MM), 'story': (108 * MM, 192 * MM)}
PT = {'a4': (841.89, 595.28), 'story': (306.14, 544.25)}
MARGIN_MM = 4.5

# the longest date the app prints, both calendars: searched over 31 years, per language
LONGEST = """() => { const out = {};
  for (const lang of ['ar', 'en']) { let best = null;
    for (const ld = new Date(2000, 0, 1); ld.getFullYear() <= 2030; ld.setDate(ld.getDate() + 1)) { const p2 = (x) => String(x).padStart(2, '0'); const iso = `${ld.getFullYear()}-${p2(ld.getMonth() + 1)}-${p2(ld.getDate())}`;
      const s = ld.toLocaleDateString((lang === 'ar' ? 'ar-JO' : 'en-GB') + '-u-nu-latn', { year: 'numeric', month: 'short', day: 'numeric' }) + ' (' + ld.toLocaleDateString((lang === 'ar' ? 'ar-SA' : 'en') + '-u-ca-islamic-umalqura-nu-latn', { year: 'numeric', month: 'long', day: 'numeric' }) + ')';
      if (!best || s.length > best.s.length) best = { iso, s }; }
    out[lang] = best; }
  return out; }"""
SEED = """async (db, dates) => {
  const R = (s) => window.__zajilEngine.rings.parseRing(s);
  const L = db.currentLoft(); if (L) await db.Lofts.save({ ...L, name: 'لوفت الريح الشمالية', breederName: 'مربٍّ للتجربة', phone: '+962 79 000 0000', website: 'loft.example.test' });
  const AR = ['نجم الشمال', 'سحابة الفجر', 'برق الصحراء', 'ريح الجنوب', 'قمر الليل', 'غيمة البحر', 'سهم الذهب', 'وردة الوادي'];
  let n = 0;
  const tree = async (depth, sex, named, long) => { let sireId = null, damId = null;
    if (depth > 1) { sireId = await tree(depth - 1, 'cock', named, long); damId = await tree(depth - 1, 'hen', named, long); }
    n++; const b = db.newBird({ name: !named ? '' : long ? `${AR[n % 8]} ابن ${AR[(n + 3) % 8]} ${n}` : AR[n % 8] + ' ' + n, sex, external: true, rings: [R(`BE-20${10 + (n % 10)}-${4100000 + n}`)], sireId, damId });
    return (await db.saveBird(b, { allowWarnings: true })).id; };
  const subject = async (fields, withParents, named, long = false) => { let sireId = null, damId = null;
    if (withParents) { sireId = await tree(4, 'cock', named, long); damId = await tree(4, 'hen', named, long); }
    return (await db.saveBird(db.newBird({ sex: 'cock', colour: 'أزرق مخطط بريش أبيض', strain: 'يانسن × فان لون', ...fields, sireId, damId }), { allowWarnings: true })).id; };
  return {
    long: await subject({ name: 'سلطان الريح الشمالية الذهبي ابن نجمة الصحراء', rings: [R('JO-2024-1234567')], hatchDate: dates.ar.iso }, true, true, true),
    noname: await subject({ name: '', rings: [R('BE-2023-6012345')], hatchDate: dates.en.iso }, true, false),
    unknown: await subject({ name: 'طير بلا أبوين معروفين', rings: [R('JO-2025-7654321')], hatchDate: dates.ar.iso }, false, true),
  }; }"""

# every box and every VISIBLE line of text of the sheet, in page coordinates (the page's origin is the document's: @page margin 0)
DOM = """(page) => { const S = document.querySelector('[data-testid=sheet]'); if (!S) return null;
  const R = (el) => { const r = el.getBoundingClientRect(); return [r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY]; };
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const cls = (el, k) => [...el.classList].some(c => c === k || c.endsWith('__' + k));
  const boxes = []; const add = (name, el) => { if (el && vis(el)) boxes.push({ name, r: R(el) }); };
  add('head', S.querySelector('header')); add('issue date', S.querySelector('[data-testid=issued]')); add('subject', S.querySelector('[data-testid=subject]')); add('subject title', S.querySelector('[data-testid=subject-title]'));
  S.querySelectorAll('[data-testid=facts] > div').forEach((c, i) => add('fact ' + ['sex', 'hatch', 'colour', 'strain'][i], c));
  S.querySelectorAll('[data-testid=sheet-node]').forEach((e, i) => add('box ' + i, e));
  add('footer', S.querySelector('footer')); add('coi', S.querySelector('[data-testid=coi]')); add('loft block', S.querySelector('[data-testid=loft-block]')); add('qr', S.querySelector('[data-testid=qr]'));
  [...S.querySelectorAll('*')].filter(e => cls(e, 'verify') || cls(e, 'ruler') || cls(e, 'brandrow') || cls(e, 'bands')).forEach(e => add(e.className.split('__').pop(), e));
  const [PW, PH] = page; const mm = 96 / 25.4;
  const edge = (r) => Math.min(r[0], r[1], PW - r[2], PH - r[3]) / mm;
  const texts = []; const tw = document.createTreeWalker(S, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) { if (!n.textContent.trim() || !vis(n.parentElement)) continue;
    const clips = []; for (let a = n.parentElement; a && a !== S.parentElement; a = a.parentElement) { const cs = getComputedStyle(a); if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') clips.push(R(a)); }
    const cut = (r) => clips.reduce((x, c) => [Math.max(x[0], c[0]), Math.max(x[1], c[1]), Math.min(x[2], c[2]), Math.min(x[3], c[3])], r);
    const rg = document.createRange(); rg.selectNodeContents(n);
    const rs = [...rg.getClientRects()].map(r => cut([r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY])).filter(r => r[2] - r[0] > 0.5 && r[3] - r[1] > 0.5);
    if (rs.length) texts.push({ t: n.textContent.trim().slice(0, 36), el: n.parentElement, rs }); }
  const textOut = texts.filter(x => x.rs.some(r => r[0] < -0.5 || r[1] < -0.5 || r[2] > PW + 0.5 || r[3] > PH + 0.5)).map(x => x.t);
  const overlaps = []; for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) for (const a of texts[i].rs) for (const b of texts[j].rs) {
    const w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
    if (w > 2 && h > 0.25 * Math.min(a[3] - a[1], b[3] - b[1])) overlaps.push([texts[i].t, texts[j].t]); }
  const own = (el) => el.closest('[data-testid=sheet-node], [data-testid=facts] > div, [data-testid=coi], [data-testid=loft-block], [data-testid=qr], [class*="__verify"]');
  const spill = texts.filter(x => { const o = own(x.el); if (!o) return false; const b = R(o); return x.rs.some(r => r[0] < b[0] - 1 || r[2] > b[2] + 1 || r[1] < b[1] - 3 || r[3] > b[3] + 3); }).map(x => x.t);
  const RING = /[A-Z]{2}-\\d{4}-\\d+/g;
  const node = (e) => { const nm = e.querySelector('[class*="__nm"]'), rg = e.querySelector('[class*="__rg"]'); return { title: nm ? nm.innerText.trim() : '', ring: rg ? rg.innerText.trim() : null, rings: (e.innerText.match(RING) || []).length }; };
  const subj = S.querySelector('[data-testid=subject]') || S.querySelector('[class*="__subj"]');
  const plate = S.querySelector('[data-testid=plate]');
  return { boxes: boxes.map(b => ({ ...b, edge: +edge(b.r).toFixed(2) })), textOut, overlaps, spill, nodes: [...S.querySelectorAll('[data-testid=sheet-node]')].filter(vis).map(node),
           subject: { title: (S.querySelector('[data-testid=subject-title]') || {}).innerText || '', plate: plate ? plate.innerText.replace(/\\s+/g, ' ').trim() : null,
                      rings: subj ? ([...subj.childNodes].filter(c => !(c.dataset && c.dataset.testid === 'facts')).map(c => c.textContent).join(' ').match(RING) || []).length : 0 },
           // the hatch date: its text inside its own cell, and that cell inside the box that holds the facts (the subject's box
           // on A4, the sheet's padded frame on 9:16) — a cell that grows to hold an unbroken date pushes out of that box
           hatchIn: (() => { const c = S.querySelectorAll('[data-testid=facts] > div')[1]; if (!c) return null; const b = R(c); const rg = document.createRange(); rg.selectNodeContents(c.lastElementChild);
                             const sub = S.querySelector('[data-testid=subject]'); const f = sub ? R(sub) : (() => { const r = R(S), cs = getComputedStyle(S); return [r[0] + parseFloat(cs.paddingLeft), r[1], r[2] - parseFloat(cs.paddingRight), r[3]]; })();
                             return [...rg.getClientRects()].every(r => r.left + scrollX >= b[0] - 1 && r.right + scrollX <= b[2] + 1) && b[0] >= f[0] - 1 && b[2] <= f[2] + 1; })() }; }"""

def certificate(pg, bid, fmt, depth, lang):
    pg.goto(f'{ROOT}cert/?id={bid}', wait_until='load'); pg.wait_for_selector('[data-testid=sheet]', timeout=15000)
    for sel in (f'format-{fmt}', f'depth-{depth}', f'lang-{lang}'):
        try: pg.click(f'[data-testid={sel}]', timeout=5000); pg.wait_for_timeout(100)
        except Exception: pass
    try: pg.wait_for_function("(a) => { const p = document.querySelector('[data-testid=state-probe]'); return p && p.dataset.format === a[0] && p.dataset.depth === String(a[1]) && p.dataset.lang === a[2]; }", arg=[fmt, depth, lang], timeout=8000)
    except Exception: pass
    pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(300)

def printed(pg, fmt, W, H):
    """The PDF (pages, size in pt) and the layout as printed."""
    pdf = pg.pdf(prefer_css_page_size=True); r = PdfReader(io.BytesIO(pdf)); mb = r.pages[0].mediabox
    PW, PH = PAGE[fmt]
    pg.set_viewport_size({'width': round(PW), 'height': round(PH)}); pg.emulate_media(media='print'); pg.evaluate('window.scrollTo(0, 0)'); pg.wait_for_timeout(200)
    d = pg.evaluate(DOM, [PW, PH])
    pg.emulate_media(media='null'); pg.set_viewport_size({'width': W, 'height': H}); pg.wait_for_timeout(120)
    return {'pages': len(r.pages), 'size': (float(mb.width), float(mb.height)), **(d or {'boxes': [], 'textOut': ['NO SHEET'], 'overlaps': [], 'spill': [], 'nodes': [], 'subject': {}, 'hatchIn': None})}

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        def device(W, H):
            ctx = b.new_context(viewport={'width': W, 'height': H}, locale='ar-JO', timezone_id='Asia/Amman', has_touch=(W < 700))
            pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
            pg.goto(HARNESS, wait_until='load', timeout=30000); pg.wait_for_function('window.__zajilReady', timeout=30000)
            dates = pg.evaluate(LONGEST); return ctx, pg, dates, run(pg, SEED, dates)
        ctx, pg, dates, ids = device(1280, 800)
        print(f"the longest dates the app prints: ar «{dates['ar']['s']}» ({dates['ar']['iso']}) · en «{dates['en']['s']}» ({dates['en']['iso']})")

        A4 = [('long', d, l) for d in (3, 4, 5) for l in ('ar', 'en')] + [('noname', 5, 'ar'), ('noname', 3, 'en'), ('unknown', 5, 'ar'), ('unknown', 4, 'en')]
        res = {}
        for who, depth, lang in A4:
            certificate(pg, ids[who], 'a4', depth, lang); res[(who, depth, lang)] = printed(pg, 'a4', 1280, 800)
        def line(k): r = res[k]; return f"{k[0]} d{k[1]} {k[2]}: pages {r['pages']} · {r['size'][0]:.1f}×{r['size'][1]:.1f} pt · nearest box {min((x['edge'] for x in r['boxes']), default=None)} mm · text outside {len(r['textOut'])} · overlaps {len(r['overlaps'])} · out of its box {len(r['spill'])}"
        for k in res: print('   ', line(k))

        # ══ H1 ══
        print('H1 — the A4 certificate prints on one page, nothing cut, every box inside the page with a margin')
        one = {k: (r['pages'], round(r['size'][0]), round(r['size'][1])) for k, r in res.items()}
        check('[H1 · M-h1-iso fails here] every A4 print — 3, 4 and 5 generations, Arabic and English, three birds — is exactly ONE page of A4 landscape (842 × 595 pt)',
              all(v == (1, 842, 595) for v in one.values()), {f'{k[0]} d{k[1]} {k[2]}': v for k, v in one.items() if v != (1, 842, 595)})
        inside = {k: [x['name'] for x in r['boxes'] if x['edge'] < MARGIN_MM] for k, r in res.items()}
        check(f'[H1 · M-h1-iso fails here] …every box of every one lies inside the page, at least {MARGIN_MM} mm from its edge, and no line of text leaves the page',
              all(not v for v in inside.values()) and all(not r['textOut'] for r in res.values()) and all(r['boxes'] for r in res.values()),
              {f'{k[0]} d{k[1]} {k[2]}': (v[:4], res[k]['textOut'][:2]) for k, v in inside.items() if v or res[k]['textOut']})

        # ══ H2 ══
        print('H2 — no text over other text, and none out of its box, with the longest names and dates')
        check('[H2 · M-h2-fit fails here] no line of text lies over another, in any box, at any depth, in either language — long names in all 30 ancestors included',
              all(not r['overlaps'] for r in res.values()), {f'{k[0]} d{k[1]} {k[2]}': r['overlaps'][:2] for k, r in res.items() if r['overlaps']})
        check('[H2 · M-h2-fit fails here] …and no line of text runs out of its own box', all(not r['spill'] for r in res.values()), {f'{k[0]} d{k[1]} {k[2]}': r['spill'][:2] for k, r in res.items() if r['spill']})
        check('[H2 · M-h2-date fails here] the longest hatch date the app prints (both calendars) stays inside its own cell, beside the sex, and that cell inside the bird\'s box — every depth, both languages',
              all(r['hatchIn'] is True for r in res.values()), {f'{k[0]} d{k[1]} {k[2]}': r['hatchIn'] for k, r in res.items() if r['hatchIn'] is not True})

        # ══ H3 ══
        print('H3 — a ring is printed once per box: the name as the title when there is one, otherwise the ring')
        L5 = res[('long', 5, 'ar')]; N5 = res[('noname', 5, 'ar')]
        named = [n for n in L5['nodes'] if n['title'] != 'غير معروف']; bare = [n for n in N5['nodes'] if n['title'] != 'غير معروف']
        check('[H3 · M-h3-twice fails here] a named ancestor\'s box: the title is its name, the ring line under it carries the ring, and the ring appears once — 30 boxes',
              len(named) == 30 and all(n['rings'] == 1 and n['ring'] and not re.search(r'[A-Z]{2}-\d{4}', n['title']) for n in named), named[:3])
        check('[H3 · M-h3-twice fails here] an ancestor with no name: the title is its ring and there is no ring line — 30 boxes',
              len(bare) == 30 and all(n['rings'] == 1 and n['ring'] is None and re.fullmatch(r'BE-\d{4}-\d+', n['title']) for n in bare), bare[:3])
        sl, sn = L5['subject'], N5['subject']
        check('[H3] the subject: a named bird\'s title is its name and its plate carries the ring once; an unnamed bird\'s title is its ring, with no plate',
              sl.get('title', '').startswith('سلطان') and sl.get('plate') and 'JO-2024-1234567' in sl['plate'] and sl.get('rings') == 1
              and sn.get('title') == 'BE-2023-6012345' and sn.get('plate') is None and sn.get('rings') == 1, (sl, sn))

        # ══ H5 — the 9:16 image ══
        print('H5 — the 9:16 image: one page of 108 × 192 mm, inside the frame, no overlap, the ring once')
        ST = [('long', 5, 'ar'), ('long', 5, 'en'), ('long', 4, 'en'), ('noname', 5, 'ar'), ('unknown', 3, 'en')]
        sres = {}
        for who, depth, lang in ST:
            certificate(pg, ids[who], 'story', depth, lang); sres[(who, depth, lang)] = printed(pg, 'story', 1280, 800)
        for k, r in sres.items(): print(f"    {k[0]} d{k[1]} {k[2]}: pages {r['pages']} · {r['size'][0]:.1f}×{r['size'][1]:.1f} pt · nearest box {min((x['edge'] for x in r['boxes']), default=None)} mm · text outside {len(r['textOut'])} · overlaps {len(r['overlaps'])} · out of its box {len(r['spill'])}")
        check('[H5 · M-h5-story fails here] every 9:16 print is one page of 108 × 192 mm; every box inside the frame with a margin; no text outside it, over other text or out of its box',
              all(r['pages'] == 1 and round(r['size'][0]) == 306 and round(r['size'][1]) == 544 and r['boxes'] and all(x['edge'] >= MARGIN_MM for x in r['boxes'])
                  and not r['textOut'] and not r['overlaps'] and not r['spill'] for r in sres.values()),
              {f'{k[0]} d{k[1]} {k[2]}': (r['pages'], [x['name'] for x in r['boxes'] if x['edge'] < MARGIN_MM][:3], r['textOut'][:2], r['overlaps'][:2], r['spill'][:2]) for k, r in sres.items()})
        SN = sres[('noname', 5, 'ar')]
        check('[H5] …and the ring once there too: an unnamed bird\'s boxes carry the ring as the title and no ring line',
              all(n['rings'] <= 1 for r in sres.values() for n in r['nodes']) and all(n['ring'] is None for n in SN['nodes'] if n['title'] != 'غير معروف') and SN['subject'].get('plate') is None,
              [n for n in SN['nodes'] if n['rings'] > 1 or n['ring'] is not None][:3])

        # ══ H4 — the same prints from a phone's screen ══
        print('H4 — printed from a 390 px phone screen: the same pages, the same boxes in the same places')
        ctx2, ph, _, ids2 = device(390, 844)
        same = {}
        for (who, depth, lang, fmt) in (('long', 5, 'ar', 'a4'), ('noname', 3, 'en', 'a4'), ('long', 5, 'en', 'story')):
            certificate(ph, ids2[who], fmt, depth, lang); a = printed(ph, fmt, 390, 844); d = (res if fmt == 'a4' else sres)[(who, depth, lang)]
            moved = [x['name'] for x, y in zip(a['boxes'], d['boxes']) if x['name'] != y['name'] or max(abs(u - v) for u, v in zip(x['r'], y['r'])) > 0.5]
            same[(who, depth, lang, fmt)] = (a['pages'], d['pages'], len(a['boxes']), len(d['boxes']), moved[:4], len(a['overlaps']), len(a['textOut']))
            print(f"    {fmt} {who} d{depth} {lang} at 390 px: pages {a['pages']} (1280 px: {d['pages']}) · boxes {len(a['boxes'])} (1280 px: {len(d['boxes'])}) · moved more than 0.5 px: {len(moved)} · overlaps {len(a['overlaps'])} · text outside {len(a['textOut'])}")
        check('[H4 · M-h4-width fails here] printed from a 390 px screen, the A4 and the 9:16 certificate are the same as from a 1280 px screen: one page, every box in the same place (within 0.5 px), no overlap',
              all(v[0] == v[1] == 1 and v[2] == v[3] > 0 and not v[4] and v[5] == 0 and v[6] == 0 for v in same.values()), same)
        ctx2.close(); ctx.close()

        check(f'zero page errors across {len(PAGES)} devices', len(PAGES) == 2 and not any(d.errs for d in PAGES), [e[:160] for d in PAGES for e in d.errs][:3])
        b.close()
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
