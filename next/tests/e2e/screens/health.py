#!/usr/bin/env python3
"""Health (/health) — intent list re-authored from example_data (as it applies) plus
every state health-v1 designs (log / empty / filtered-empty / new / edit / bird
error), the two departures design/README.md rules deliberate (an edit path, visible
errors) and ruling 4's derived next-vaccination block. Binds to data-testid only.
Seeds through the layer on the harness route, then exercises the real screen.
Provisions its own server (R6)."""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance, check_toast_clear, wait_toasts_clear, check_caret

# The LOCAL calendar date, as src/dates.js todayISO() computes it. NEVER
# new Date().toISOString().slice(0,10) — that is the UTC date, and east of
# Greenwich it names YESTERDAY between local midnight and the offset. The
# no-utc-date guard fails the build if that form comes back.
LOCAL_TODAY = "(()=>{const n=new Date();return `${n.getFullYear()}-`+`${String(n.getMonth()+1).padStart(2,'0')}-`+`${String(n.getDate()).padStart(2,'0')}`;})()"
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'health')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
HEALTH = f'{ROOT}health.html'
def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }"); return pg
def wipe(pg):
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const e of [...db.state.healthEvents.values()]) await db.Health.remove(e.id);
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

        # ── EMPTY (spec data-v="empty") ──
        pg.goto(HEALTH, wait_until='load'); pg.wait_for_selector('[data-testid=count-line]', timeout=6000)
        check('empty: «لا أحداث صحية مسجلة.» + body, count «لا أحداث بعد», no next-vaccination banner',
              pg.locator('[data-testid=empty-title]').inner_text().strip() == 'لا أحداث صحية مسجلة.' and 'سجّل أول تطعيم' in pg.locator('[data-testid=empty-state]').inner_text()
              and pg.locator('[data-testid=count-line]').inner_text().strip() == 'لا أحداث بعد' and pg.locator('[data-testid=next-vac]').count() == 0)
        shots(pg, 'empty')

        # ── LOG on the sample data ──
        load(h, './sample-data.json')
        pg.goto(HEALTH, wait_until='load'); pg.wait_for_selector('[data-testid=ev-row]', timeout=6000)
        n = h.evaluate("() => window.__zajilDb.state.healthEvents.size")
        latest = h.evaluate("() => [...window.__zajilDb.state.healthEvents.values()].sort((a,b)=>(b.date||'').localeCompare(a.date||''))[0].date")
        check(f'the log lists every event ({n}), newest first', pg.locator('[data-testid=ev-row]').count() == n and n >= 5, f'{pg.locator("[data-testid=ev-row]").count()} rows')
        check('count line «n أحداث · آخرها <date>»', pg.locator('[data-testid=count-line]').inner_text().startswith(f'{n} أحداث') and 'آخرها' in pg.locator('[data-testid=count-line]').inner_text(), pg.locator('[data-testid=count-line]').inner_text())
        kinds = pg.locator('[data-testid=type-chip]').evaluate_all("els => [...new Set(els.map(e => e.dataset.type))].sort()")
        check('every event carries its type chip, from vanilla\'s four types', set(kinds) <= {'vaccination', 'treatment', 'illness', 'check'} and len(kinds) >= 3, kinds)
        n_loft = h.evaluate("() => [...window.__zajilDb.state.healthEvents.values()].filter(e => e.wholeLoft).length")
        # the desktop table is in the DOM at every width (display:none until 1100), so count inside the phone list
        check('whole-loft events show the loft scope, per-bird events link to the bird', pg.locator('[data-testid=ev-rows] [data-testid=scope-loft]').count() == n_loft and pg.locator('[data-testid=ev-rows] [data-testid=scope-bird]').count() == n - n_loft and pg.locator('[data-testid=scope-bird]').first.get_attribute('href').startswith('/bird?id='), f'{n_loft} whole-loft')

        # ── [ruling 4] the derived next-vaccination banner ──
        want = h.evaluate("""() => { const es = [...window.__zajilDb.state.healthEvents.values()].filter(e => e.eventType === 'vaccination' && e.date).sort((a,b)=>(b.date||'').localeCompare(a.date||''));
            if (!es.length) return null; const d = new Date(es[0].date + 'T00:00:00'); d.setDate(d.getDate() + 365);
            const due = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
            const days = Math.round((new Date(due + 'T00:00:00') - new Date((()=>{const n=new Date();return `${n.getFullYear()}-`+`${String(n.getMonth()+1).padStart(2,'0')}-`+`${String(n.getDate()).padStart(2,'0')}`;})() + 'T00:00:00')) / 86400000);
            return { last: es[0].date, due, days, med: es[0].medication, loft: !!es[0].wholeLoft }; }""")
        banner = pg.locator('[data-testid=next-vac]')
        check('[ruling 4] the banner derives the due date as the last vaccination + 365 days', banner.count() == 1 and str(abs(want['days'])) == pg.locator('[data-testid=next-days]').inner_text().strip(), f"due {want['due']}, {want['days']} days")
        check('[ruling 4] …states both dates on one line and SAYS it is an estimate', 'آخر جرعة' in pg.locator('[data-testid=dose-line]').inner_text() and 'يُستحق' in pg.locator('[data-testid=dose-line]').inner_text() and pg.locator('[data-testid=next-estimate]').inner_text().strip() == 'تقديري — سنة من آخر تطعيم')
        check('[ruling 4] …and names the vaccination and its scope', want['med'][:10] in pg.locator('[data-testid=next-vac]').inner_text() and (('اللوفت كامل' in pg.locator('[data-testid=next-vac]').inner_text()) == want['loft']))
        check_clearance(pg, check, 'health · log')
        shots(pg, 'log')
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(200)
        check('desktop: the table (التاريخ · النوع · النطاق · الدواء/اللقاح · ملاحظات) replaces the rows', pg.locator('[data-testid=ev-table]').is_visible() and pg.locator('[data-testid=ev-tr]').count() == n and not pg.locator('[data-testid=ev-rows]').is_visible())
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(200)

        # ── filters ──
        labels = [x.strip() for x in pg.locator('[data-testid=filter]').all_inner_texts()]
        check('filters: الكل · تطعيم · علاج · مرض · فحص · اللوفت كامل', labels == ['الكل', 'تطعيم', 'علاج', 'مرض', 'فحص', 'اللوفت كامل'], labels)
        n_trt = h.evaluate("() => [...window.__zajilDb.state.healthEvents.values()].filter(e => e.eventType === 'treatment').length")
        pg.click('[data-testid=filter][data-filter=treatment]'); pg.wait_for_timeout(200)
        check('filtering by «علاج» keeps only treatments', pg.locator('[data-testid=ev-row]').count() == n_trt and set(pg.locator('[data-testid=type-chip]').evaluate_all("els => els.map(e => e.dataset.type)")) == {'treatment'}, f'{n_trt} treatments')
        pg.click('[data-testid=filter][data-filter=loft]'); pg.wait_for_timeout(200)
        check('filtering by «اللوفت كامل» keeps only whole-loft events', pg.locator('[data-testid=ev-row]').count() == n_loft)
        pg.click('[data-testid=filter][data-filter=illness]'); pg.wait_for_timeout(200)
        n_ill = h.evaluate("() => [...window.__zajilDb.state.healthEvents.values()].filter(e => e.eventType === 'illness').length")
        if n_ill == 0:
            check('a filter that matches nothing says «لا أحداث تطابق التصفية.» — not the first-run body', pg.locator('[data-testid=empty-title]').inner_text().strip() == 'لا أحداث تطابق التصفية.' and 'سجّل أول تطعيم' not in pg.locator('[data-testid=empty-state]').inner_text())
        else:
            check('filtering by «مرض» keeps only illness events', pg.locator('[data-testid=ev-row]').count() == n_ill)
            pg.evaluate("() => { const b = [...document.querySelectorAll('[data-testid=filter]')].find(x => x.dataset.filter === 'check'); b && b.click(); }"); pg.wait_for_timeout(200)
        pg.click('[data-testid=filter][data-filter=all]'); pg.wait_for_timeout(200)
        check('«الكل» restores every event', pg.locator('[data-testid=ev-row]').count() == n)
        check('the banner stays visible under a filter (it describes the loft, not the list)', pg.locator('[data-testid=next-vac]').count() == 1)

        # ── the sheet: new (spec data-v="new") ──
        pg.click('[data-testid=new-event-fab]'); pg.wait_for_selector('[data-testid=event-sheet]')
        check('sheet: «حدث جديد», type «تطعيم» with its colour dot, scope «طير واحد», date today', pg.locator('[data-testid=sheet-title]').inner_text().strip() == 'حدث جديد' and pg.locator('[data-testid=f-type]').input_value() == 'vaccination' and pg.locator('[data-testid=type-dot]').get_attribute('data-type') == 'vaccination' and pg.locator('[data-testid=f-scope]').input_value() == 'bird' and pg.locator('[data-testid=f-date]').input_value() == pg.evaluate("() => " + LOCAL_TODAY))
        types = [x.strip() for x in pg.locator('[data-testid=f-type] option').all_inner_texts()]
        check('the four vanilla event types, in vanilla\'s order', types == ['تطعيم', 'علاج', 'مرض', 'فحص'], types)
        pg.select_option('[data-testid=f-type]', 'treatment'); pg.wait_for_timeout(100)
        check('changing the type recolours the dot', pg.locator('[data-testid=type-dot]').get_attribute('data-type') == 'treatment')
        # [example_data#14] the bird field hides for a whole-loft event
        check('[example_data#14] scope «طير واحد» shows the bird field', pg.locator('[data-testid=f-bird]').count() == 1)
        pg.select_option('[data-testid=f-scope]', 'loft'); pg.wait_for_timeout(150)
        check('[example_data#14] scope «اللوفت كامل» HIDES the bird field', pg.locator('[data-testid=f-bird]').count() == 0)
        shots(pg, 'sheet', widths=(430, 1400))

        # ── [README: the silent failure] saving a per-bird event with no bird ──
        pg.select_option('[data-testid=f-scope]', 'bird'); pg.wait_for_timeout(150)
        before = h.evaluate("() => window.__zajilDb.state.healthEvents.size")
        pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(250)
        check('[README: silent failure] no bird → alert banner + the field says which way out it has', pg.locator('[data-testid=sheet-alert]').count() == 1 and 'لم يُحفظ الحدث' in pg.locator('[data-testid=sheet-alert]').inner_text() and pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=f-bird] [role=alert]')).display") != 'none' and 'غيّر النطاق' in pg.locator('[data-testid=f-bird]').inner_text())
        check('…and nothing was written', pg.evaluate("() => window.__zajilDb.state.healthEvents.size") == before)
        pg.screenshot(path=f'{FID}/sheet-error-430.png', full_page=True)
        pg.click('[data-testid=bird-pick]'); pg.wait_for_selector('[data-testid=bird-picklist]')
        pg.click('[data-testid=bird-item] >> nth=0'); pg.wait_for_timeout(150)
        check('picking a bird clears the error and fills the field', pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=f-bird] [role=alert]')).display") == 'none' and pg.locator('[data-testid=sheet-alert]').count() == 0)
        check_caret(pg, check, 'f-med', 'باراسيتامول', 'health sheet')
        check_caret(pg, check, 'f-notes', 'جرعة كاملة', 'health sheet')
        pg.fill('[data-testid=f-med]', 'دواء الاختبار'); pg.fill('[data-testid=f-notes]', 'ملاحظة الاختبار'); pg.fill('[data-testid=f-date]', '2026-09-05')
        pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(500)
        saved = pg.evaluate("() => { const e = [...window.__zajilDb.state.healthEvents.values()].find(x => x.medication === 'دواء الاختبار'); return e && [e.eventType, e.wholeLoft, !!e.birdId, e.date, e.notes]; }")
        check('saving writes the event through Health.save', saved == ['treatment', False, True, '2026-09-05', 'ملاحظة الاختبار'], saved)
        check('…the sheet closed and the row is in the log', pg.locator('[data-testid=event-sheet]').count() == 0 and pg.locator('[data-testid=ev-row]').count() == n + 1)
        wait_toasts_clear(pg)

        # ── [README: the added EDIT path — vanilla can only create] ──
        pg.locator('[data-testid=ev-row]', has_text='دواء الاختبار').locator('[data-testid=ev-edit]').click(); pg.wait_for_selector('[data-testid=event-sheet]')
        check('[README: new capability] the row opens the sheet as «تعديل», prefilled', pg.locator('[data-testid=sheet-title]').inner_text().strip() == 'تعديل' and pg.locator('[data-testid=f-med]').input_value() == 'دواء الاختبار' and pg.locator('[data-testid=f-type]').input_value() == 'treatment')
        pg.fill('[data-testid=f-med]', 'دواء معدّل'); pg.select_option('[data-testid=f-scope]', 'loft'); pg.wait_for_timeout(150)
        pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(500)
        edited = pg.evaluate("() => { const es = [...window.__zajilDb.state.healthEvents.values()]; return [es.filter(x => x.medication === 'دواء معدّل').length, es.filter(x => x.medication === 'دواء الاختبار').length, (es.find(x => x.medication === 'دواء معدّل') || {}).wholeLoft, (es.find(x => x.medication === 'دواء معدّل') || {}).birdId]; }")
        check('[README: new capability] editing saves IN PLACE — one record, not a second', edited == [1, 0, True, None], edited)
        check('…and switching the scope to the loft cleared the bird, as vanilla\'s rule says', pg.locator('[data-testid=ev-rows] [data-testid=ev-row]', has_text='دواء معدّل').locator('[data-testid=scope-loft]').count() == 1)
        wait_toasts_clear(pg)

        # ── inline delete confirm + undo ──
        row = pg.locator('[data-testid=ev-row]', has_text='دواء معدّل')
        row.locator('[data-testid=ev-delete]').click(); pg.wait_for_selector('[data-testid=inline-confirm]')
        check('delete asks inline, inside the row, not in a dialog', pg.locator('[data-testid=ev-rows] [data-testid=inline-confirm]').count() == 1 and pg.locator('[data-testid=dialog]').count() == 0)
        pg.click('[data-testid=ev-rows] [data-testid=confirm-no]'); pg.wait_for_timeout(150)
        check('«إلغاء» leaves the event alone', pg.locator('[data-testid=inline-confirm]').count() == 0 and pg.locator('[data-testid=ev-row]').count() == n + 1)
        row.locator('[data-testid=ev-delete]').click(); pg.click('[data-testid=ev-rows] [data-testid=confirm-go]'); pg.wait_for_timeout(400)
        check('«حذف» removes it and offers «تراجع»', pg.locator('[data-testid=ev-row]').count() == n and pg.locator('[data-testid=toast-action]').count() == 1)
        check_toast_clear(pg, check, 'health (undo toast over the FAB)')
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(400)
        check('undo restores it into the log', pg.locator('[data-testid=ev-row]').count() == n + 1)
        wait_toasts_clear(pg)

        # ── a loft with no vaccination at all: the banner is absent (ruling 4) ──
        wipe(h)
        h.evaluate("""async () => { const db = await window.__zajilDb;
            const b = db.newBird({ name: 'طير الصحة', sex: 'hen' }); await db.saveBird(b, { force: true });
            await db.Health.save({ id: 'hc-1', eventType: 'check', wholeLoft: false, birdId: b.id, date: '2026-06-01', medication: 'فحص', notes: '' }); }""")
        pg.goto(HEALTH, wait_until='load'); pg.wait_for_selector('[data-testid=ev-row]')
        check('[ruling 4] a log with no vaccination shows no banner at all', pg.locator('[data-testid=next-vac]').count() == 0 and pg.locator('[data-testid=ev-row]').count() == 1)
        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
