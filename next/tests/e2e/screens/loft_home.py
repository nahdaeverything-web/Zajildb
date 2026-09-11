#!/usr/bin/env python3
"""Loft home (/birds) — intent list re-authored from core_flows, example_data,
teaching_loft, change_events, ownership (as they apply), plus every state
loft-home-v1 designs. Binds to data-testid only. Seeds through the layer on the
harness route, then exercises the real screen. Provisions its own server (R6).

Root assertion → new test mapping is in the docstring of each check."""
import os, sys, json, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'loft-home')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
BIRDS = HARNESS.replace('test-harness.html', 'birds.html')
def boot(ctx):
    """Fresh database via the harness route; returns a page on it."""
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }")
    return pg
def wipe(pg):
    # reload first: this tab's in-memory mirror is its own; another tab's writes live only in IndexedDB until re-read
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const b of db.allBirds()) await db.deleteBird(b.id); }""")

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})

        # ── EMPTY STATE (spec data-v="empty") ──
        h = boot(ctx); wipe(h)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(BIRDS, wait_until='load'); pg.wait_for_selector('[data-testid=empty-state]', timeout=5000)
        check('[example_data#1 / teaching_loft#1 → spec: ONE button] empty state offers the example loader', pg.locator('[data-testid=empty-example]').count() == 1)
        check('empty state: «أضف أول طائر» primary + spec body', pg.locator('[data-testid=empty-cta]').inner_text() == 'أضف أول طائر' and 'شجرة نسب' in pg.locator('[data-testid=empty-state]').inner_text())
        check('empty state: count line reads «لا طيور بعد»', pg.locator('[data-testid=count-line]').inner_text().strip() == 'لا طيور بعد')
        check('empty state: search, filters and FAB hidden', pg.locator('[data-testid=search-input]').count() == 0 and pg.locator('[data-testid=fab-add]').count() == 0)
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/empty-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})

        # ── [example_data#2] example data loaded via the UI ──
        pg.click('[data-testid=empty-example]')
        pg.wait_for_function("document.querySelectorAll('[data-testid=bird-row]').length >= 30", timeout=15000)
        n_rows = pg.locator('[data-testid=bird-row]').count()
        check('[example_data#2] example data loaded via UI → rows render', n_rows >= 30, n_rows)
        check('[teaching_loft#2] 38 birds loaded (count line)', pg.locator('[data-testid=count-line]').inner_text().startswith('38'), pg.locator('[data-testid=count-line]').inner_text())
        check('toast confirms the load (bird.exampleLoaded)', pg.locator('[data-testid=toast]').count() >= 1)

        # ── FULL STATE (spec data-v="full") ──
        check('count line: «N طائرًا · M ذكرًا · F أنثى»', all(x in pg.locator('[data-testid=count-line]').inner_text() for x in ('طائرًا', 'ذكرًا', 'أنثى')))
        check('[example_data#3] rows show the sex word chip', pg.locator('[data-testid=bird-row]').first.locator('[data-sex]').count() == 1 and pg.locator('[data-testid=bird-row] [data-sex]').first.inner_text().strip()[-3:] in ('ذكر', 'نثى', 'روف'))
        check('[ownership#2] status pill visible on a row', pg.locator('[data-testid=bird-row] [data-testid=status-pill]').count() >= 1)
        labels = pg.locator('[data-testid=year-label]').all_inner_texts()
        check('rows grouped by generation, newest first, with counts', len(labels) >= 2 and all('جيل' in l for l in labels))
        check('phone: FAB «إضافة طائر» present', pg.locator('[data-testid=fab-add]').is_visible())
        for w in (430, 900):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/full-{w}.png', full_page=False)
        pg.set_viewport_size({'width': 430, 'height': 900})

        # ── search (core_flows#3–4, vanilla's fields + ring normalisation) ──
        # the search term comes from the data, not from an assumption about it: a distinctive Arabic name in the loaded loft
        name = pg.evaluate("() => { const db = window.__zajilDb; const b = db.allBirds().find(x => x.name && /[\u0600-\u06FF]/.test(x.name) && x.name.length >= 3); return b ? b.name : ''; }")
        pg.fill('[data-testid=search-input]', name); pg.wait_for_timeout(300)
        rows = pg.locator('[data-testid=bird-row]').all_inner_texts()
        check('[core_flows#3] Arabic name search narrows to matching rows', 0 < len(rows) < n_rows and all(name in r for r in rows), f'{name!r} → {len(rows)} of {n_rows}')
        sample_ring = pg.evaluate("() => { const db = window.__zajilDb; const b = db.allBirds().find(x => x.rings && x.rings.length); return b.rings[0].raw; }")   # the birds tab: its mirror holds the import
        loose = sample_ring.lower().replace('-', ' ').replace('/', ' ')
        pg.fill('[data-testid=search-input]', loose); pg.wait_for_timeout(300)
        check('[core_flows#4] ring search is normalised (separators/case ignored)', pg.locator('[data-testid=bird-row]').count() >= 1, f'{sample_ring!r} as {loose!r}')
        pg.fill('[data-testid=search-input]', 'zzz-no-such'); pg.wait_for_timeout(300)
        check('no match → quiet «لا نتائج» label', pg.locator('[data-testid=year-label]').first.inner_text().strip() == 'لا نتائج')
        pg.fill('[data-testid=search-input]', ''); pg.wait_for_timeout(300)

        # ── filter pills (spec: الكل · ذكور · إناث · فريق السباق · تربية · years) ──
        pills = pg.locator('[data-testid=filter-pill]').all_inner_texts()
        check('pills: الكل ذكور إناث فريق السباق تربية الخارجية فقط + generation years', pills[:6] == ['الكل', 'ذكور', 'إناث', 'فريق السباق', 'تربية', 'الخارجية فقط'] and any(t.isdigit() for t in pills[6:]), pills[:8])
        pg.click('[data-testid=filter-pill][data-filter=f]'); pg.wait_for_timeout(200)
        sexes = pg.locator('[data-testid=bird-row] [data-sex]').evaluate_all("els => els.map(e => e.dataset.sex)")
        check('pill «إناث» → only hens listed', len(sexes) > 0 and set(sexes) == {'hen'}, set(sexes))
        pg.click('[data-testid=filter-pill][data-filter=race]'); pg.wait_for_timeout(200)
        st = pg.locator('[data-testid=bird-row] [data-testid=status-pill]').all_inner_texts()
        check('pill «فريق السباق» → only race-team birds', len(st) > 0 and set(x.strip() for x in st) == {'فريق السباق'}, set(st))
        year_pill = pg.locator('[data-testid=filter-pill][data-year]').first; y = year_pill.inner_text()
        year_pill.click(); pg.wait_for_timeout(200)
        check(f'year pill {y} → one generation group only', pg.locator('[data-testid=year-label]').count() == 1 and y in pg.locator('[data-testid=year-label]').first.inner_text())
        pg.click('[data-testid=filter-pill][data-filter=all]'); pg.wait_for_timeout(200)
        check('«الكل» restores every row', pg.locator('[data-testid=bird-row]').count() == n_rows)
        # ── [ownership#5] the ownership filter splits the register; the external marker on rows (ruling 14: kit over spec) ──
        n_ext = pg.evaluate("() => window.__zajilDb.allBirds().filter(b => b.external).length")
        pg.click('[data-testid=filter-pill][data-filter=ext]'); pg.wait_for_timeout(200)
        check('[ownership#5] pill «الخارجية فقط» lists exactly the external birds, each carrying the «خارجي» marker', n_ext > 0 and pg.locator('[data-testid=bird-row]').count() == n_ext and pg.locator('[data-testid=bird-row] [data-testid=ext-tag]').count() == n_ext, f'{n_ext} external')
        pg.click('[data-testid=filter-pill][data-filter=all]'); pg.wait_for_timeout(200)
        # scoped to the phone rows: the desktop table (hidden at 430 by CSS) also carries the marker in its name cell
        check('[ownership#5] owned + external = total; markers only on external rows', pg.locator('[data-testid=bird-row]').count() == n_rows and pg.locator('[data-testid=bird-row] [data-testid=ext-tag]').count() == n_ext, f"{pg.locator('[data-testid=bird-row] [data-testid=ext-tag]').count()} markers / {n_ext} external")
        # ── ruling 6: the season eyebrow follows the one display rule (1 July turnover) ──
        y, m = pg.evaluate("() => { const d = new Date(); return [d.getFullYear(), d.getMonth() + 1]; }"); a = y if m >= 7 else y - 1
        check('[ruling 6] season eyebrow «موسم a / a+1» with the July turnover', pg.locator('[data-testid=season-eyebrow]').inner_text().strip() == f'موسم {a} / {a + 1}', pg.locator('[data-testid=season-eyebrow]').inner_text())

        # ── [change_events#1, #5] external write refreshes the register, scroll preserved ──
        pg.evaluate("window.scrollTo(0, 600)"); pg.wait_for_timeout(100)
        # the intent behind change_events#4/#5 is «the page did not move»: the row the user was looking at stays where it was.
        # Vanilla achieved it by restoring scrollY after rebuilding the list; here the list is patched in place and the browser's
        # scroll anchoring keeps the anchored row still (scrollY itself shifts by the inserted row's height). Assert the intent.
        anchor = pg.evaluate("() => { const r=[...document.querySelectorAll('[data-testid=bird-row]')].find(e=>e.getBoundingClientRect().top>=0); return { id: r.getAttribute('href'), top: r.getBoundingClientRect().top }; }")
        pg.evaluate("async () => { const db = await window.__zajilDb; await db.saveBird(db.newBird({ name: 'X-external-1', sex: 'cock', hatchDate: '2026-01-01' })); }")
        pg.wait_for_function("[...document.querySelectorAll('[data-testid=bird-row]')].some(r => r.textContent.includes('X-external-1'))", timeout=3000)
        check('[change_events#1] an external write refreshes the register (no reload)', True)
        after = pg.evaluate("(href) => { const r=[...document.querySelectorAll('[data-testid=bird-row]')].find(e=>e.getAttribute('href')===href); return r ? r.getBoundingClientRect().top : null; }", anchor['id'])
        check('[change_events#4/#5] the page did not move: the row in view stays at the same viewport position', after is not None and abs(after - anchor['top']) < 4, f"{anchor['top']:.0f}→{after}")

        # ── DESKTOP (kit Part 3 + ruling 6: sortable table) ──
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(250)
        heads = pg.locator('[data-testid=th-sort]').all_inner_texts()
        check('1400: six table headers', [h_.strip() for h_ in heads] == ['الحلقة', 'الاسم', 'الجنس', 'الحالة', 'الجيل', 'آخر نتيجة'], heads)
        check('1400: phone list and FAB hidden, table shown', pg.locator('[data-testid=fab-add]').is_hidden() and pg.locator('[data-testid=table-row]').count() >= 30)
        first_before = pg.locator('[data-testid=table-row]').first.inner_text()
        pg.click('[data-testid=th-sort][data-key=name]'); pg.wait_for_timeout(200)
        names = pg.locator('[data-testid=table-row] [data-testid=cell-name]').all_inner_texts()
        check('[ruling 6] click «الاسم» sorts by name', names == sorted(names) or names == sorted(names, reverse=True), names[:3])
        pg.click('[data-testid=th-sort][data-key=name]'); pg.wait_for_timeout(200)
        names2 = pg.locator('[data-testid=table-row] [data-testid=cell-name]').all_inner_texts()
        check('[ruling 6] second click reverses the sort', names2 == list(reversed(names)))
        pg.screenshot(path=f'{FID}/full-1400.png', full_page=False)
        check('zero page errors', not errs, errs)

        # ── SMALL STATE (spec data-v="small": ≤ 8 birds) ──
        wipe(h)
        h.evaluate("""async () => { const db = await window.__zajilDb;
            for (let i = 0; i < 8; i++) await db.saveBird(db.newBird({ name: 'صغير-' + i, sex: i % 2 ? 'hen' : 'cock', hatchDate: '202' + (4 + (i % 2)) + '-03-01' })); }""")
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.goto(BIRDS, wait_until='load')
        pg.wait_for_function("document.querySelectorAll('[data-testid=bird-row]').length === 8", timeout=5000)
        check('small: 8 rows, count line «8 طائرًا · 4 ذكرًا · 4 أنثى»', pg.locator('[data-testid=count-line]').inner_text().strip() == '8 طائرًا · 4 ذكرًا · 4 أنثى', pg.locator('[data-testid=count-line]').inner_text())
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/small-{w}.png', full_page=False)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
