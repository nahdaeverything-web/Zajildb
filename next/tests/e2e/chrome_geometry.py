#!/usr/bin/env python3
"""Fixed full-width chrome must never sit under the desktop rail — at ANY width.

WHY THIS EXISTS. The backup banner is mounted above <main> and spans the viewport. From
1100px the rail is fixed at the inline-start edge (the RIGHT edge, in RTL) and `main` clears
it with `margin-inline: var(--rail-w) 0`. Chrome that does not take the same inset runs
UNDER the rail and hides the start of its own sentence.

It was fixed once and asserted at ONE width — 1400px. A single-width assertion cannot tell a
rule that applies everywhere from a rule that happens to apply there, and the report came back
that it was still wrong at ~2700px. It was not, but nothing in the suite could have said so.
So this asserts the PROPERTY across a range: 1100 (the breakpoint itself), 1400, 1920, 2560.

ALSO ASSERTED HERE: THE RAIL IS SIZED BY ITS CONTENT. The rail used to declare
`width:132px` — the width of six particular Arabic words, drawn once, in loft-home-v1.
«الإحصائيات» needs a 121px item box; 132px gives it 107px; so the longest label overflowed
its own item and collided with its icon at every desktop width, in every state. Shortening
the word was refused, and rightly: the word is not the defect, the fixed size is.

So the assertion below is about the RULE, not about the six words. Every item is measured in
rest AND under hover, at all four widths — and then a SEVENTH, synthetic label, longer than
any real one, is written into the rail and everything is measured again. If the sizing rule
ever goes back to a constant, the synthetic case is what fails: the real labels might still
happen to fit inside whatever number was chosen, and that is exactly how this defect shipped.
The four pieces of chrome that clear the rail are checked against the rail's MEASURED width
rather than against 132, for the same reason.

Also asserted here: the dual Gregorian+Hijri date in the health and race logs stays on ONE
line. «21 حزيران 2026 (6 محرم 1448 هـ)» is ~236px and wrapped to three lines in a 139px
column, breaking mid-parenthesis.

Binds to data-testid only. Provisions its own server (R6)."""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve

WIDTHS = [1100, 1400, 1920, 2560]
passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

GEO = """() => {
  const box = (e) => { if (!e) return null; const b = e.getBoundingClientRect();
    return { x: Math.round(b.x), right: Math.round(b.right), w: Math.round(b.width) }; };
  // by testid, NOT by "a fixed nav narrower than 200px". The rail is content-sized now, so
  // its width is not known in advance — a finder with a number in it would stop finding the
  // rail the moment a label grew, and every assertion below would quietly pass on nothing.
  const railEl = document.querySelector('[data-testid=rail]');
  const rail = (railEl && getComputedStyle(railEl).display !== 'none') ? railEl : null;
  return { vw: window.innerWidth,
           banner: box(document.querySelector('[data-testid=backup-warn]')),
           rail: box(rail) };
}"""

# One item's geometry, reduced to the only three questions that matter: does the label
# collide with its own icon, does the item's content fit the box it was given, and does the
# label stay inside the rail. The label is measured with a Range over the anchor's own text
# node — an element box would report the anchor's box, which is the thing under suspicion.
RAIL_ITEMS = """() => {
  const rail = document.querySelector('[data-testid=rail]');
  if (!rail || getComputedStyle(rail).display === 'none') return null;
  const rb = rail.getBoundingClientRect();
  const items = [...rail.querySelectorAll('a')].map((a) => {
    const ib = a.querySelector('svg').getBoundingClientRect();
    let lb = null, label = '';
    for (const n of a.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      label = n.textContent.trim();
      const r = document.createRange(); r.selectNodeContents(n); lb = r.getBoundingClientRect(); break;
    }
    return {
      tab: a.getAttribute('data-tab'), label,
      hovered: getComputedStyle(a).backgroundColor,
      box: Math.round(a.getBoundingClientRect().width),
      icon: [Math.round(ib.left), Math.round(ib.right)],
      text: lb ? [Math.round(lb.left), Math.round(lb.right)] : null,
      // the three failures, named
      overlap: lb ? !(lb.right <= ib.left + 0.5 || lb.left >= ib.right - 0.5) : true,
      clipped: a.scrollWidth > a.clientWidth + 1,
      escapes: lb ? (lb.left < rb.left - 0.5 || lb.right > rb.right + 0.5) : true,
    };
  });
  return { railW: Math.round(rb.width),
           railVar: getComputedStyle(document.documentElement).getPropertyValue('--rail-w').trim(),
           mainInset: getComputedStyle(document.querySelector('main')).marginRight,
           items };
}"""

# longer than every real label, and real Arabic so it shapes and measures like one
SYNTHETIC = 'الإحصائيات التفصيلية للسباقات الموسمية'
SET_LABEL = """([tab, text]) => {
  const a = document.querySelector(`[data-testid=rail] a[data-tab="${tab}"]`);
  for (const n of a.childNodes) if (n.nodeType === 3 && n.textContent.trim()) { n.textContent = text; return true; }
  return false;
}"""

