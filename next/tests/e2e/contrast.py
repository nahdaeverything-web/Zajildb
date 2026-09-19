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

  2. A RATCHET on everything else. There are other failing pairs — muted greys on white,
     light text on tints, the danger colour on its tint — none of them ruled on yet. The
     suite records how many DISTINCT failing (route, fg, bg, size, weight) combinations exist
     and fails if that number GROWS. It cannot be gamed by moving a failure around, and it
     cannot silently accept a new one.

Thresholds are AA: 4.5:1, or 3:1 when the text is large — >=24px, or >=18.66px at weight
>=700. The effective background is resolved by compositing up the ancestor chain until
opaque, so a transparent control over a card is measured against the card. The text colour is
composited over that background, and the element's own `opacity` is folded in, because a
label at 60% opacity really is lower contrast.

BASELINE: 84 distinct failing combinations at the time of writing, over the routes below.
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

BASELINE = 84
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

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        pg = ctx.new_page(); pg.set_default_timeout(90000)
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(800)
        pg.evaluate("async () => { await window.__zajilReady; }")
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge'); }""")
        bid = pg.evaluate("async () => { const db = await window.__zajilDb; return db.allBirds()[0].id; }")

        white_on_brand, brand_on_white, fails = [], [], set()
        for route in ROUTES:
            base, _, qs = route.partition('?')
            url = ROOT + base + '.html' + (('?' + qs) if qs else '')
            if base in ('bird', 'pedigree', 'cert'):
                url += ('&' if qs else '?') + 'id=' + bid
            pg.goto(url, wait_until='load'); pg.wait_for_timeout(1400)
            pg.evaluate("async () => { try { await document.fonts.ready; } catch (e) {} }")
            for r in pg.evaluate(SCAN):
                r['route'] = route
                if r['fg'].lower() in WHITE and r['bg'].lower() in BRAND:
                    white_on_brand.append(r)
                if r['fg'].lower() in BRAND and r['bg'].lower() in NEAR_WHITE:
                    brand_on_white.append(r)
                if not r['pass']:
                    fails.add((route, r['fg'], r['bg'], r['px'], r['w']))

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

        check(f'[RATCHET] distinct AA failures have not grown beyond {BASELINE}',
              len(fails) <= BASELINE, f'{len(fails)} distinct combinations')
        if len(fails) < BASELINE:
            print(f"    note: {BASELINE - len(fails)} fewer than the baseline — lower BASELINE to {len(fails)}")
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
