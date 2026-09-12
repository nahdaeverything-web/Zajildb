#!/usr/bin/env python3
"""4A fidelity + reachability for the shared-states components (spec §01–§08).
Screenshots every section at 430 / 900 / 1400 into next/fidelity/shared-states/
and asserts each designed state is reachable and behaves as the spec says.
Provisions its own server (R6). Binds to data-testid only, never to styling classes."""
import os, sys, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'fidelity', 'shared-states')); os.makedirs(OUT, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")
srv, BASE = serve(); GAL = BASE.replace('test-harness.html', 'test-harness/gallery.html')
SECTIONS = ['g-sync', 'g-toast', 'g-dialogs', 'g-validation', 'g-notice', 'g-empty', 'g-loading', 'g-media', 'g-bits']
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (430, 900, 1400):
            pg = b.new_page(viewport={'width': w, 'height': 900}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(GAL, wait_until='load'); pg.wait_for_timeout(800)
            check(f'{w}: gallery renders, dir=rtl', pg.evaluate("document.documentElement.dir") == 'rtl')
            for sec in SECTIONS:
                el = pg.locator(f'[data-testid={sec}]'); el.scroll_into_view_if_needed(); pg.wait_for_timeout(120)
                el.screenshot(path=f'{OUT}/{sec[2:]}-{w}.png')
            pg.screenshot(path=f'{OUT}/full-{w}.png', full_page=True)
            check(f'{w}: zero page errors', not errs, errs)
            if w >= 1100:
                pg.click('[data-testid=fire-toast-success]'); pg.wait_for_timeout(120)
                fb = pg.evaluate("() => innerHeight - document.querySelector('[data-testid=toast]').getBoundingClientRect().bottom")
                check(f'{w}: no tab bar (rail) → toast 12 px from the bottom edge', 11 <= fb <= 13, f'{fb:.0f}px')
            pg.close()

        # ── behaviour, once, at 430 ──
        pg = b.new_page(viewport={'width': 430, 'height': 900}); pg.goto(GAL, wait_until='load'); pg.wait_for_timeout(600)

        # §01 sync: five visible states + synced renders nothing
        for st in ('offline', 'syncing', 'pending', 'error', 'off'):
            check(f'sync.{st} visible with role=status', pg.locator(f'[data-testid=sync-{st}][role=status]').is_visible())
        check('sync.synced renders nothing', pg.locator('[data-testid=sync-synced]').evaluate("e => e.childElementCount === 0 && e.textContent.trim() === ''"))
        check('sync.pending count in .n', pg.locator('[data-testid=sync-pending] span span').inner_text() == '3')
        a = pg.locator('[data-testid=sync-error] a')
        check('sync.error links to /tools labelled nav.tools', a.get_attribute('href') == '/tools' and a.inner_text() == 'الأدوات')

        # §02 toasts: kinds, timings (spec: 4 s / error 6 s / undo 6 s), undo action fires
        pg.click('[data-testid=fire-toast-success]'); t0 = time.time()
        check('success toast appears with kind', pg.locator('[data-testid=toast][data-kind=success]').is_visible())
        pg.wait_for_selector('[data-testid=toast][data-kind=success]', state='detached', timeout=6000); dt = time.time() - t0
        check('success toast expires ≈4 s', 3.5 <= dt <= 5.0, f'{dt:.1f}s')
        pg.click('[data-testid=fire-toast-error]'); t0 = time.time()
        pg.wait_for_selector('[data-testid=toast][data-kind=error]', state='detached', timeout=8000); dt = time.time() - t0
        check('error toast expires ≈6 s', 5.5 <= dt <= 7.0, f'{dt:.1f}s')
        pg.click('[data-testid=fire-toast-undo]')
        check('undo toast carries the action «تراجع»', pg.locator('[data-testid=toast-action]').inner_text() == 'تراجع')
        g = pg.evaluate("() => { const nav=[...document.querySelectorAll('nav')].find(n=>getComputedStyle(n).display!=='none'&&/tabbar/.test(n.className)); const t=document.querySelector('[data-testid=toast]').getBoundingClientRect(); return { gap: nav ? nav.getBoundingClientRect().top - t.bottom : null, fromBottom: innerHeight - t.bottom, w: t.width }; }")
        check('toast sits 12 px above the tab bar (spec §02)', g['gap'] is not None and 11 <= g['gap'] <= 13, f"gap={g['gap']}")
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(150)
        check('undo action fires and the undo toast is dismissed', pg.locator('[data-testid=toast][data-kind=success]').count() == 1 and pg.locator('[data-testid=toast-action]').count() == 0)
        pg.wait_for_timeout(4500)

        # [ruling 6, 4C acceptance] at most two toasts are visible; a third drops the oldest.
        # §02 draws a stack and vanilla appends without a cap, but the clearance proved under
        # ruling C holds at two — a third reaches into the last row of a short list.
        pg.click('[data-testid=fire-toast-success]'); pg.wait_for_timeout(80)
        pg.click('[data-testid=fire-toast-error]'); pg.wait_for_timeout(80)
        check('[ruling 6] two toasts stack, as the spec draws them', pg.locator('[data-testid=toast]').count() == 2)
        pg.click('[data-testid=fire-toast-info]'); pg.wait_for_timeout(120)
        kinds = pg.locator('[data-testid=toast]').evaluate_all("els => els.map(e => e.dataset.kind)")
        check('[ruling 6] a third replaces the OLDEST — never three at once', len(kinds) == 2 and kinds == ['error', 'info'], kinds)
        band = pg.evaluate("""() => { const ts = [...document.querySelectorAll('[data-testid=toast]')];
            const top = Math.min(...ts.map(t => t.getBoundingClientRect().top));
            const nav = [...document.querySelectorAll('nav')].find(n => getComputedStyle(n).display !== 'none' && /tabbar/.test(n.className));
            return { height: Math.round(Math.max(...ts.map(t => t.getBoundingClientRect().bottom)) - top), gap: nav ? Math.round(nav.getBoundingClientRect().top - Math.max(...ts.map(t => t.getBoundingClientRect().bottom))) : null }; }""")
        # the bound is not a guess: every screen reserves at least the spec's panel padding (170px) plus the
        # layout's own (84px) under its last element, so a capped stack must be shorter than that to stay clear.
        check('[ruling 6] …the capped stack is shorter than the clearance every screen reserves (254px), and still seats at 12px',
              band['height'] < 254 and 11 <= band['gap'] <= 13, band)
        pg.wait_for_timeout(6500)

        # §03 dialogs: resolve on cancel / confirm / Escape; focus trapped
        pg.click('[data-testid=open-dlg-simple]')
        check('simple dialog opens (role=dialog, aria-modal)', pg.locator('[data-testid=dialog][role=dialog][aria-modal=true]').is_visible())
        pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(100)
        check('cancel closes it', pg.locator('[data-testid=dialog]').count() == 0)
        pg.click('[data-testid=open-dlg-bird]'); txt = pg.locator('[data-testid=dialog]').inner_text()
        check('delete-bird dialog names the bird and the relation count', 'برق' in txt and '7' in txt)
        pg.keyboard.press('Escape'); pg.wait_for_timeout(100)
        check('Escape closes as cancel', pg.locator('[data-testid=dialog]').count() == 0)
        pg.click('[data-testid=open-dlg-signout]')
        check('sign-out confirm is ink, not danger', pg.locator('[data-testid=dialog-confirm]').evaluate("e => !/danger/.test(e.className)"))
        for _ in range(6): pg.keyboard.press('Tab')
        check('Tab stays inside the dialog', pg.evaluate("document.activeElement.closest('[data-testid=dialog]') !== null"))
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(100)
        check('confirm closes it', pg.locator('[data-testid=dialog]').count() == 0)
        pg.click('[data-testid=open-dlg-errs]')
        check('error-list dialog: one button, 3 items', pg.locator('[data-testid=dialog-confirm]').count() == 0 and pg.locator('[data-testid=dialog-errs] li').count() == 3)
        pg.click('[data-testid=dialog-cancel]')
        pg.click('[data-testid=open-dlg-warns]')
        # ruling 14 (4A acceptance): vanilla act.saveAnyway «حفظ رغم التحذير» wins over the spec's «حفظ رغم ذلك» (same meaning)
        check('warnings dialog: 2 items, «حفظ رغم التحذير»', pg.locator('[data-testid=dialog-warns] li').count() == 2 and pg.locator('[data-testid=dialog-confirm]').inner_text() == 'حفظ رغم التحذير')
        pg.click('[data-testid=dialog-confirm]')

        # §04 validation · §05 notice · §06 empty · §07 loading · §08 media · bits
        check('field error message rendered (role=alert)', pg.locator('[data-testid=field-err] [data-testid=field-error][role=alert]').is_visible())
        check('field warning (non-blocking) rendered', pg.locator('[data-testid=field-warn] [data-testid=field-warn]').is_visible())
        n0 = pg.locator('[data-testid=notice-default]').count(); pg.click('[data-testid=notice-default] [data-testid=notice-dismiss]'); pg.wait_for_timeout(100)
        check('notice dismisses on ✕ and does not return', n0 == 1 and pg.locator('[data-testid=notice-default]').count() == 0)
        check('first-run empty: h2 + body + one primary', pg.locator('[data-testid=empty-first] h2').inner_text() == 'لا طيور بعد' and pg.locator('[data-testid=empty-cta]').count() == 1)
        check('quiet empty: outline action «مسح الفلاتر»', pg.locator('[data-testid=empty-alt]').inner_text() == 'مسح الفلاتر')
        check('page loading: spinner + «جارٍ التحميل…»', pg.locator('[data-testid=loading]').inner_text().strip() == 'جارٍ التحميل…')
        pg.click('[data-testid=btn-working]'); pg.wait_for_timeout(100)
        check('working button: disabled, label → «جارٍ الحفظ…», sibling disabled',
              pg.locator('[data-testid=btn-working]').is_disabled() and 'جارٍ الحفظ' in pg.locator('[data-testid=btn-working]').inner_text() and pg.locator('[data-testid=g-loading] button').first.is_disabled())
        check('media tiles say «الصورة على جهاز آخر» ×2 + file variant', pg.locator('[data-testid=media-elsewhere]').count() == 3 and pg.locator('[data-testid=media-elsewhere]').first.inner_text().strip().endswith('الصورة على جهاز آخر'))
        check('media hero carries filename + meta', 'IMG_4471' in pg.locator('[data-testid=media-elsewhere-hero]').inner_text())
        check('COI band exposed as data (25% → severe)', pg.locator('[data-testid=coi-badge]').first.get_attribute('data-band') == 'severe')
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
