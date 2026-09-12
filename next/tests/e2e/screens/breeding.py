#!/usr/bin/env python3
"""Breeding (/breeding → /pair?id=) — intent list re-authored from core_flows,
example_data, teaching_loft, change_events, ownership (as they apply) plus
every state breeding-v1 designs (list / detail / empty / new / errors / link /
blocked / ring / warnings). Binds to data-testid only. Seeds through the layer
on the harness route, then exercises the real screens. Provisions its own
server (R6)."""
import os, re, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance, check_toast_clear, scroll_to_bottom, wait_toasts_clear
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'breeding')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
LIST = f'{ROOT}breeding.html'
def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }"); return pg
def wipe(pg):
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const p of [...db.state.pairs.values()]) await db.Pairs.remove(p.id);
        for (const b of db.allBirds()) await db.deleteBird(b.id); }""")
def load(pg, file):
    pg.evaluate("async (f) => { const db = await window.__zajilDb; await db.importAll(await (await fetch(f)).json(), 'merge'); }", file)
def shots(pg, name):
    for w in (430, 900, 1400):
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 430, 'height': 900})

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        h = boot(ctx); wipe(h)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

        # ── EMPTY (spec data-v="empty") ──
        pg.goto(LIST, wait_until='load'); pg.wait_for_selector('[data-testid=season-row]', timeout=6000)
        check('empty season: «لا أزواج في هذا الموسم بعد.» + body, FAB «زوج جديد», season select = this year', 'لا أزواج' in pg.locator('[data-testid=empty-state]').inner_text() and pg.locator('[data-testid=new-pair-fab]').inner_text().strip() == 'زوج جديد' and pg.locator('[data-testid=season-select]').input_value() == '2026')
        shots(pg, 'empty')

        # ── LIST on the sample data (core_flows#8 / example_data#12: 2026 has 3 pairs) ──
        load(h, './sample-data.json')
        pg.goto(LIST, wait_until='load'); pg.wait_for_selector('[data-testid=pair-row]', timeout=6000)
        n26 = h.evaluate("() => [...window.__zajilDb.state.pairs.values()].filter(p => p.season === '2026').length")
        check('[core_flows#8 / example_data#12] breeding 2026 lists the season\'s pairs (3)', pg.locator('[data-testid=pair-row]').count() == n26 == 3, f'{pg.locator("[data-testid=pair-row]").count()} rows')
        check('count line «n أزواج · m نشط», rows sorted by nest, each with names / plates / nest chip / status / summary', pg.locator('[data-testid=count-line]').inner_text().startswith('3') and pg.locator('[data-testid=pair-row] [data-testid=pair-status]').count() == 3)
        opts = pg.locator('[data-testid=season-select] option').all_inner_texts()
        check('season select = current year ∪ seasons on record, newest first', opts == sorted(set(opts), reverse=True) and '2023' in opts and '2026' in opts, opts)
        pg.select_option('[data-testid=season-select]', '2023'); pg.wait_for_timeout(200)
        check('switching the season filters the list', pg.locator('[data-testid=pair-row]').count() == 1)
        pg.select_option('[data-testid=season-select]', '2026'); pg.wait_for_timeout(200)
        shots(pg, 'list')
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(150)
        check('desktop: the table (الزوج · العش · الحالة · التقدم) replaces the rows', pg.locator('[data-testid=pair-table]').is_visible() and pg.locator('[data-testid=pair-tr]').count() == 3 and not pg.locator('[data-testid=pair-rows]').is_visible())
        pg.set_viewport_size({'width': 430, 'height': 900})

        # ── DETAIL: the mid-cycle pair (example_data#13: hatch buttons) ──
        mid = h.evaluate("() => { const p = [...window.__zajilDb.state.pairs.values()].find(p => (p.rounds||[]).some(r => (r.eggs||[]).some(e => e.state === 'laid'))); return p && p.id; }")
        pg.click('[data-testid=pair-row] >> nth=0'); pg.wait_for_url(re.compile(r'/pair'), timeout=6000); pg.wait_for_selector('[data-testid=pair-card]')
        check('row → /pair?id= with the back link «الأزواج · موسم 2026» and the parents as links', '/pair' in pg.url and 'الأزواج' in pg.locator('[data-testid=back-link]').inner_text() and pg.locator('[data-testid=parent-sire]').get_attribute('href').startswith('/bird?id='))
        pg.goto(f'{ROOT}pair.html?id={mid}', wait_until='load'); pg.wait_for_selector('[data-testid=pair-card]')
        check('[example_data#13] the mid-cycle pair shows «تسجيل الفقس» / «لم تفقس» on its laid eggs', pg.locator('[data-testid=egg-hatch]').count() >= 1 and pg.locator('[data-testid=egg-fail]').count() >= 1)
        check('the newest round starts open, older rounds collapsed', pg.locator('[data-testid=round]').last.get_attribute('data-open') == '1')
        shots(pg, 'detail')
        # ── [ownership#6–7] link an existing bird on an unringed hatched egg ──
        unringed = h.evaluate("() => { for (const p of window.__zajilDb.state.pairs.values()) for (const r of p.rounds||[]) for (const e of r.eggs||[]) if (e.state === 'hatched' && !e.chickId) return p.id; return null; }")
        if not unringed:   # make one: hatch a laid egg on the mid-cycle pair
            pg.click('[data-testid=egg-hatch] >> nth=0'); pg.wait_for_timeout(300); unringed = mid
        pg.goto(f'{ROOT}pair.html?id={unringed}', wait_until='load'); pg.wait_for_selector('[data-testid=egg-link]')
        check('[ownership#6] «ربط طير مسجَّل» offered on an unringed hatched egg (and «تركيب الحلقة»)', pg.locator('[data-testid=egg-link]').count() >= 1 and pg.locator('[data-testid=egg-ring]').count() >= 1)
        pg.click('[data-testid=egg-link] >> nth=0'); pg.wait_for_selector('[data-testid=sheet-link]')
        # a bird linked to another egg this season → the spec's blocked state
        linked = h.evaluate("(pid) => { const db = window.__zajilDb; const me = db.state.pairs.get(pid); for (const p of db.state.pairs.values()) if (p.season === me.season) for (const r of p.rounds||[]) for (const e of r.eggs||[]) if (e.chickId) return db.getBird(e.chickId).name; return null; }", unringed)
        if linked:
            pg.click('[data-testid=f-link-btn]'); pg.fill('[data-testid=f-link-input]', linked); pg.wait_for_timeout(150); pg.click('[data-testid=f-link-item] >> nth=0'); pg.wait_for_timeout(150)
            check('[spec «ربط ممنوع»] a bird already linked to an egg this season is blocked with a reason, confirm disabled', 'لا يمكن الربط' in pg.locator('[data-testid=link-blocked]').inner_text() and pg.locator('[data-testid=sheet-save]').is_disabled())
        free = h.evaluate("(pid) => { const db = window.__zajilDb; const me = db.state.pairs.get(pid); const used = new Set(); for (const p of db.state.pairs.values()) for (const r of p.rounds||[]) for (const e of r.eggs||[]) if (e.chickId) used.add(e.chickId); const b = db.allBirds().find(x => !used.has(x.id) && x.id !== me.sireId && x.id !== me.damId && !x.sireId && !x.damId && x.name && !x.external); return b && b.name; }", unringed)
        pg.click('[data-testid=f-link-btn]'); pg.fill('[data-testid=f-link-input]', free); pg.wait_for_timeout(150); pg.click('[data-testid=f-link-item] >> nth=0'); pg.wait_for_timeout(150)
        ok_link = not pg.locator('[data-testid=link-blocked]').count()
        if ok_link:
            pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(500)
            got = h.evaluate("(pid) => { const db = window.__zajilDb; const me = db.state.pairs.get(pid); const e = (me.rounds||[]).flatMap(r => r.eggs||[]).find(e => e.chickId); const c = e && db.getBird(e.chickId); return c && [c.sireId === me.sireId, c.damId === me.damId]; }", unringed)
            check('[ownership#7] linking succeeds: the egg carries the chick and the bird\'s parents are set to this pair', got == [True, True] and pg.locator('[data-testid=egg-chick]').count() >= 1, got)
        else:
            check('[ownership#7] linking either succeeds or explains why', 'لا يمكن الربط' in pg.locator('[data-testid=link-blocked]').inner_text())
            pg.click('[data-testid=sheet-cancel]')

        # ── NEW PAIR: errors, then success with the kin box (spec data-v="new" / "newerr") ──
        pg.goto(LIST, wait_until='load'); pg.wait_for_selector('[data-testid=pair-row]')
        pg.click('[data-testid=new-pair-fab]'); pg.wait_for_selector('[data-testid=sheet-new]')
        check('[ownership#4] the pair sheet exposes pairing + acquired dates and acquired-from', pg.locator('[data-testid=f-mated]').count() == 1 and pg.locator('[data-testid=f-bought]').count() == 1 and pg.locator('[data-testid=f-source]').count() == 1)
        check('kin box waits for both parents', 'تنبيه القرابة' in pg.locator('[data-testid=kin]').inner_text())
        # [picker_duplicates#4/#6] the create offer follows the same rules here as on the form — while nothing is picked yet
        used_ring = h.evaluate("() => { const b = window.__zajilDb.allBirds().find(x => (x.rings||[]).length && x.sex === 'hen'); return b && b.rings[0].raw; }")
        pg.click('[data-testid=f-dam-btn]'); pg.fill('[data-testid=f-dam-input]', used_ring); pg.wait_for_timeout(200)
        check('[picker_duplicates#4] an existing ring typed by hand resolves to that bird — no create offer', pg.locator('[data-testid=f-dam-create]').count() == 0 and pg.locator('[data-testid=f-dam-item]').count() >= 1, used_ring)
        pg.fill('[data-testid=f-dam-input]', 'JO-2099-55555'); pg.wait_for_timeout(200)
        check('[picker_duplicates#6] …but a genuinely new ring still offers it, so backfill stays possible', pg.locator('[data-testid=f-dam-create]').count() == 1)
        pg.fill('[data-testid=f-dam-input]', ''); pg.wait_for_timeout(150); pg.click('[data-testid=sheet-new] h2'); pg.wait_for_timeout(200)
        pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(150)
        errs_txt = pg.locator('[data-testid=new-errs]').inner_text()
        check('[spec «أخطاء»] saving empty → «لم يُحفظ الزوج» listing sire / dam / nest', 'لم يُحفظ الزوج' in errs_txt and 'اختر الأب' in errs_txt and 'اختر الأم' in errs_txt and 'رقم العش' in errs_txt)
        sibs = h.evaluate("() => { const db = window.__zajilDb; const bs = db.allBirds(); for (const a of bs) for (const c of bs) if (a.id !== c.id && a.sireId && a.damId && a.sireId === c.sireId && a.damId === c.damId && a.sex === 'cock' && c.sex === 'hen') return [a.name, c.name]; return null; }")
        pg.click('[data-testid=f-sire-btn]'); pg.fill('[data-testid=f-sire-input]', sibs[0]); pg.wait_for_timeout(150); pg.click('[data-testid=f-sire-item] >> nth=0')
        pg.click('[data-testid=f-dam-btn]'); pg.fill('[data-testid=f-dam-input]', sibs[1]); pg.wait_for_timeout(150); pg.click('[data-testid=f-dam-item] >> nth=0'); pg.wait_for_timeout(150)
        check('[teaching_loft#6 on the pair sheet] full siblings → kin box «أشقاء», COI 25%, severe', 'أشقاء' in pg.locator('[data-testid=kin-title]').inner_text() and pg.locator('[data-testid=kin-box]').get_attribute('data-level') == 'severe' and pg.locator('[data-testid=kin-box] [data-testid=coi-badge]').inner_text().startswith('25'))
        # ── [picker_guards#7–8] a refused save keeps the sheet up, and no stale pair is written ──
        n_pairs = h.evaluate("() => window.__zajilDb.state.pairs.size")
        pg.click('[data-testid=f-dam-btn]'); pg.fill('[data-testid=f-dam-input]', 'xyz-nonexistent'); pg.wait_for_timeout(200)
        check('[picker_guards#7] a query that matches nothing offers no candidate to pick by accident', pg.locator('[data-testid=f-dam-item]').count() == 0)
        pg.click('[data-testid=sheet-new] h2'); pg.wait_for_timeout(150)
        check('[picker_guards#7] …and abandoning that search leaves the committed dam in place (the port has no way to blank it by typing)', 'اختر أنثى' not in pg.locator('[data-testid=f-dam-btn]').inner_text())
        check('[picker_guards#8] the sheet is still open for correction, and nothing was written', pg.locator('[data-testid=sheet-new]').count() == 1 and h.evaluate("() => window.__zajilDb.state.pairs.size") == n_pairs)
        busy = h.evaluate("() => { const p = [...window.__zajilDb.state.pairs.values()].find(p => p.season === '2026' && p.status === 'active' && p.nestBox); return p.nestBox; }")
        pg.fill('[data-testid=f-nest]', busy); pg.click('[data-testid=sheet-save]'); pg.wait_for_timeout(150)
        check('[spec «أخطاء»] a nest taken by an active pair this season is refused', 'مشغول' in pg.locator('[data-testid=new-errs]').inner_text())
        pg.fill('[data-testid=f-nest]', '99'); pg.fill('[data-testid=f-source]', 'لوفت الاختبار'); pg.screenshot(path=f'{FID}/new-pair-430.png', full_page=True)
        n0 = h.evaluate("() => window.__zajilDb.state.pairs.size")
        pg.click('[data-testid=sheet-save]'); pg.wait_for_url(re.compile(r'/pair'), timeout=6000); pg.wait_for_selector('[data-testid=pair-card]')
        newp = pg.evaluate("() => { const p = [...window.__zajilDb.state.pairs.values()].find(p => p.nestBox === '99'); return p && [p.season, p.status, p.acquiredFrom, (p.rounds||[]).length]; }")
        check('saving lands on the new pair: season 2026, active, source kept, no rounds', newp == ['2026', 'active', 'لوفت الاختبار', 0] and 'مشترى' in pg.locator('[data-testid=pair-card]').inner_text(), newp)
        # ── rounds and eggs: add round → add egg → hatch → ring the chick → wean; dates edit; delete egg / round with undo ──
        pg.click('[data-testid=add-round]'); pg.wait_for_selector('[data-testid=round]')
        check('«بطن جديد» adds an open round «البطن 1» with «بلا بيض»', pg.locator('[data-testid=round]').count() == 1 and pg.locator('[data-testid=round]').get_attribute('data-open') == '1' and 'بلا بيض' in pg.locator('[data-testid=round-toggle]').inner_text())
        pg.click('[data-testid=add-egg]'); pg.wait_for_selector('[data-testid=egg]')
        check('«إضافة بيضة» → a laid egg dated today with «تسجيل الفقس» / «لم تفقس»', pg.locator('[data-testid=egg][data-state=laid]').count() == 1 and pg.locator('[data-testid=egg-laidDate]').input_value() != '' and pg.locator('[data-testid=egg-hatch]').count() == 1)
        pg.click('[data-testid=add-egg]'); pg.wait_for_timeout(200); pg.click('[data-testid=egg-fail] >> nth=1'); pg.wait_for_timeout(200)
        check('a second egg marked «لم تفقس»; the round summary counts it', pg.locator('[data-testid=egg][data-state=failed]').count() == 1 and 'لم تفقس' in pg.locator('[data-testid=round-toggle]').inner_text())
        pg.click('[data-testid=egg-hatch] >> nth=0'); pg.wait_for_selector('[data-testid=egg-ring]')
        check('«تسجيل الفقس» → hatched today: «فقس:» date + «تركيب الحلقة» / «ربط طير مسجَّل»; the pair stat «1 من 2 فقست»', pg.locator('[data-testid=egg-hatchDate]').input_value() != '' and pg.locator('[data-testid=egg-link]').count() == 1 and 'من' in pg.locator('[data-testid=pair-stat]').inner_text())
        pg.click('[data-testid=egg-ring]'); pg.wait_for_selector('[data-testid=sheet-ring]')
        check('ring sheet: context line «فرخ … × … · البطن 1 · فقس …», save disabled without a ring', 'البطن' in pg.locator('[data-testid=sheet-ring]').inner_text() and pg.locator('[data-testid=sheet-save]').is_disabled())
        used = h.evaluate("() => { const b = window.__zajilDb.allBirds().find(x => (x.rings||[]).length); return b.rings[0].raw; }")
        pg.fill('[data-testid=f-ring]', used); pg.wait_for_timeout(150)
        check('[spec «تحذيرات»] a used ring → warnings alert, button becomes «حفظ رغم التحذير»', pg.locator('[data-testid=ring-warn]').count() == 1 and pg.locator('[data-testid=sheet-save]').inner_text().strip() == 'حفظ رغم التحذير')
        pg.fill('[data-testid=f-ring]', 'JO-2025-77001'); pg.wait_for_timeout(150)
        check('[spec «تحذيرات»] ring year ≠ hatch year → the year warning', 'سنة الحلقة' in pg.locator('[data-testid=ring-warn]').inner_text())
        pg.fill('[data-testid=f-ring]', 'JO-2026-77001'); pg.fill('[data-testid=f-name]', 'فرخ الاختبار'); pg.click('[data-testid=f-sex][data-sex=cock]'); pg.wait_for_timeout(100)
        check('a clean ring: no warnings, button «حفظ وربط بالبيضة»', pg.locator('[data-testid=ring-warn]').count() == 0 and pg.locator('[data-testid=sheet-save]').inner_text().strip() == 'حفظ وربط بالبيضة')
        pg.click('[data-testid=sheet-save]'); pg.wait_for_selector('[data-testid=egg-chick]', timeout=6000)
        chick = pg.evaluate("() => { const db = window.__zajilDb; const c = db.allBirds().find(x => x.name === 'فرخ الاختبار'); const p = [...db.state.pairs.values()].find(p => p.nestBox === '99'); return c && [c.status, c.sireId === p.sireId, c.damId === p.damId, c.hatchDate !== '', c.strain === (db.getBird(p.sireId).strain || ''), (p.rounds[0].eggs[0].chickId === c.id), p.rounds[0].eggs[0].ringed]; }")
        # two toasts may be stacked here (the pair's «تم الحفظ» is still up) — the chick's is the newest
        check('ringing creates the chick (young bird, parents = the pair, hatch date from the egg, sire\'s strain) and links the egg', chick == [ 'young bird', True, True, True, True, True, True ] and 'أُنشئ سجل الفرخ' in pg.locator('[data-testid=toast]').last.inner_text(), chick)
        check('the linked chick shows with its plate and «فطام»; offspring block lists it', pg.locator('[data-testid=egg-wean]').count() == 1 and pg.locator('[data-testid=offspring-pill]').count() >= 1)
        pg.click('[data-testid=egg-wean]'); pg.wait_for_selector('[data-testid=egg-weaned]')
        pg.click('[data-testid=egg-more] >> nth=0'); pg.wait_for_selector('[data-testid=egg-menu]')
        check('«فطام» → «مفطوم» chip; the ⋯ menu offers «إلغاء الربط», a labelled «تاريخ الفطام», «حذف البيضة»', pg.locator('[data-testid=egg-unlink]').count() == 1 and pg.locator('[data-testid=egg-weanDate]').input_value() != '' and pg.locator('[data-testid=egg-delete]').count() == 1)
        pg.fill('[data-testid=egg-hatchDate]', '2026-03-05'); pg.locator('[data-testid=egg-hatchDate]').dispatch_event('change'); pg.wait_for_timeout(300)
        check('editing the hatch date also corrects the chick\'s record', pg.evaluate("() => window.__zajilDb.allBirds().find(x => x.name === 'فرخ الاختبار').hatchDate") == '2026-03-05')
        shots(pg, 'detail-full')
        wait_toasts_clear(pg)   # measure the delete's own toast, not the ring/save toasts still expiring behind it
        pg.click('[data-testid=egg-more] >> nth=1'); pg.click('[data-testid=egg-delete]'); pg.wait_for_selector('[data-testid=inline-confirm]')
        check('[spec] «حذف البيضة» → inline «تأكيد الحذف؟»', pg.locator('[data-testid=inline-confirm]').count() == 1)
        pg.click('[data-testid=confirm-go]'); pg.wait_for_timeout(300)
        check('…deletes the egg; the toast offers «تراجع»', pg.locator('[data-testid=egg]').count() == 1 and pg.locator('[data-testid=toast-action]').count() == 1)
        # [ruling C] the undo toast on the pair detail, where the tab bar is the only bottom chrome
        check_toast_clear(pg, check, 'pair detail (undo toast)')
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(300)
        check('…undo puts it back', pg.locator('[data-testid=egg]').count() == 2)
        pg.wait_for_timeout(4500)
        pg.click('[data-testid=round-delete]'); pg.click('[data-testid=confirm-go]'); pg.wait_for_timeout(300)
        check('[spec] «حذف البطن» with confirm → round gone, undo offered', pg.locator('[data-testid=round]').count() == 0 and pg.locator('[data-testid=toast-action]').count() == 1)
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(300)
        check('…undo restores the round with both eggs', pg.locator('[data-testid=round]').count() == 1 and pg.locator('[data-testid=egg]').count() == 2)
        pg.wait_for_timeout(4500)
        pg.click('[data-testid=pair-toggle]'); pg.wait_for_timeout(200)
        check('«مفصول» separates the pair (status chip, card off)', pg.locator('[data-testid=pair-card]').get_attribute('data-status') == 'separated' and pg.locator('[data-testid=pair-card] [data-testid=pair-status]').inner_text().strip() == 'مفصول')
        pg.click('[data-testid=pair-delete]'); pg.click('[data-testid=confirm-go]'); pg.wait_for_url(re.compile(r'/breeding'), timeout=6000); pg.wait_for_selector('[data-testid=pair-row]')
        # the list shows the 2026 season only: its 3 original pairs + the one just created (n0 counted every season)
        check('deleting the pair → back to the list without it, undo offered', pg.locator('[data-testid=pair-row]').count() == n26 and pg.locator('[data-testid=toast-action]').count() == 1, f'{pg.locator("[data-testid=pair-row]").count()} rows, {pg.locator("[data-testid=toast-action]").count()} undo')
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(400)
        check('…undo restores the pair into the list', pg.locator('[data-testid=pair-row]').count() == n26 + 1, pg.locator('[data-testid=pair-row]').count())
        # ── [change_events#2] a change event while the sheet is open: the sheet survives and the page does not move ──
        pg.evaluate('window.scrollTo(0, 300)'); pg.wait_for_timeout(200); y0 = pg.evaluate('window.scrollY')
        pg.click('[data-testid=new-pair-fab]'); pg.wait_for_selector('[data-testid=sheet-new]')
        pg.evaluate("async () => { const db = window.__zajilDb; await db.saveBird(db.newBird({ name: 'أثناء الحوار', sex: 'hen' })); }"); pg.wait_for_timeout(500)
        check('[change_events#2] the sheet SURVIVES a change event fired while it is open', pg.locator('[data-testid=sheet-new]').count() == 1)
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
        check('[change_events#2] Escape closes it and the page did NOT move', pg.locator('[data-testid=sheet-new]').count() == 0 and abs(pg.evaluate('window.scrollY') - y0) < 60, f"{y0} -> {pg.evaluate('window.scrollY')}")
        # ── teaching loft: 2026 shows its pairs (teaching_loft#9) ──
        wipe(h); load(h, './example-loft-large.json')
        nl = h.evaluate("() => [...window.__zajilDb.state.pairs.values()].filter(p => p.season === '2026').length")
        pg.goto(LIST, wait_until='load'); pg.wait_for_selector('[data-testid=pair-row]')
        check(f'[teaching_loft#9] 2026 breeding shows the teaching loft\'s pairs ({nl})', pg.locator('[data-testid=pair-row]').count() == nl == 3)
        check_clearance(pg, check, 'breeding list')
        pid = pg.evaluate("() => [...window.__zajilDb.state.pairs.values()].find(p => p.season === '2026').id")
        pg.goto(f'{ROOT}pair.html?id={pid}', wait_until='load'); pg.wait_for_selector('[data-testid=pair-card]')
        check_clearance(pg, check, 'pair detail')
        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
