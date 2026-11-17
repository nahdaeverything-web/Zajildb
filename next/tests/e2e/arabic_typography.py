#!/usr/bin/env python3
"""Arabic must be drawn by a face that HAS Arabic, and must never be letter-spaced.

WHY THIS EXISTS. IBM Plex Mono carries no Arabic glyphs. Wherever a mono style reached a
string that can contain Arabic — dates, «لم يتم التصدير بعد», «شعار محفوظ على هذا الجهاز»,
the race table's «المسافة كم», the version line — every Arabic character fell back on its own
and the script came apart. It looks exactly like letter-spacing, which is how it was first
reported; it is not. Measured at the time: 41 Arabic-bearing elements across nine routes.

The rule this enforces: MONO IS FOR LTR DATA ONLY — ring numbers, coordinates, speeds,
versions. Any string that can contain Arabic renders in the Arabic face. And Arabic is
connected script, so it is never tracked: no letter-spacing, positive or negative.

HOW COVERAGE IS DETECTED, since the obvious ways do not work:

  · `document.fonts.check(font, text)` is useless here — measured, it returns True for
    plexMono + Arabic, and True for a font that does not exist at all. It reports that SOME
    face can render the text, not that the named one can.
  · Comparing rendered width against a reference face is noisy — a weight difference alone
    moved «زاجل» by 2px and produced false alarms.

What works is the fallback-divergence trick. A face that LACKS a glyph falls through to
whatever generic sits behind it in the stack. So the same string is measured three times,
behind three different generics:

    20px <face>, monospace   |   20px <face>, serif   |   20px <face>, sans-serif

If the face covers the text, it draws all three and the widths are identical. If it does not,
three different generics draw it and the widths diverge. Verified both ways before this suite
was written:

    plexMono   + Arabic  -> 48.2, 34, 34   (diverge)  -> NO coverage
    plexMono   + latin   -> 48, 48, 48     (agree)    -> coverage
    alexandria + Arabic  -> 39, 39, 39     (agree)    -> coverage
    NoSuchFont + Arabic  -> 48.2, 34, 34   (diverge)  -> NO coverage

Elements with no client rects are skipped: <title> lives in <head>, has no font of its own,
and reported as Times New Roman on every route.

Binds to data-testid only where it needs an element. Provisions its own server (R6)."""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve
sys.path.insert(0, HERE)

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

from _typography import SCAN   # shared with screens/sync_auto.py (2026-11-13)


ROUTES = ['birds', 'bird', 'breeding', 'races', 'races?tab=fci', 'health', 'stats', 'tools',
          'pedigree', 'cert', 'sign-in']

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 1000})
        pg = ctx.new_page()
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(800)
        pg.evaluate("async () => { await window.__zajilReady; }")
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            await db.importAll(await (await fetch(new URL('example-loft-large.json', document.querySelector('link[rel=manifest]').href))).json(), 'merge'); }""")

        # the detector must be able to FAIL, or a green run proves nothing
        sanity = pg.evaluate("""() => {
            const cv = document.createElement('canvas').getContext('2d');
            const covers = (family, text) => {
              const w = ['monospace','serif','sans-serif'].map(g => { cv.font = `20px ${family}, ${g}`;
                return cv.measureText(text).width; });
              return Math.abs(w[0]-w[1]) < 0.01 && Math.abs(w[1]-w[2]) < 0.01;
            };
            return { monoArabic: covers('plexMono', 'أبجد'), monoLatin: covers('plexMono', 'abcd'),
                     arabicFace: covers('alexandria', 'أبجد'), bogus: covers('NoSuchFontXYZ', 'أبجد') };
        }""")
        check('the detector reports NO coverage for the mono face on Arabic',
              sanity['monoArabic'] is False, str(sanity))
        check('…and coverage for the mono face on latin, and for the Arabic face on Arabic',
              sanity['monoLatin'] is True and sanity['arabicFace'] is True, str(sanity))
        check('…and NO coverage for a font that does not exist, so it is not just saying yes',
              sanity['bogus'] is False, str(sanity))

        total = 0
        for route in ROUTES:
            base, _, qs = route.partition('?')
            url = ROOT + base + '/' + (('?' + qs) if qs else '')
            if base in ('bird', 'pedigree', 'cert'):
                bid = pg.evaluate("async () => { const db = await window.__zajilDb; return db.allBirds()[0].id; }")
                url += ('&' if qs else '?') + 'id=' + bid
            pg.goto(url, wait_until='load'); pg.wait_for_timeout(1500)
            pg.evaluate("async () => { try { await document.fonts.ready; } catch (e) {} }")
            hits = pg.evaluate(SCAN)
            total += len(hits)
            detail = '; '.join(f"{h['why'].strip()} face={h['face']} «{h['text'][:26]}»" for h in hits[:3])
            check(f'/{route}: no Arabic in a face that cannot draw it, and none letter-spaced',
                  not hits, detail)
        check('across every route, zero', total == 0, f'{total} element(s)')

        # THE VERSION ROW WITH NO VERSION (RULED 2026-11-17). With no service worker to answer, the row says «غير معروف»
        # — and it said it in the mono face, which cannot draw Arabic (seen 2026-11-16 by the example-removal suite; the
        # walk above passes الأدوات only when a worker answers in time). The walk now visits that state by name.
        ctx2 = b.new_context(viewport={'width': 390, 'height': 844}); p2 = ctx2.new_page()
        p2.add_init_script("Object.defineProperty(navigator, 'serviceWorker', { get: () => undefined });")
        p2.goto(ROOT + 'tools/', wait_until='load'); p2.wait_for_selector('[data-testid=about-version]'); p2.wait_for_timeout(1500)
        p2.evaluate("async () => { try { await document.fonts.ready; } catch (e) {} }")
        shown = p2.locator('[data-testid=about-version]').inner_text().strip(); hits = p2.evaluate(SCAN)
        check('/tools with no service worker: the version row says «غير معروف»', shown == 'غير معروف', shown)
        check('[M-mono fails here] …and no Arabic on that screen is in a face that cannot draw it',
              not hits, '; '.join(f"{h['why'].strip()} face={h['face']} «{h['text'][:26]}»" for h in hits[:3]))
        # …and the sign-in screen's footer, which had the same fault in its own markup (measured 2026-11-17 at phone width)
        p3 = ctx2.new_page(); p3.add_init_script("Object.defineProperty(navigator, 'serviceWorker', { get: () => undefined });")
        p3.goto(ROOT + 'sign-in/', wait_until='load'); p3.wait_for_selector('[data-testid=version]'); p3.wait_for_timeout(1500)
        p3.evaluate("async () => { try { await document.fonts.ready; } catch (e) {} }")
        foot = p3.locator('[data-testid=version]').inner_text().strip(); hits = p3.evaluate(SCAN)
        check('/sign-in with no service worker: the footer says «الإصدار غير معروف»', 'غير معروف' in foot, foot)
        check('[M-mono-signin fails here] …and no Arabic on that screen is in a face that cannot draw it',
              not hits, '; '.join(f"{h['why'].strip()} face={h['face']} «{h['text'][:26]}»" for h in hits[:3]))
        ctx2.close()
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
