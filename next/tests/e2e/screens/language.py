#!/usr/bin/env python3
"""The app language, on EVERY surface at once — the nav, the banner and the page together.

FOUND LIVE 2026-10-04, in a real session with Arabic selected: the desktop rail read
Birds / Breeding / Races / Health / Statistics / Tools and the backup banner read «More than
30 days since your last export.» — its full stop on the wrong side — while the page around
them was Arabic.

THE MECHANISM, measured on the live origin before anything was changed:

    t() reads ONE module variable (src/i18n.js `lang`), set by configure(). Nothing about that
    variable is React state, so a component shows a new language only when something ELSE
    makes it render again:
      · a SCREEN re-renders on every data-layer change (useZajilStore), and saving a setting
        raises one — so the page body followed the switch at once;
      · the NAV re-rendered only when the route changed (usePathname);
      · the BANNER re-rendered only when it appeared or disappeared (its own boolean).
    So each kept whatever language was in force the last time it happened to render. Tap
    English, move about, tap العربية: Arabic page, English rail, English banner — until the
    next navigation (the rail) or the next reload (the banner).

Not a missing key (both strings have Arabic, and render it on a cold load), not a first-paint
race (a cold load with Arabic stored is correct), not a hardcoded string.

WHAT THIS ASSERTS. The detector (_language.py, shared with the deploy gate) is DERIVED FROM
THE DICTIONARY, not typed: a visible string
"renders in English" when it is the `en` value of a key whose `ar` value differs (or an
instance of its template, or contains a multi-word phrase of one). So it cannot go stale as
strings are added, and it needs no list of surfaces — whatever is on screen is examined, at
430px (the tab bar) AND 1400px (the rail only exists at >=1100px), on:
  · the reported path — through English and back, WITHOUT a reload, then tab by tab, which
    is where chrome that outlives a navigation shows what it remembered;
  · a cold load of every route the export wrote, derived from out/ rather than listed.
And the same cause the other way round: with English applied, no Arabic UI string remains.

Binds to data-testid only. Provisions its own server (R6)."""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
sys.path.insert(0, HERE)
from _serve import serve, OUT                 # noqa: E402
from _layout import wait_toasts_clear         # noqa: E402
from _language import (DICT, LEX, STATS, NAV, BANNER, TABS, leaks, say, strings_of,   # noqa: E402
                       open_row, set_lang, tab, nav_labels)

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


def run(pg, fn, arg=None):
    return pg.evaluate("async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }" % fn, arg)


# ── the routes: every page the export wrote, never a typed list ─────────────────────
def _route(d):
    rel = os.path.relpath(d, OUT).replace(os.sep, '/')
    return '' if rel == '.' else rel


ROUTES = sorted(_route(d) for d, _, files in os.walk(OUT) if 'index.html' in files)
ROUTES = [r for r in ROUTES if not r.startswith(('test-harness', '404', '_not-found', '_next'))]
NEEDS_ID = {'bird': 'bird', 'bird/edit': 'bird', 'pedigree': 'bird', 'cert': 'bird', 'pair': 'pair'}

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

