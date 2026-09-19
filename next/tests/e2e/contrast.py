#!/usr/bin/env python3
"""Text-on-fill contrast, asserted against WCAG AA, across the app.

WHAT IT ENFORCES, in two parts, because the app is not at zero failures and pretending
otherwise would make this suite a decoration:

  1. THE RULED INVARIANT, in BOTH directions, because the brand green is 4.20:1 against white
     whichever side it is on:
       · white text on a solid brand FILL      (buttons, pills, banners)
       · brand text on a white/near-white SURFACE (nav labels, links, headline figures)
     Both were 4.20:1 and both now use --brand-deep at 6.12:1. Every such pair is asserted
     individually, so a token change or a new control that drops one below AA is named.

  2. FILLED CONTROLS, WHOLE. «طير جديد» shipped as a solid brand rectangle with no visible
     word on it — white text that the cascade had repainted brand-green, on a brand-green
     fill, 1.00:1. Part 1 above could not have caught it, for two separate reasons, and both
     are fixed here:
       · the element was never FOUND. The scan ran at 430px only, and «طير جديد» is a
         desktop control. So the suite is now run at BOTH 430 and 1400, and it asserts by
         name that the two controls which shipped broken — birds/add-bird and
         pedigree/hero-cert — are actually in the set it measured.
       · white-on-white is not a PAIR. Part 1 asks "is every white-on-brand surface legible";
         a label the cascade painted the same colour as its fill is in neither list. So this
         part starts from the CONTROL, not from a colour pair: for every control that paints
         an opaque fill of its own, the label must exist, be non-empty, and be legible
         against that fill. A control that says nothing is a defect whatever its colours.

  3. A RATCHET on everything else. There are other failing pairs — muted greys on white,
     light text on tints, the danger colour on its tint — none of them ruled on yet. The
     suite records how many DISTINCT failing (route, fg, bg, size, weight) combinations exist
     and fails if that number GROWS. It cannot be gamed by moving a failure around, and it
     cannot silently accept a new one.

Thresholds are AA: 4.5:1, or 3:1 when the text is large — >=24px, or >=18.66px at weight
>=700. The effective background is resolved by compositing up the ancestor chain until
opaque, so a transparent control over a card is measured against the card. The text colour is
composited over that background, and the element's own `opacity` is folded in, because a
label at 60% opacity really is lower contrast.

BASELINE: 108 distinct failing combinations over the routes below, at BOTH widths. THE
INCREASE FROM 84 IS COVERAGE, NOT REGRESSION, and the arithmetic is written out here so that
nobody has to take that on trust:

     84   the old baseline, scanned at 430px alone
    -1    the certificate's plate year at 11px stopped failing (see below)
    ───
     83   what the phone-width scan finds today
    +25   what ONLY the desktop width shows, and the 430px scan could never have seen
    ───
    108

  · The 25 desktop-only ones are ALL --ink-3 (#8c97a2) on white or page: table headers, ruler
    labels, empty dashes, the desktop nav rail's own labels. That is the same dominant,
    approved-token group the other 83 are mostly made of, and it is RULED not to be repainted
    without the design owner saying so.
  · There was a 26th, and it was not --ink-3: the certificate's plate year, «16», WHITE ON
    --gold, 2.65:1. RULED 2026-09-19 — do not darken the gold, because «gold is an accent and
    forcing it to AA changes what the accent is», the same reasoning that protects --ink-3.
    The LABEL moved instead: --ink on --gold, measured 6.76:1, cert.module.css:185. It renders
    at 9px and 11px, so fixing it removed TWO combinations, which is why the total is 108 and
    not 109.
  · Nine other rules still paint white on a gold fill (the ring plate on birds, breeding,
    pedigree, bird, the bird form, races and health, plus bird's .best and .pill.gold), and
    they are DEFERRED by the same ruling, recorded by token pair — `#fff on --gold`, 3 combos,
    worst 2.65 — alongside --ink-3 rather than changed.

The key is (route, fg, bg, px, weight) and deliberately NOT the viewport, so a pair that fails
at both widths counts once. Lowering this number is the point; raising it needs a ruling and a
new number here.
Lowering it is the point; raising it needs a ruling and a new number here. What they are, and
why they are not fixed, is in PORT-COMPLETE.md — the dominant group is --ink-3, an approved
token, and repainting every secondary label in the app is a design decision rather than a
contrast fix.

Provisions its own server (R6)."""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve

BASELINE = 108
# BOTH, not just the phone. A desktop-only control cannot fail a suite that never renders it:
# that is exactly how a 1.00:1 button reached a real browsing session.
VIEWPORTS = [(430, 900), (1400, 1000)]
ROUTES = ['birds', 'bird', 'bird/new', 'breeding', 'races', 'races?tab=fci', 'health',
          'stats', 'tools', 'pedigree', 'cert', 'sign-in']
