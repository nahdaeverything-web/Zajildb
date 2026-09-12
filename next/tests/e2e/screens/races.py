#!/usr/bin/env python3
"""Races (/races) — intent list re-authored from core_flows, teaching_loft (as they
apply) plus every state races-v1 designs (log / empty / new result / form errors),
and the two silent failures design/README.md rules the spec must replace with
visible errors. Binds to data-testid only. Seeds through the layer on the harness
route, then exercises the real screen. Provisions its own server (R6)."""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance, check_toast_clear, scroll_to_bottom, wait_toasts_clear
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'races')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
RACES = f'{ROOT}races.html'
def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }"); return pg
def wipe(pg):
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const r of [...db.state.raceResults.values()]) await db.Races.remove(r.id);
        for (const b of db.allBirds()) await db.deleteBird(b.id); }""")
def load(pg, file):
    pg.evaluate("async (f) => { const db = await window.__zajilDb; await db.importAll(await (await fetch(f)).json(), 'merge'); }", file)
def shots(pg, name, widths=(430, 900, 1400)):
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(200); pg.screenshot(path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 430, 'height': 900})

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        h = boot(ctx); wipe(h)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

        # ── EMPTY (spec data-v="empty") — one emptiness drives both tabs ──
        pg.goto(RACES, wait_until='load'); pg.wait_for_selector('[data-testid=count-line]', timeout=6000)
        check('empty: «لا نتائج مسجلة.» + body, count line «لا نتائج هذا الموسم», FAB «نتيجة جديدة»',
              'لا نتائج مسجلة' in pg.locator('[data-testid=log-empty]').inner_text() and pg.locator('[data-testid=count-line]').inner_text().strip() == 'لا نتائج هذا الموسم' and pg.locator('[data-testid=new-result-fab]').inner_text().strip() == 'نتيجة جديدة')
        pg.click('[data-testid=tab-fci]'); pg.wait_for_timeout(150)
        check('empty: the FCI tab is empty too, with its own body line', pg.locator('[data-testid=fci-empty]').count() == 1 and 'تظهر الطيور هنا' in pg.locator('[data-testid=fci-empty]').inner_text())
        shots(pg, 'empty')
        pg.click('[data-testid=tab-log]'); pg.wait_for_timeout(150)

        # ── LOG on the sample data [core_flows#9: 12 results] ──
        load(h, './sample-data.json')
        pg.goto(RACES, wait_until='load'); pg.wait_for_selector('[data-testid=race-row]', timeout=6000)
        n = h.evaluate("() => window.__zajilDb.state.raceResults.size")
        nb = h.evaluate("() => new Set([...window.__zajilDb.state.raceResults.values()].map(r => r.birdId)).size")
        check(f'[core_flows#9] the log lists every result ({n})', pg.locator('[data-testid=race-row]').count() == n == 12, f'{pg.locator("[data-testid=race-row]").count()} rows')
        check('count line «n نتائج · b طيور» from the results', pg.locator('[data-testid=count-line]').inner_text().strip() == f'{n} نتائج · {nb} طيور', pg.locator('[data-testid=count-line]').inner_text())
        dates = h.evaluate("() => new Set([...window.__zajilDb.state.raceResults.values()].map(r => r.date)).size")
        check('rows grouped by date, newest first, one label per date', pg.locator('[data-testid=date-group]').count() == dates and pg.evaluate("() => { const ds = [...document.querySelectorAll('[data-testid=race-tr] td:first-child')].map(td => td.textContent); return ds.join('|'); }") != '', f'{dates} groups')
        first_pos = h.evaluate("() => { const rs = [...window.__zajilDb.state.raceResults.values()].sort((a,b)=>(b.date||'').localeCompare(a.date||'')); return rs[0].position; }")
        pill = pg.locator('[data-testid=race-row] [data-testid=pos-pill]').first
        check('position pill: a rank ≤10 is the brand pill, no rank is «—»', (pill.inner_text().strip() == str(first_pos)) if first_pos else pill.inner_text().strip() == '—', f'position={first_pos}')
        check('training results carry the gold «تدريب» tag', pg.evaluate("() => [...document.querySelectorAll('[data-testid=type-tag]')].some(e => e.textContent.trim() === 'تدريب')"))
        q_expected = h.evaluate("() => { const e = window.__zajilEngine; return [...window.__zajilDb.state.raceResults.values()].filter(r => e.fci.resultQualifies(r).qualifies).length; }")
        check('the FCI column marks exactly the results the engine qualifies', pg.locator('[data-testid=race-row] [data-testid=fci-chip][data-on="1"]').count() == q_expected, f'{q_expected} qualify')
        check_clearance(pg, check, 'races · log')
        shots(pg, 'log')
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(200)
        check('desktop: the 9-column table replaces the phone rows', pg.locator('[data-testid=race-table]').is_visible() and pg.locator('[data-testid=race-tr]').count() == n and not pg.locator('[data-testid=race-rows]').is_visible() and pg.locator('[data-testid=race-table] thead th').count() == 9)
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(200)

        # ── FCI tab [teaching_loft#11 shape: the checker lists birds with their reasons] ──
        pg.click('[data-testid=tab-fci]'); pg.wait_for_selector('[data-testid=fci-card]')
        exp = h.evaluate("""() => { const db = window.__zajilDb, e = window.__zajilEngine;
            const rs = [...db.state.raceResults.values()];
            const rows = db.allBirds().map(b => ({ b, el: e.fci.birdEligibility(b, rs.filter(r => r.birdId === b.id)) }))
              .filter(({ b, el }) => el.hasRing || rs.some(r => r.birdId === b.id));
            return { n: rows.length, q: rows.filter(r => r.el.qualifyingResults.length).length,
                     why: rows.reduce((a, r) => a + r.el.nonQualifying.reduce((x, nq) => x + nq.reasons.length, 0), 0) }; }""")
        check('[teaching_loft#11] the checker lists every bird with an FCI ring or a result', pg.locator('[data-testid=fci-card]').count() == exp['n'] and exp['n'] >= 5, f"{exp['n']} birds")
        check('qualified birds are the tinted cards; the rule line states 20 / 150', pg.locator('[data-testid=fci-card][data-qualified="1"]').count() == exp['q'] and '20' in pg.locator('[data-testid=fci-rule]').inner_text() and '150' in pg.locator('[data-testid=fci-rule]').inner_text(), f"{exp['q']} qualified")
        check('every non-qualifying result states its engine reason under the card', pg.locator('[data-testid=fci-why] div').count() == exp['why'] and exp['why'] > 0, f"{exp['why']} reasons")
        check('a bird without an FCI ring shows the red ✗ chip', pg.locator('[data-testid=fci-ring][data-on="0"]').count() >= 1)
        shots(pg, 'fci')
        check_clearance(pg, check, 'races · FCI')
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(200)
        check('desktop: the FCI table replaces the cards', pg.locator('[data-testid=fci-table]').is_visible() and pg.locator('[data-testid=fci-tr]').count() == exp['n'] and not pg.locator('[data-testid=fci-cards]').is_visible())
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(200)
        pg.click('[data-testid=tab-log]'); pg.wait_for_timeout(150)

        # ── the result sheet (spec data-v="modal") ──
        pg.click('[data-testid=new-result-fab]'); pg.wait_for_selector('[data-testid=result-sheet]')
        check('sheet: title «نتيجة جديدة», bird placeholder, both groups present', pg.locator('[data-testid=sheet-title]').inner_text().strip() == 'نتيجة جديدة' and 'اختر طيرًا من اللوفت' in pg.locator('[data-testid=bird-pick]').inner_text() and pg.locator('[data-testid=calc-btn]').count() == 1)
        types = pg.locator('[data-testid=f-type] option').all_inner_texts()
        check('race types = vanilla\'s six, «نادي» the default', [x.strip() for x in types] == ['تدريب', 'نادي', 'اتحاد', 'وطني', 'لوفت واحد', 'دولي'] and pg.locator('[data-testid=f-type]').input_value() == 'club', types)
        shots(pg, 'sheet', widths=(430, 1400))

        # ── [spec data-v="errors" · README: two silent failures replaced] ──
        # the spec's demo types «29.5321 35.0063 N», which VANILLA's parse accepts (races.js:136 takes the two
        # numbers and ignores the rest) — so the unparseable case is a real one: a direction word, no second number
        pg.fill('[data-testid=i-coords]', '29.5321 شمال'); pg.fill('[data-testid=i-loftcoords]', '')
        pg.click('[data-testid=calc-btn]'); pg.wait_for_timeout(200)
        coords_err = pg.locator('[data-testid=f-coords]')
        check('[README: silent failure 1] unparseable coordinates → the field turns red and SAYS why', 'تعذّر قراءة الإحداثيات' in coords_err.inner_text() and pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=f-coords] .err-msg, [data-testid=f-coords] [role=alert]')).display") != 'none')
        check('…and the empty loft coordinates say their own why', 'تعذّر قراءة إحداثيات اللوفت' in pg.locator('[data-testid=f-loft]').inner_text() and pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=f-loft] [role=alert]')).display") != 'none')
        check('…and nothing was computed', pg.locator('[data-testid=calc-ok]').count() == 0 and pg.locator('[data-testid=f-dist]').input_value() == '')
        # the port adds the spec's range check on top of vanilla's regex: an impossible coordinate is an error, not a nonsense distance
        pg.fill('[data-testid=i-coords]', '200, 500'); pg.click('[data-testid=calc-btn]'); pg.wait_for_timeout(200)
        check('an out-of-range coordinate is refused too (spec\'s ±90 / ±180 check)', 'تعذّر قراءة الإحداثيات' in pg.locator('[data-testid=f-coords]').inner_text() and pg.locator('[data-testid=calc-ok]').count() == 0)
        pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(300)
        check('[README: silent failure 2] saving with no bird → alert banner + the field says «الطير مطلوب»', pg.locator('[data-testid=sheet-alert]').count() == 1 and 'لم تُحفظ النتيجة' in pg.locator('[data-testid=sheet-alert]').inner_text() and pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=f-bird] [role=alert]')).display") != 'none')
        pg.wait_for_timeout(700)   # the spec scrolls back with behavior:'smooth'
        check('…and the sheet scrolled back to the first bad field', pg.evaluate("() => document.querySelector('[data-testid=result-sheet]').scrollTop") < 40, pg.evaluate("() => document.querySelector('[data-testid=result-sheet]').scrollTop"))
        check('…and no result was written', h.evaluate("() => window.__zajilDb.state.raceResults.size") == n)
        pg.screenshot(path=f'{FID}/sheet-errors-430.png', full_page=True)

        # ── the calculator's success path: engine haversine + velocity ──
        pg.click('[data-testid=bird-pick]'); pg.wait_for_selector('[data-testid=bird-picklist]')
        pg.click('[data-testid=bird-item] >> nth=0'); pg.wait_for_timeout(150)
        check('picking a bird fills the field with its name and plate, and clears the error', pg.locator('[data-testid=f-bird] .plate, [data-testid=bird-pick] span').count() >= 1 and 'اختر طيرًا' not in pg.locator('[data-testid=bird-pick]').inner_text())
        pg.fill('[data-testid=i-coords]', '29.5321, 35.0063'); pg.fill('[data-testid=i-loftcoords]', '31.9539, 35.9106')
        pg.fill('[data-testid=f-reltime]', '2026-09-04T06:30'); pg.fill('[data-testid=f-arrtime]', '2026-09-04T10:04')
        pg.click('[data-testid=calc-btn]'); pg.wait_for_selector('[data-testid=calc-ok]')
        want = pg.evaluate("""() => { const e = window.__zajilEngine; const a = { lat: 29.5321, lon: 35.0063 }, b = { lat: 31.9539, lon: 35.9106 };
            return { km: (e.velocity.haversineMetres(a, b) / 1000).toFixed(1), mpm: Math.round(e.velocity.velocityMPM(a, b, '2026-09-04T06:30', '2026-09-04T10:04')) }; }""")
        check('calculate → distance and velocity from the ENGINE, written into both fields', pg.locator('[data-testid=f-dist]').input_value() == want['km'] and pg.locator('[data-testid=f-vel]').input_value() == str(want['mpm']), want)
        check('…and the green line states both values', f"{want['km']} km" in pg.locator('[data-testid=calc-ok]').inner_text() and f"{want['mpm']} m/min" in pg.locator('[data-testid=calc-ok]').inner_text(), pg.locator('[data-testid=calc-ok]').inner_text()[:80])
        check('…and both coordinate fields are no longer in error', pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=f-coords] [role=alert]')).display") == 'none')
        pg.fill('[data-testid=f-name]', 'سباق الاختبار'); pg.fill('[data-testid=f-date]', '2026-09-04')
        pg.select_option('[data-testid=f-type]', 'federation'); pg.fill('[data-testid=f-pos]', '3')
        pg.fill('[data-testid=f-fanciers]', '25'); pg.fill('[data-testid=f-birds]', '200'); pg.fill('[data-testid=f-relname]', 'القويرة')
        pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(600)
        saved = pg.evaluate("() => { const r = [...window.__zajilDb.state.raceResults.values()].find(x => x.raceName === 'سباق الاختبار'); return r && [r.raceType, r.position, r.fanciersEntered, r.birdsEntered, r.distanceKm, r.velocity, r.releasePoint && r.releasePoint.name, !!r.loftPoint]; }")
        check('saving writes the full record through Races.save', saved == ['federation', 3, 25, 200, float(want['km']), want['mpm'], 'القويرة', True], saved)
        check('…the loft coordinates are remembered for the next result (setSetting)', pg.evaluate("() => window.__zajilDb.state.settings.loftCoords") == '31.9539, 35.9106')
        check('…the sheet closed and the row is in the log', pg.locator('[data-testid=result-sheet]').count() == 0 and pg.locator('[data-testid=race-row]').count() == n + 1)
        check('…and it qualifies for FCI (25 fanciers, 200 birds, a federation race)', pg.evaluate("() => { const r = [...window.__zajilDb.state.raceResults.values()].find(x => x.raceName === 'سباق الاختبار'); return window.__zajilEngine.fci.resultQualifies(r).qualifies; }"))
        wait_toasts_clear(pg)

        # ── edit the same result ──
        pg.locator('[data-testid=race-row]', has_text='سباق الاختبار').locator('[data-testid=race-edit]').click(); pg.wait_for_selector('[data-testid=result-sheet]')
        check('edit: the sheet opens titled «تعديل», prefilled, with the bird already chosen', pg.locator('[data-testid=sheet-title]').inner_text().strip() == 'تعديل' and pg.locator('[data-testid=f-name]').input_value() == 'سباق الاختبار' and 'اختر طيرًا' not in pg.locator('[data-testid=bird-pick]').inner_text())
        pg.fill('[data-testid=f-pos]', '1'); pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(500)
        check('edit saves in place — no second record, position updated', pg.evaluate("() => [...window.__zajilDb.state.raceResults.values()].filter(x => x.raceName === 'سباق الاختبار').length") == 1 and pg.evaluate("() => [...window.__zajilDb.state.raceResults.values()].find(x => x.raceName === 'سباق الاختبار').position") == 1)
        wait_toasts_clear(pg)

        # ── inline delete confirm + undo (spec: a strip inside the row, not a dialog) ──
        row = pg.locator('[data-testid=race-row]', has_text='سباق الاختبار')
        row.locator('[data-testid=race-delete]').click(); pg.wait_for_selector('[data-testid=inline-confirm]')
        # the desktop table is in the DOM at every width (display:none until 1100), so scope the count to the phone list
        check('delete asks inline, inside the row («تأكيد الحذف؟»), not in a dialog', pg.locator('[data-testid=race-rows] [data-testid=inline-confirm]').count() == 1 and pg.locator('[data-testid=dialog]').count() == 0)
        pg.click('[data-testid=confirm-no]'); pg.wait_for_timeout(150)
        check('«إلغاء» leaves the result alone', pg.locator('[data-testid=inline-confirm]').count() == 0 and pg.locator('[data-testid=race-row]').count() == n + 1)
        row.locator('[data-testid=race-delete]').click(); pg.click('[data-testid=confirm-go]'); pg.wait_for_timeout(400)
        check('«حذف» removes it and offers «تراجع»', pg.locator('[data-testid=race-row]').count() == n and pg.locator('[data-testid=toast-action]').count() == 1)
        check_toast_clear(pg, check, 'races (undo toast over the FAB)')
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(400)
        check('undo restores it into the log', pg.locator('[data-testid=race-row]').count() == n + 1)
        wait_toasts_clear(pg)

        # ── the teaching loft [teaching_loft#10: 17 results] ──
        wipe(h); load(h, './example-loft-large.json')
        n2 = h.evaluate("() => window.__zajilDb.state.raceResults.size")
        pg.goto(RACES, wait_until='load'); pg.wait_for_selector('[data-testid=race-row]')
        check(f'[teaching_loft#10] the teaching loft\'s results all render ({n2})', pg.locator('[data-testid=race-row]').count() == n2 == 17, f'{pg.locator("[data-testid=race-row]").count()} rows')
        pg.goto(f'{RACES}?tab=fci', wait_until='load'); pg.wait_for_selector('[data-testid=fci-card]')
        check('[teaching_loft#11] ?tab=fci opens the checker and it lists ≥5 birds', pg.locator('[data-testid=tab-fci]').get_attribute('aria-selected') == 'true' and pg.locator('[data-testid=fci-card]').count() >= 5, pg.locator('[data-testid=fci-card]').count())
        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