try:
    check('the dictionary parsed is the app\'s own — both files, both languages',
          len(DICT) >= 600 and DICT['nav.birds'] == {'ar': 'الطيور', 'en': 'Birds'},
          f"{len(DICT)} keys · {len(LEX['en'][0])} English values, {len(LEX['en'][1])} templates, {len(LEX['en'][2])} phrases")
    check('the routes are derived from the export, and every screen is among them',
          len(ROUTES) >= 13 and {'birds', 'tools', 'cert', 'sign-in', 'bird/new'} <= set(ROUTES), ' '.join(r or '(root)' for r in ROUTES))

    with sync_playwright() as p:
        b = p.chromium.launch()
        for vw in (430, 1400):
            which = 'rail' if vw >= 1100 else 'tabbar'
            T = f'@{vw}'
            ctx = b.new_context(viewport={'width': vw, 'height': 900})
            pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(f'{ROOT}tools/', wait_until='load'); pg.wait_for_selector('[data-testid=set-lang], [data-row=lang]', timeout=10000)
            open_row(pg, 'teaching')
            pg.click('[data-testid=load-large]'); pg.wait_for_timeout(3000); wait_toasts_clear(pg)
            ids = run(pg, "(db) => ({ bird: (db.allBirds().find(b => b.sireId && b.damId) || db.allBirds()[0]).id, pair: [...db.state.pairs.values()][0].id })")
            data = strings_of(run(pg, "async (db) => await db.exportAll({ includeMedia: false })"), set())
            url = lambda r: f"{ROOT}{r + '/' if r else ''}" + (f"?id={ids[NEEDS_ID[r]]}" if r in NEEDS_ID else '')   # noqa: E731

            # ── the surfaces the report names are really on screen (else this proves nothing) ──
            check(f'{T} the {which} is the nav on screen, with its six labels, and the backup banner is up',
                  pg.locator(f'[data-testid={which}]').is_visible() and len(nav_labels(pg, which)) == 6
                  and pg.locator('[data-testid=backup-warn]').is_visible(),
                  f"{nav_labels(pg, which)}")
            base = leaks(pg, 'ar', data)
            check(f'{T} Arabic from a cold start: no English UI string on screen', not base, say(base))

            # ── English, tapped: the same cause, seen from the other side ──
            set_lang(pg, 'en')
            blind = leaks(pg, 'ar', data)
            check(f'{T} [control] the detector is not blind — with English applied it finds English all over the page',
                  len(blind) >= 15, f'{len(blind)} English strings')
            got = leaks(pg, 'en', data)
            check(f'{T} «English» tapped: the nav and the banner answer AT ONCE, with the page',
                  nav_labels(pg, which) == NAV['en'] and pg.locator('[data-testid=backup-warn] span').inner_text().strip() == BANNER['en'],
                  f"{nav_labels(pg, which)} / «{pg.locator('[data-testid=backup-warn] span').inner_text().strip()[:40]}»")
            check(f'{T} …and no Arabic UI string is left anywhere on screen', not got, say(got))

            # ── English stored, then a reload: the BOOT path applies a language nothing announced ──
            pg.reload(wait_until='load'); pg.wait_for_timeout(2200)
            got = leaks(pg, 'en', data)
            check(f'{T} reloaded with English stored: the nav comes back in English, not in the prerendered Arabic',
                  nav_labels(pg, which) == NAV['en'], str(nav_labels(pg, which)))
            check(f'{T} …and no Arabic UI string is left on screen', not got, say(got))
            tab(pg, '/birds'); tab(pg, '/tools')

            # ── THE REPORTED STATE: back to Arabic, without a reload ──
            set_lang(pg, 'ar')
            doc = pg.evaluate("() => document.documentElement.lang + '/' + document.documentElement.dir")
            got = leaks(pg, 'ar', data)
            check(f'{T} [THE BUG] «العربية» tapped after English: the {which} reads Arabic',
                  nav_labels(pg, which) == NAV['ar'], str(nav_labels(pg, which)))
            check(f'{T} [THE BUG] …and so does the backup banner, its full stop where an Arabic sentence ends',
                  pg.locator('[data-testid=backup-warn] span').inner_text().strip() == BANNER['ar']
                  and pg.locator('[data-testid=backup-warn-act]').inner_text().strip() == DICT['act.export']['ar'] and doc == 'ar/rtl',
                  f"«{pg.locator('[data-testid=backup-warn] span').inner_text().strip()[:48]}» [{pg.locator('[data-testid=backup-warn-act]').inner_text().strip()}] {doc}")
            check(f'{T} [THE BUG] …NO visible UI string renders in English while the app language is Arabic', not got, say(got))

            # ── tab by tab, client-side: the chrome persists across these, so it shows what it kept ──
            stale = []
            for href in TABS:
                tab(pg, href)
                stale += [(f'{href} · {w}', s, k) for w, s, k in leaks(pg, 'ar', data)]
            check(f'{T} …nor on any of the six tabs reached by client-side navigation afterwards', not stale, say(stale))

            # ── cold, every route the export wrote ──
            cold = []
            for r in ROUTES:
                pg.goto(url(r), wait_until='load'); pg.wait_for_timeout(1500)
                cold += [(f'{r or "(root)"} · {w}', s, k) for w, s, k in leaks(pg, 'ar', data)]
            check(f'{T} cold, Arabic stored: none of the {len(ROUTES)} exported routes renders an English UI string', not cold, say(cold))

            # ── and the other way round, cold: English stored, every route ──
            pg.goto(f'{ROOT}tools/', wait_until='load'); pg.wait_for_selector('[data-testid=set-lang], [data-row=lang]', timeout=10000)
            set_lang(pg, 'en')
            cold = []
            for r in ROUTES:
                pg.goto(url(r), wait_until='load'); pg.wait_for_timeout(1500)
                cold += [(f'{r or "(root)"} · {w}', s, k) for w, s, k in leaks(pg, 'en', data)]
            check(f'{T} cold, English stored: none of the {len(ROUTES)} exported routes renders an Arabic UI string', not cold, say(cold, 8))
            check(f'{T} zero page errors', not errs, '; '.join(errs[:2]))
            ctx.close()
        b.close()
    check('the scan was not vacuous', STATS['scanned'] >= 4000, f"{STATS['scanned']} visible strings examined")
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