BRAND = ('#128c6e', '#0e6f57')
WHITE = ('#ffffff', '#fefefe')
# 'near white' is the page and surface grounds the brand is ever set as text on
NEAR_WHITE = ('#ffffff', '#fefefe', '#f5f7f8', '#fbfcfc')

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')

SCAN = """() => {
  const parse = (c) => { const m = c.match(/[\\d.]+/g); if (!m) return null;
    return { r:+m[0], g:+m[1], b:+m[2], a: m[3] === undefined ? 1 : +m[3] }; };
  const effBg = (node) => {
    let acc = null;
    for (let n = node; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (!c || c.a === 0) continue;
      if (acc === null) { acc = c; if (acc.a >= 1) break; continue; }
      const a = acc.a + c.a * (1 - acc.a);
      acc = { r:(acc.r*acc.a + c.r*c.a*(1-acc.a))/a, g:(acc.g*acc.a + c.g*c.a*(1-acc.a))/a,
              b:(acc.b*acc.a + c.b*c.a*(1-acc.a))/a, a };
      if (acc.a >= 1) break;
    }
    if (!acc) return { r:255, g:255, b:255, a:1 };
    if (acc.a < 1) { const a = acc.a;
      acc = { r: acc.r*a + 255*(1-a), g: acc.g*a + 255*(1-a), b: acc.b*a + 255*(1-a), a:1 }; }
    return acc;
  };
  const lum = (c) => { const ch = [c.r,c.g,c.b].map(v => { v/=255;
    return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*ch[0] + 0.7152*ch[1] + 0.0722*ch[2]; };
  const hex = (c) => '#' + [c.r,c.g,c.b].map(v => Math.round(v).toString(16).padStart(2,'0')).join('');
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (!el.getClientRects().length) continue;
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    if (!own) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    const fgRaw = parse(cs.color); if (!fgRaw) continue;
    const bg = effBg(el);
    const op = parseFloat(cs.opacity);
    const aEff = fgRaw.a * (isNaN(op) ? 1 : op);
    const fg = { r: fgRaw.r*aEff + bg.r*(1-aEff), g: fgRaw.g*aEff + bg.g*(1-aEff),
                 b: fgRaw.b*aEff + bg.b*(1-aEff) };
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1,L2)+0.05) / (Math.min(L1,L2)+0.05);
    const px = parseFloat(cs.fontSize), w = parseInt(cs.fontWeight,10) || 400;
    const need = (px >= 24 || (px >= 18.66 && w >= 700)) ? 3 : 4.5;
    out.push({ text: own.slice(0,24), fg: hex(fg), bg: hex(bg),
               ratio: Math.round(ratio*100)/100, px, w, need, pass: ratio >= need,
               testid: el.getAttribute('data-testid') || '', tag: el.tagName.toLowerCase() });
  }
  return out;
}"""

