#!/usr/bin/env python3
"""Fixed full-width chrome must never sit under the desktop rail — at ANY width.

WHY THIS EXISTS. The backup banner is mounted above <main> and spans the viewport. From
1100px the rail is fixed at the inline-start edge (the RIGHT edge, in RTL) and `main` clears
it with `margin-inline: 132px 0`. Chrome that does not take the same inset runs UNDER the
rail and hides the start of its own sentence.

It was fixed once and asserted at ONE width — 1400px. A single-width assertion cannot tell a
rule that applies everywhere from a rule that happens to apply there, and the report came back
that it was still wrong at ~2700px. It was not, but nothing in the suite could have said so.
So this asserts the PROPERTY across a range: 1100 (the breakpoint itself), 1400, 1920, 2560.

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
ROOT = HARNESS.replace('test-harness.html', '')

GEO = """() => {
  const box = (e) => { if (!e) return null; const b = e.getBoundingClientRect();
    return { x: Math.round(b.x), right: Math.round(b.right), w: Math.round(b.width) }; };
  const rail = [...document.querySelectorAll('nav')].find((n) => getComputedStyle(n).position === 'fixed'
      && getComputedStyle(n).display !== 'none' && n.getBoundingClientRect().width < 200);
  return { vw: window.innerWidth,
           banner: box(document.querySelector('[data-testid=backup-warn]')),
           rail: box(rail) };
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
            await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge');
            await db.setSetting('lastExport', '2020-01-01T00:00:00.000Z'); }""")

        pg.goto(f'{ROOT}birds.html', wait_until='load'); pg.wait_for_timeout(1800)
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

        # the dual date stays on one line, in both logs, at the widest and narrowest
        for route, label in ((f'{ROOT}health.html', 'health'), (f'{ROOT}races.html?season=all', 'races')):
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
