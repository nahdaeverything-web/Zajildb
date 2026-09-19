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
from _layout import check_clearance, check_toast_clear, scroll_to_bottom, check_caret, shot
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
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); shot(pg, path=f'{FID}/empty-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})

        # ── [example_data#2] example data loaded via the UI ──
        pg.click('[data-testid=empty-example]')
        pg.wait_for_function("document.querySelectorAll('[data-testid=bird-row]').length >= 30", timeout=15000)
        n_rows = pg.locator('[data-testid=bird-row]').count()
        check('[example_data#2] example data loaded via UI → rows render', n_rows >= 30, n_rows)
        check('[teaching_loft#2] 38 birds loaded (count line)', pg.locator('[data-testid=count-line]').inner_text().startswith('38'), pg.locator('[data-testid=count-line]').inner_text())
        check('toast confirms the load (bird.exampleLoaded)', pg.locator('[data-testid=toast]').count() >= 1)
        # [ruling C] the load toast is up over a full list: scrolled to the bottom it must not cover the last row's tap target
        check_toast_clear(pg, check, 'loft home with 38 rows')

        # ── FULL STATE (spec data-v="full") ──
        check('count line: «N طائرًا · M ذكرًا · F أنثى»', all(x in pg.locator('[data-testid=count-line]').inner_text() for x in ('طائرًا', 'ذكرًا', 'أنثى')))
        check('[example_data#3] rows show the sex word chip', pg.locator('[data-testid=bird-row]').first.locator('[data-sex]').count() == 1 and pg.locator('[data-testid=bird-row] [data-sex]').first.inner_text().strip()[-3:] in ('ذكر', 'نثى', 'روف'))
        check('[ownership#2] status pill visible on a row', pg.locator('[data-testid=bird-row] [data-testid=status-pill]').count() >= 1)
        labels = pg.locator('[data-testid=year-label]').all_inner_texts()
        check('rows grouped by generation, newest first, with counts', len(labels) >= 2 and all('جيل' in l for l in labels))
        fab = pg.locator('[data-testid=fab-add] a').bounding_box()
        check('phone: FAB «طير جديد» present, the spec\'s 58px pill', pg.locator('[data-testid=fab-add]').is_visible() and fab and fab['height'] >= 58, f"{fab and round(fab['height'])}px tall")
        check_clearance(pg, check, 'loft home')
        for w in (430, 900):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); shot(pg, path=f'{FID}/full-{w}.png', full_page=False)
        pg.set_viewport_size({'width': 430, 'height': 900})

        # ── search (core_flows#3–4, vanilla's fields + ring normalisation) ──
        # the search term comes from the data, not from an assumption about it: a distinctive Arabic name in the loaded loft
        name = pg.evaluate("() => { const db = window.__zajilDb; const b = db.allBirds().find(x => x.name && /[\u0600-\u06FF]/.test(x.name) && x.name.length >= 3); return b ? b.name : ''; }")
        check_caret(pg, check, 'search-input', 'نجمة', 'loft home')
        pg.fill('[data-testid=search-input]', name); pg.wait_for_timeout(300)
        rows = pg.locator('[data-testid=bird-row]').all_inner_texts()
        check('[core_flows#3] Arabic name search narrows to matching rows', 0 < len(rows) < n_rows and all(name in r for r in rows), f'{name!r} → {len(rows)} of {n_rows}')
        sample_ring = pg.evaluate("() => { const db = window.__zajilDb; const b = db.allBirds().find(x => x.rings && x.rings.length); return b.rings[0].raw; }")   # the birds tab: its mirror holds the import
        loose = sample_ring.lower().replace('-', ' ').replace('/', ' ')
        pg.fill('[data-testid=search-input]', loose); pg.wait_for_timeout(300)
        check('[core_flows#4] ring search is normalised (separators/case ignored) — and matches EXACTLY that bird',
              pg.locator('[data-testid=bird-row]').count() == 1,
              f'{sample_ring!r} as {loose!r} matched {pg.locator("[data-testid=bird-row]").count()} rows')
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
        # [Phase 6, fidelity audit] a status/sex pill AND a year pill together. The spec
        # applies both and lights both (loft-home-v1.html:331-333, :379) and vanilla ANDs
        # every filter (js/views/birds.js:35-40) — but the port's handlers cleared each
        # other, so «إناث» + «2024» could not be reached at all.
        pg.fill('[data-testid=search-input]', ''); pg.wait_for_timeout(250)
        pg.click('[data-testid=filter-pill][data-filter=all]'); pg.wait_for_timeout(300)
        n_all = pg.locator('[data-testid=bird-row]').count()
        pg.click('[data-filter=f]'); pg.wait_for_timeout(350)
        n_f = pg.locator('[data-testid=bird-row]').count()
        yr = pg.locator('[data-year]').first.get_attribute('data-year')
        pg.click(f'[data-year="{yr}"]'); pg.wait_for_timeout(350)
        n_both = pg.locator('[data-testid=bird-row]').count()
        lit = pg.evaluate("() => [...document.querySelectorAll('[data-filter],[data-year]')]"
                          ".filter(e => e.getAttribute('aria-pressed') === 'true')"
                          ".map(e => e.getAttribute('data-filter') || e.getAttribute('data-year'))")
        check('a sex filter AND a year filter apply together, narrowing the list',
              0 < n_both <= n_f < n_all, f'all={n_all} females={n_f} females+{yr}={n_both}')
        check('…and BOTH pills are lit, and say so to a screen reader',
              sorted(lit) == sorted(['f', yr]), str(lit))
        pg.click('[data-filter=all]'); pg.wait_for_timeout(350)
        check('…and «الكل» is the reset that clears both',
              pg.locator('[data-testid=bird-row]').count() == n_all
              and pg.evaluate("() => [...document.querySelectorAll('[data-year]')].every(e => e.getAttribute('aria-pressed') === 'false')"))

        pg.click('[data-testid=filter-pill][data-filter=all]'); pg.wait_for_timeout(250)
        year_pill = pg.locator('[data-testid=filter-pill][data-year]').first; y = year_pill.inner_text()
        year_pill.click(); pg.wait_for_timeout(200)
        check(f'year pill {y} → one generation group only', pg.locator('[data-testid=year-label]').count() == 1 and y in pg.locator('[data-testid=year-label]').first.inner_text())
        # [Phase 6, fidelity audit] the table's sort caret. The spec puts the label and a
        # caret inside `<span class="sort">`, reveals it on the active column and rotates it
        # 180° when descending (loft-home-v1.html:251-256, CSS :109-111). The port rendered a
        # bare span and never set the desc class, so both rules were dead: aria-sort said the
        # direction and nothing showed it.
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(500)
        SORT = """() => { const ths = [...document.querySelectorAll('[data-testid=th-sort]')];
            const act = ths.find(t => t.getAttribute('aria-sort') !== 'none');
            const off = ths.find(t => t.getAttribute('aria-sort') === 'none');
            const g = (t) => { const sv = t && t.querySelector('svg'); const cs = sv && getComputedStyle(sv);
                return { aria: t && t.getAttribute('aria-sort'), svg: !!sv,
                         opacity: cs && cs.opacity, rotated: !!cs && cs.transform !== 'none' }; };
            return { active: g(act), inactive: g(off) }; }"""
        srt = pg.evaluate(SORT)
        check('the table\'s sorted column shows a caret, and the others do not',
              srt['active']['svg'] and srt['active']['opacity'] == '1'
              and srt['inactive']['opacity'] == '0', str(srt))
        check('…and the caret is rotated when the sort is descending',
              srt['active']['aria'] == 'descending' and srt['active']['rotated'], str(srt['active']))
        pg.click('[data-testid=th-sort][data-key=year]'); pg.wait_for_timeout(400)
        srt2 = pg.evaluate(SORT)
        check('…and upright when it is ascending, so the direction is visible and not only announced',
              srt2['active']['aria'] == 'ascending' and not srt2['active']['rotated'], str(srt2['active']))
        pg.click('[data-testid=th-sort][data-key=year]'); pg.wait_for_timeout(300)
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(400)
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
        check('[change_events#1] an external write refreshes the register, with no reload',
              pg.locator('[data-testid=bird-row]', has_text='X-external-1').count() == 1
              and pg.evaluate("() => performance.getEntriesByType('navigation').length") == 1,
              f"{pg.locator('[data-testid=bird-row]', has_text='X-external-1').count()} row(s) for the new bird")
        after = pg.evaluate("(href) => { const r=[...document.querySelectorAll('[data-testid=bird-row]')].find(e=>e.getAttribute('href')===href); return r ? r.getBoundingClientRect().top : null; }", anchor['id'])
        check('[change_events#4/#5] the page did not move: the row in view stays at the same viewport position', after is not None and abs(after - anchor['top']) < 4, f"{anchor['top']:.0f}→{after}")

        # ── DESKTOP (kit Part 3 + ruling 6: sortable table) ──
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(250)
        heads = pg.locator('[data-testid=th-sort]').all_inner_texts()
        check('1400: six table headers', [h_.strip() for h_ in heads] == ['الحلقة', 'الاسم', 'الجنس', 'الحالة', 'الجيل', 'آخر نتيجة'], heads)
        check('1400: phone list and FAB hidden, table shown', pg.locator('[data-testid=fab-add]').is_hidden() and pg.locator('[data-testid=table-row]').count() >= 30)
        # captured HERE, in the state the filename claims: the full register at 1400 on its
        # DEFAULT sort. It used to be captured at the end of this block, after two clicks on
        # «الاسم» had re-sorted the table and reversed it — so the file said "full-1400" and
        # the picture was "full-1400, sorted by name, descending".
        shot(pg, path=f'{FID}/full-1400.png', full_page=False)
        first_before = pg.locator('[data-testid=table-row]').first.inner_text()
        pg.click('[data-testid=th-sort][data-key=name]'); pg.wait_for_timeout(200)
        names = pg.locator('[data-testid=table-row] [data-testid=cell-name]').all_inner_texts()
        check('[ruling 6] click «الاسم» sorts by name', names == sorted(names) or names == sorted(names, reverse=True), names[:3])
        pg.click('[data-testid=th-sort][data-key=name]'); pg.wait_for_timeout(200)
        names2 = pg.locator('[data-testid=table-row] [data-testid=cell-name]').all_inner_texts()
        check('[ruling 6] second click reverses the sort', names2 == list(reversed(names)))
        # ── A BIRD WITH NO NAME RENDERS SOMETHING, IN BOTH VIEWS ───────────────────────
        # A bird found in the register with a blank name cell, ring JO-2026-7591, entered by
        # hand. Both halves of it were real:
        #   · the record genuinely had name:"". Nothing requires a name — the form trims it
        #     (bird/form.tsx:208) and classifySave has no name rule at all (engine/validate.js),
        #     so a nameless bird is a legitimate record, not a corrupt one.
        #   · and the two views DISAGREED about what to do with it. The phone row already fell
        #     back to the ring (birds/view.tsx:151); the desktop table did not, and rendered an
        #     empty <td>. One register, two readings of the same record.
        # So this asserts the property for both views at once, over three shapes of nameless
        # bird — the desktop table is the one that was broken, and the phone list is what stops
        # the fix being a table-only patch that lets them drift apart again.
        wipe(h)
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            const mk = async (o) => db.saveBird({ ...db.newBird({ sex: 'cock', hatchDate: '2026-01-01' }), ...o });
            const ring = (raw) => [{ raw, type: 'official' }];   // primaryRing reads .raw (BirdBits.tsx:12)
            await mk({ name: '', rings: ring('JO-2026-7591') });    // the one that was reported
            await mk({ name: '   ', rings: ring('JO-2026-7592') }); // whitespace is not a name
            await mk({ name: '', rings: [] });                      // no name AND no ring at all
            await mk({ name: 'مسمّى', rings: ring('JO-2026-7594') }); // a control: a named bird
        }""")
        pg.goto(BIRDS, wait_until='load'); pg.wait_for_timeout(1200)

        # the NAME SLOT in each view, not the whole row: the phone row also prints the ring on
        # its second line, so a row-level check reports a blank name slot as answered. That is
        # the weaker test passing while the defect stands.
        for vw, sel in ((430, '[data-testid=bird-row] [data-testid=row-name]'),
                        (1400, '[data-testid=table-row] [data-testid=cell-name]')):
            pg.set_viewport_size({'width': vw, 'height': 900}); pg.wait_for_timeout(300)
            cells = pg.locator(sel).all_inner_texts()
            check(f'@{vw}: all four birds are listed (else this proves nothing)',
                  len(cells) == 4, f'{len(cells)} row(s)')
            blank = [i for i, c in enumerate(cells) if not c.strip()]
            check(f'@{vw}: no bird renders as a blank — a nameless one falls back to its ring or id',
                  not blank, f'row(s) {blank} empty of {len(cells)}: {cells}')
            check(f'@{vw}: the reported bird shows its ring where its name would be',
                  any('JO-2026-7591' in c for c in cells), cells)
            check(f'@{vw}: a whitespace-only name is treated as no name, not as a name',
                  any('JO-2026-7592' in c for c in cells), cells)
            check(f'@{vw}: the control bird still shows its NAME, not its ring',
                  any('مسمّى' in c for c in cells), cells)

        # and the two views must agree — the defect was not the empty cell, it was the
        # disagreement. Compare the identifying text the two renderings settle on.
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(300)
        phone = sorted(c.strip() for c in pg.locator('[data-testid=bird-row] [data-testid=row-name]').all_inner_texts())
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(300)
        table = sorted(c.strip() for c in pg.locator('[data-testid=table-row] [data-testid=cell-name]').all_inner_texts())
        check('the phone list and the desktop table name the same four birds the same way',
              phone == table, f'phone {phone}  table {table}')

        check('zero page errors', not errs, errs)

        # ── SMALL STATE (spec data-v="small": ≤ 8 birds) ──
        wipe(h)
        # id AND createdAt are SEEDED, so this fixture's order is total. Measured, after a
        # wrong guess: small-1400.png is the DESKTOP TABLE, which sorts by YEAR alone — and
        # these eight birds occupy two years, so every comparison inside a year is a tie.
        # Array.sort is stable, so ties keep source order, and source order is the IndexedDB
        # key order, i.e. uuid. Three trials with seeded createdAt still gave three different
        # pictures, and in each the table order matched the uuid order exactly. Fresh uuids
        # every run were the whole cause. (For a real loft this is stable but arbitrary: same-
        # year birds sort by an id nobody can see. That is a design question, not a bug — see
        # ROOT-FINDINGS.)
        h.evaluate("""async () => { const db = await window.__zajilDb;
            for (let i = 0; i < 8; i++) await db.saveBird(db.newBird({ name: 'صغير-' + i, sex: i % 2 ? 'hen' : 'cock', hatchDate: '202' + (4 + (i % 2)) + '-03-01',
                id: '00000000-0000-4000-8000-00000000000' + i, createdAt: '2026-03-01T08:0' + i + ':00.000Z' })); }""")
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.goto(BIRDS, wait_until='load')
        pg.wait_for_function("document.querySelectorAll('[data-testid=bird-row]').length === 8", timeout=5000)
        check('small: 8 rows, count line «8 طائرًا · 4 ذكرًا · 4 أنثى»', pg.locator('[data-testid=count-line]').inner_text().strip() == '8 طائرًا · 4 ذكرًا · 4 أنثى', pg.locator('[data-testid=count-line]').inner_text())
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); shot(pg, path=f'{FID}/small-{w}.png', full_page=False)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