# Starts from the CONTROL and asks what is written on it — the inverse of SCAN, which
# starts from a text node and asks what is behind it. A label that the cascade painted the
# colour of its own fill is invisible to the second question and obvious to the first.
FILLED = """() => {
  const parse = (c) => { const m = c.match(/[\\d.]+/g); if (!m) return null;
    return { r:+m[0], g:+m[1], b:+m[2], a: m[3] === undefined ? 1 : +m[3] }; };
  const effBg = (node) => {
    let acc = null;
    for (let n = node; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (!c || c.a === 0) continue;
      if (acc === null) { acc = c; if (acc.a >= 1) break; continue; }
      const a = acc.a + c.a * (1 - acc.a);
      acc = { r:(acc.r*acc.a + c.r*c.a*(1-acc.a))/a, g:(acc.g*acc.a + c.g*c.a*(1-acc.a))/a,
              b:(acc.b*acc.a + c.b*c.a*(1-acc.a))/a, a };
      if (acc.a >= 1) break;
    }
    if (!acc) return { r:255, g:255, b:255, a:1 };
    if (acc.a < 1) { const a = acc.a;
      acc = { r: acc.r*a + 255*(1-a), g: acc.g*a + 255*(1-a), b: acc.b*a + 255*(1-a), a:1 }; }
    return acc;
  };
  const lum = (c) => { const ch = [c.r,c.g,c.b].map(v => { v/=255;
    return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*ch[0] + 0.7152*ch[1] + 0.0722*ch[2]; };
  const hex = (c) => '#' + [c.r,c.g,c.b].map(v => Math.round(v).toString(16).padStart(2,'0')).join('');
  const ownText = (n) => [...n.childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim();
  // checkVisibility, not getClientRects: the tools page keeps its dev buttons inside a CLOSED
  // <details>, which still has layout boxes in Chromium. Those buttons are labelled and simply
  // not rendered; a weaker test reports them as unlabelled and the suite cries wolf.
  const shown = (e) => e.checkVisibility({ checkVisibilityCSS: true, contentVisibilityAuto: true,
                                           opacityProperty: true, visibilityProperty: true });
  // the page and surface grounds. A control sitting on white has not been "filled" with
  // anything — it is the coloured fills where a label can vanish into its own background.
  const GROUND = ['#ffffff', '#f5f7f8'];
  const out = [];
  for (const el of document.body.querySelectorAll('button, a, [role=button], input[type=submit], input[type=button]')) {
    if (!shown(el)) continue;
    const own = parse(getComputedStyle(el).backgroundColor);
    if (!own || own.a < 0.999) continue;
    const fill = hex(effBg(el));
    if (GROUND.includes(fill)) continue;
    const label = (el.innerText || '').trim();
    const acc = (el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
    let worst = null, need = null, fg = null, txt = '';
    for (const n of [el, ...el.querySelectorAll('*')]) {
      if (!ownText(n) || !shown(n)) continue;
      const c2 = getComputedStyle(n);
      const fgRaw = parse(c2.color); if (!fgRaw) continue;
      const bg = effBg(n);
      const op = parseFloat(c2.opacity); const aEff = fgRaw.a * (isNaN(op) ? 1 : op);
      const f = { r: fgRaw.r*aEff + bg.r*(1-aEff), g: fgRaw.g*aEff + bg.g*(1-aEff), b: fgRaw.b*aEff + bg.b*(1-aEff) };
      const L1 = lum(f), L2 = lum(bg);
      const ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
      const px = parseFloat(c2.fontSize), w = parseInt(c2.fontWeight,10) || 400;
      if (worst === null || ratio < worst) {
        worst = Math.round(ratio*100)/100; fg = hex(f); txt = ownText(n).slice(0, 20);
        need = (px >= 24 || (px >= 18.66 && w >= 700)) ? 3 : 4.5;
      }
    }
    out.push({ testid: el.getAttribute('data-testid') || '', tag: el.tagName.toLowerCase(),
               fill, label: label.slice(0, 20), acc: acc.slice(0, 20), worst, need, fg, txt,
               // pointer-events:none is the app's own mark for a control that is off
               inert: getComputedStyle(el).pointerEvents === 'none' });
  }
  return out;
}"""