DATE_LINES = """() => {
  const td = [...document.querySelectorAll('table tbody td')].find((c) => /\\d{4}/.test(c.textContent));
  if (!td) return null;
  const el = td.querySelector('bdi') || td;
  const cs = getComputedStyle(el); const b = el.getBoundingClientRect();
  return { text: el.textContent.trim(), w: Math.round(b.width),
           lines: Math.round(b.height / parseFloat(cs.lineHeight)) };
}"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(800)
        pg.evaluate("async () => { await window.__zajilReady; }")
        # a non-empty loft AND a stale export, so the banner is on screen at all
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            await db.importAll(await (await fetch(new URL('example-loft-large.json', document.querySelector('link[rel=manifest]').href))).json(), 'merge');
            await db.setSetting('lastExport', '2020-01-01T00:00:00.000Z'); }""")

        pg.goto(f'{ROOT}birds/', wait_until='load'); pg.wait_for_timeout(1800)
        seen_rail = 0
        for w in WIDTHS:
            pg.set_viewport_size({'width': w, 'height': 1000}); pg.wait_for_timeout(500)
            g = pg.evaluate(GEO)
            bn, rl = g['banner'], g['rail']
            if not bn:
                check(f'@{w}: the banner is on screen at all (else this proves nothing)', False, str(g))
                continue
            if not rl:
                check(f'@{w}: the rail is present', False, 'no fixed rail found')
                continue
            seen_rail += 1
            overlap = bn['right'] > rl['x'] and bn['x'] < rl['right']
            check(f'@{w}: the banner does not run under the rail',
                  not overlap, f"banner {bn['x']}..{bn['right']}  rail {rl['x']}..{rl['right']}")
        check('the rail was actually present at every width tested',
              seen_rail == len(WIDTHS), f'{seen_rail} of {len(WIDTHS)}')

        # ── THE RAIL IS SIZED BY ITS CONTENT, NOT BY A NUMBER ──────────────────────────
        def sweep(tag):
            """Every item, at every width, at rest and under hover. Returns the rail widths
            seen, so the synthetic case can be compared against the real one."""
            widths, faults, measured = {}, [], 0
            for w in WIDTHS:
                pg.set_viewport_size({'width': w, 'height': 1000}); pg.wait_for_timeout(450)
                states = [('rest', None)] + [('hover', t['tab']) for t in pg.evaluate(RAIL_ITEMS)['items']]
                for state, tab in states:
                    if tab: pg.hover(f'[data-testid=rail] a[data-tab="{tab}"]')
                    else: pg.mouse.move(int(w / 2), 500)
                    pg.wait_for_timeout(120)
                    g = pg.evaluate(RAIL_ITEMS)
                    if g is None:
                        faults.append(f'@{w} {state}: no rail'); continue
                    widths[w] = g['railW']
                    for it in g['items']:
                        measured += 1
                        if tab and it['tab'] == tab and it['hovered'] in ('rgba(0, 0, 0, 0)', 'transparent'):
                            faults.append(f"@{w}: hovering {it['tab']} did not apply the hover style "
                                          f"(bg {it['hovered']}) — the hover half of this sweep proves nothing")
                        for kind in ('overlap', 'clipped', 'escapes'):
                            if it[kind]:
                                faults.append(f"@{w} {state}{'/' + tab if tab else ''}: «{it['label'][:18]}» {kind.upper()} "
                                              f"— box {it['box']}px, icon {it['icon']}, text {it['text']}")
                    if g['railVar'] != f"{g['railW']}px":
                        faults.append(f"@{w} {state}: --rail-w is {g['railVar']} but the rail measures {g['railW']}px")
                    if g['mainInset'] != f"{g['railW']}px":
                        faults.append(f"@{w} {state}: main clears {g['mainInset']} but the rail measures {g['railW']}px")
            check(f'[{tag}] every rail item was actually measured (else this proves nothing)',
                  measured == len(WIDTHS) * 7 * 6, f'{measured} measurements, expected {len(WIDTHS) * 7 * 6}')
            check(f'[{tag}] no label overlaps its icon, overflows its item, or escapes the rail '
                  f'— any item, rest or hover, at {"/".join(str(x) for x in WIDTHS)}',
                  not faults, f'{len(faults)} fault(s): ' + ' | '.join(faults[:4]))
            return widths

        real = sweep('real labels')

        # THE ONE THAT CATCHES A REVERT. Six short words fit inside almost any number someone
        # might hard-code, so the real labels alone cannot tell a content-driven rule from a
        # lucky constant. A label longer than any real one can: under a fixed width it
        # overflows, under `max-content` the rail grows.
        pg.set_viewport_size({'width': 1400, 'height': 1000}); pg.wait_for_timeout(300)
        check('the synthetic label was actually written into the rail (else this proves nothing)',
              pg.evaluate(SET_LABEL, ['/stats', SYNTHETIC]) is True)
        synth = sweep('synthetic label')
        check('the rail GREW to fit a label longer than any real one — it is not a fixed width',
              all(synth[w] > real[w] + 40 for w in WIDTHS),
              '  '.join(f'@{w}: {real[w]}→{synth[w]}px' for w in WIDTHS))
        check('…and it is the same width at every viewport — driven by its content, not the window',
              len(set(real.values())) == 1 and len(set(synth.values())) == 1,
              f'real {sorted(set(real.values()))}  synthetic {sorted(set(synth.values()))}')

        pg.reload(wait_until='load'); pg.wait_for_timeout(1200)   # drop the synthetic label

        # the dual date stays on one line, in both logs, at the widest and narrowest
        for route, label in ((f'{ROOT}health/', 'health'), (f'{ROOT}races/?season=all', 'races')):
            for w in (1100, 2560):
                pg.set_viewport_size({'width': w, 'height': 1000})
                pg.goto(route, wait_until='load'); pg.wait_for_timeout(1600)
                d = pg.evaluate(DATE_LINES)
                check(f'@{w}: the {label} log keeps a Gregorian+Hijri date on ONE line',
                      d is not None and d['lines'] == 1,
                      f"{d['lines']} line(s), {d['w']}px «{d['text'][:30]}»" if d else 'no date cell found')
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