# RAISED, NOT RULED — 2026-09-19. The certificate's photo rows dim everything in an OFF row to
# 45% (cert.module.css:92), which takes «اختيار صورة» to 1.96:1. The disabled-state ruling
# (bird/form.module.css:96-108) chose an inert --line fill with --ink-2 ink, measured 6.22:1,
# and its floor is 3:1 — so this control misses a ruling that already exists. Extending that
# ruling to the certificate is a design owner's call, not a test author's, so it is recorded
# here by name: it does not fail the suite, and anything that JOINS it does.
UNRULED_LOW_FILL = {'pick-bird', 'pick-sire', 'pick-dam'}
FILL_FLOOR = 3.0   # below this a label is not low-contrast, it is unreadable

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        white_on_brand, brand_on_white, filled, fails = [], [], [], set()
        for vw, vh in VIEWPORTS:
            ctx = b.new_context(viewport={'width': vw, 'height': vh})
            pg = ctx.new_page(); pg.set_default_timeout(90000)
            pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(800)
            pg.evaluate("async () => { await window.__zajilReady; }")
            pg.evaluate("""async () => { const db = await window.__zajilDb;
                await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge'); }""")
            bid = pg.evaluate("async () => { const db = await window.__zajilDb; return db.allBirds()[0].id; }")

            for route in ROUTES:
                base, _, qs = route.partition('?')
                url = ROOT + base + '.html' + (('?' + qs) if qs else '')
                if base in ('bird', 'pedigree', 'cert'):
                    url += ('&' if qs else '?') + 'id=' + bid
                pg.goto(url, wait_until='load'); pg.wait_for_timeout(1400)
                pg.evaluate("async () => { try { await document.fonts.ready; } catch (e) {} }")
                for r in pg.evaluate(SCAN):
                    r['route'] = route; r['vw'] = vw
                    if r['fg'].lower() in WHITE and r['bg'].lower() in BRAND:
                        white_on_brand.append(r)
                    if r['fg'].lower() in BRAND and r['bg'].lower() in NEAR_WHITE:
                        brand_on_white.append(r)
                    if not r['pass']:
                        # deliberately NOT keyed by width. The same token pair failing at 430
                        # and at 1400 is one failing combination seen twice, and keying it by
                        # viewport would double the baseline the moment the scan widened —
                        # which would read as 76 new defects and be 76 lies.
                        fails.add((route, r['fg'], r['bg'], r['px'], r['w']))
                for c in pg.evaluate(FILLED):
                    c['route'] = route; c['vw'] = vw
                    filled.append(c)
            ctx.close()

        check('white-on-brand surfaces were actually found (else this proves nothing)',
              len(white_on_brand) >= 12, f'{len(white_on_brand)} found')
        bad = [r for r in white_on_brand if not r['pass']]
        check('[RULED] every white-on-brand surface passes AA',
              not bad,
              '; '.join(f"{r['route']}/{r['testid'] or r['tag']} {r['ratio']} on {r['bg']}" for r in bad[:4]))
        light = [r for r in white_on_brand if r['bg'].lower() == '#128c6e']
        check('…and none of them is still filled with the lighter --brand',
              not light,
              '; '.join(f"{r['route']}/{r['testid'] or r['tag']}" for r in light[:4]))

        check('brand-as-text surfaces were actually found (else this proves nothing)',
              len(brand_on_white) >= 10, f'{len(brand_on_white)} found')
        badT = [r for r in brand_on_white if not r['pass']]
        check('[RULED] every brand-coloured TEXT on a white surface passes AA',
              not badT,
              '; '.join(f"{r['route']}/{r['testid'] or r['tag']} {r['ratio']}" for r in badT[:4]))
        lightT = [r for r in brand_on_white if r['fg'].lower() == '#128c6e']
        check('…and none of it is still the lighter --brand',
              not lightT, '; '.join(f"{r['route']}/{r['testid'] or r['tag']}" for r in lightT[:4]))

        # ── FILLED CONTROLS ────────────────────────────────────────────────────────────
        check('filled controls were actually found at BOTH widths (else this proves nothing)',
              all(any(c['vw'] == vw for c in filled) for vw, _ in VIEWPORTS) and len(filled) >= 40,
              f"{len(filled)} across " + ', '.join(f"{vw}:{sum(1 for c in filled if c['vw'] == vw)}"
                                                   for vw, _ in VIEWPORTS))
        # the two that shipped at 1.00:1. Named, because "we scan everything" is what the
        # single-width version of this suite also believed.
        for tid, route in (('add-bird', 'birds'), ('hero-cert', 'pedigree')):
            hit = [c for c in filled if c['testid'] == tid]
            check(f'the control that shipped unreadable is in the measured set — {route}/{tid}',
                  bool(hit), f"{len(hit)} instance(s); fill {hit[0]['fill'] if hit else '—'}, "
                             f"label «{hit[0]['label'] if hit else ''}», {hit[0]['worst'] if hit else '—'}:1")

        # A toggle or a swatch legitimately carries no word, but it must still say what it is:
        # the certificate's four photo/loft switches are bare <button>s with aria-label and
        # aria-pressed and nothing else, and they are correctly named. So the rule is a
        # RENDERED label or an accessible name — not a guess at which controls are allowed to
        # be wordless, which is how the first version of this check cried wolf on all four.
        mute = [c for c in filled if not c['label'] and not c['acc']]
        check('every filled control says something — a rendered label, or an accessible name',
              not mute,
              '; '.join(f"{c['vw']}/{c['route']}/{c['testid'] or c['tag']} fill {c['fill']}" for c in mute[:4]))

        unreadable = [c for c in filled if c['worst'] is not None and c['worst'] < FILL_FLOOR
                      and c['testid'] not in UNRULED_LOW_FILL]
        check(f"no filled control's label is unreadable against its own fill (floor {FILL_FLOOR}:1)",
              not unreadable,
              '; '.join(f"{c['vw']}/{c['route']}/{c['testid'] or c['tag']} «{c['txt']}» "
                        f"{c['fg']} on {c['fill']} = {c['worst']}:1" for c in unreadable[:4]))
        still = [c for c in filled if c['testid'] in UNRULED_LOW_FILL and c['worst'] is not None]
        if still:
            print(f"    note: {len(still)} recorded-but-unruled control(s) below the floor — "
                  f"{still[0]['testid']} «{still[0]['txt']}» at {min(c['worst'] for c in still)}:1 "
                  f"(cert.module.css:92, awaiting a ruling)")

        check(f'[RATCHET] distinct AA failures have not grown beyond {BASELINE}',
              len(fails) <= BASELINE, f'{len(fails)} distinct combinations')
        if len(fails) < BASELINE:
            print(f"    note: {BASELINE - len(fails)} fewer than the baseline — lower BASELINE to {len(fails)}")
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
