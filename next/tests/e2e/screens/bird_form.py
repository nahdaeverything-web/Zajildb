#!/usr/bin/env python3
"""Add / edit bird (/bird/new, /bird/edit?id=) — intent list re-authored from
record_factory, ownership, data_loss, example_data (as they apply) plus the
states add-edit-bird-v2 designs and the shared-states validation dialogs.
Binds to data-testid only. Seeds through the layer on the harness route, then
exercises the real screen. Provisions its own server (R6)."""
import os, re, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'bird-form')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
NEW = f'{ROOT}bird/new.html'
def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }"); return pg
def wipe(pg):
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const b of db.allBirds()) await db.deleteBird(b.id); }""")
def snap(pg, expr, arg=None):  # read the layer from the page under test (its own mirror)
    return pg.evaluate(expr, arg)

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        h = boot(ctx); wipe(h)
        h.evaluate("async () => { const db = await window.__zajilDb; await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge'); }")
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

        # ── the empty form (spec: new) ──
        pg.goto(NEW, wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]', timeout=6000)
        check('new form: title «طير جديد» (vanilla act.newBird wins — ruling 14), loft · season line', pg.locator('[data-testid=form-title]').inner_text().strip() == 'طير جديد' and 'موسم' in pg.locator('header').inner_text())
        check('no tab bar on the form (modal flow); the fixed action bar has إلغاء / حفظ وإضافة آخر / حفظ', pg.evaluate("() => ![...document.querySelectorAll('nav')].some(n => /tabbar/.test(n.className) && getComputedStyle(n).display !== 'none')") and pg.locator('[data-testid=save-btn]').inner_text().strip() == 'حفظ' and pg.locator('[data-testid=save-new-btn]').count() == 1)
        check('sex segment ذكر · أنثى · غير معروف, «غير معروف» pressed by default', [x.strip() for x in pg.locator('[data-testid=sex-btn]').all_inner_texts()] == ['ذكر', 'أنثى', 'غير معروف'] and pg.locator('[data-testid=sex-btn][data-sex=unknown]').get_attribute('aria-pressed') == 'true')
        n_st = snap(pg, "() => window.__zajilDb.loftStatuses().length")
        check('status chips = the loft\'s statuses (vanilla loftStatuses), «نشط» not among them', pg.locator('[data-testid=status-chip]').count() == n_st and 'نشط' not in pg.locator('[data-testid=f-status]').inner_text())
        check('[ownership#1] the ownership control is present (external switch, off)', pg.locator('[data-testid=external-switch]').get_attribute('aria-checked') == 'false')
        check('[ownership#2] status visible for an owned bird', pg.locator('[data-testid=f-status]').is_visible())
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/new-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        pg.click('[data-testid=external-switch]'); pg.wait_for_timeout(100)
        check('[ownership#3] status hidden for an external bird', pg.locator('[data-testid=f-status]').count() == 0)
        pg.screenshot(path=f'{FID}/new-external-430.png', full_page=True)
        # ── [record_factory#1 path 1] the switch → an external bird with REFERENCE_STATUS ──
        pg.fill('[data-testid=ring-input] >> nth=0', 'BE-2001-9000001'); pg.click('[data-testid=save-btn]')
        pg.wait_for_url(re.compile(r'/bird\?id='), timeout=6000); pg.wait_for_selector('[data-testid=profile-hero]')
        ext1 = snap(pg, "() => { const b = window.__zajilDb.allBirds().find(x => (x.rings||[]).some(r => r.raw === 'BE-2001-9000001')); return b && [b.external, b.status]; }")
        check('[ownership#4 / record_factory#1] saved as external with reference status, landed on the profile', ext1 == [True, 'reference'], ext1)
        # ── [record_factory#1 path 2] the picker's quick create → external + reference ──
        pg.goto(NEW, wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        pg.click('[data-testid=parent-sire-create]'); pg.fill('[data-testid=picker-input]', 'BE-2001-9000002'); pg.click('[data-testid=picker-create]'); pg.wait_for_timeout(500)
        ext2 = snap(pg, "() => { const b = window.__zajilDb.allBirds().find(x => (x.rings||[]).some(r => r.raw === 'BE-2001-9000002')); return b && [b.external, b.status, b.sex]; }")
        check('[record_factory#1] quick-create mints an external cock with reference status and fills the slot', ext2 == [True, 'reference', 'cock'] and pg.locator('[data-testid=parent-sire]').count() == 1, ext2)
        # ── [example_data#4] pick flow: list opens, closes after pick, closes on outside click ──
        pg.click('[data-testid=parent-dam-pick]'); pg.wait_for_timeout(150)
        # vanilla's dam filter excludes cocks only (bird-form.js:98) — unknown-sex birds stay eligible
        check('[example_data#4] «اختيار من اللوفت» opens the candidate list (no cocks)', pg.locator('[data-testid=picker-dam] [data-testid=picker-item]').count() > 0 and 'cock' not in pg.locator('[data-testid=picker-dam] [data-sex]').evaluate_all('els => els.map(e => e.dataset.sex)'))
        pg.click('[data-testid=picker-item] >> nth=0'); pg.wait_for_timeout(150)
        check('[example_data#4] the list CLOSES after a pick and the slot shows the dam', pg.locator('[data-testid=picker-dam]').count() == 0 and pg.locator('[data-testid=parent-dam]').count() == 1)
        pg.click('[data-testid=parent-dam-change]'); pg.wait_for_timeout(100); pg.click('[data-testid=form-title]'); pg.wait_for_timeout(150)
        check('[example_data#4] the list closes on an outside click', pg.locator('[data-testid=picker-dam]').count() == 0)
        # ── [example_data#7–8] ?sire=&dam= prefill ──
        pair = snap(pg, "() => { const db = window.__zajilDb; const b = db.allBirds().find(x => x.sireId && x.damId); return [b.sireId, b.damId, db.getBird(b.sireId).name, db.getBird(b.damId).name]; }")
        pg.goto(f"{NEW}?sire={pair[0]}&dam={pair[1]}", wait_until='load'); pg.wait_for_selector('[data-testid=parent-sire]')
        check('[example_data#7–8] sire + dam prefilled from the query', pair[2] in pg.locator('[data-testid=parent-sire-name]').inner_text() and pair[3] in pg.locator('[data-testid=parent-dam-name]').inner_text())
        # ── [record_factory#2–5] the deferred sibling intent ──
        # the harness tab's mirror is its own: re-read it after the birds this test created in the other tab
        h.reload(wait_until='load'); h.wait_for_timeout(500); h.evaluate("async () => { await window.__zajilReady; }")
        target = h.evaluate("async () => { const db = await window.__zajilDb; const b = await db.saveBird(db.newBird({ name: 'بلا أبوين', sex: 'hen' })); return b.id; }")
        before = h.evaluate("(id) => { const db = window.__zajilDb; const b = db.getBird(id); return [b.sireId, b.damId, db.allBirds().length]; }", target)
        pg.goto(f"{NEW}?siblingOf={target}", wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        check('[record_factory#3] a notice explains what will happen on save', pg.locator('[data-testid=sibling-notice]').count() == 1 and 'بلا أبوين' in pg.locator('[data-testid=sibling-notice]').inner_text())
        pg.goto(f'{ROOT}birds.html', wait_until='load'); pg.wait_for_timeout(500)   # ABANDON
        h.reload(wait_until='load'); h.wait_for_timeout(500); h.evaluate("async () => { await window.__zajilReady; }")
        after = h.evaluate("(id) => { const db = window.__zajilDb; const b = db.getBird(id); return [b.sireId, b.damId, db.allBirds().length]; }", target)
        check('[record_factory#4] abandoning leaves the original untouched and creates no placeholders', after == before, f'{before} -> {after}')
        pg.goto(f"{NEW}?siblingOf={target}", wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        pg.fill('[data-testid=ring-input] >> nth=0', 'JO-2026-8800001'); pg.click('[data-testid=save-btn]')
        pg.wait_for_url(re.compile(r'/bird\?id='), timeout=6000); pg.wait_for_selector('[data-testid=profile-hero]')
        done = snap(pg, """(id) => { const db = window.__zajilDb, e = window.__zajilEngine; const orig = db.getBird(id); const sib = db.allBirds().find(b => (b.rings||[]).some(r => r.raw === 'JO-2026-8800001'));
            return { origS: orig.sireId, origD: orig.damId, sibS: sib && sib.sireId, sibD: sib && sib.damId, dangling: e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents }).length }; }""", target)
        check('[record_factory#5] completing it links BOTH birds to the same placeholder parents', bool(done['origS']) and done['origS'] == done['sibS'] and done['origD'] == done['sibD'], done)
        check('[record_factory#6] and leaves the database referentially clean', done['dangling'] == 0, done['dangling'])
        # ── [data_loss#1, #3] abandoning a search keeps the parent; explicit clear detaches ──
        child = snap(pg, "() => { const b = window.__zajilDb.allBirds().find(x => x.sireId && x.damId && x.name); return [b.id, window.__zajilDb.getBird(b.sireId).name]; }")
        pg.goto(f'{ROOT}bird/edit.html?id={child[0]}', wait_until='load'); pg.wait_for_selector('[data-testid=parent-sire]')
        pg.click('[data-testid=parent-sire-change]'); pg.fill('[data-testid=picker-input]', 'xyz'); pg.wait_for_timeout(150); pg.click('[data-testid=form-title]'); pg.wait_for_timeout(200)
        check('[data_loss#1] the slot still shows the real sire after abandoning a search', child[1] in pg.locator('[data-testid=parent-sire-name]').inner_text())
        b4 = snap(pg, "(id) => { const b = window.__zajilDb.getBird(id); return [b.sireId, b.damId]; }", child[0])
        pg.click('[data-testid=save-btn]'); pg.wait_for_url(re.compile(r'/bird\?id='), timeout=6000)
        check('[data_loss#2] parent links survive the save', snap(pg, "(id) => { const b = window.__zajilDb.getBird(id); return [b.sireId, b.damId]; }", child[0]) == b4)
        pg.goto(f'{ROOT}bird/edit.html?id={child[0]}', wait_until='load'); pg.wait_for_selector('[data-testid=parent-sire]')
        pg.click('[data-testid=parent-sire-clear]'); pg.wait_for_timeout(100)
        check('[data_loss#3] explicit «إزالة» empties the slot', pg.locator('[data-testid=parent-sire-empty]').count() == 1)
        pg.click('[data-testid=save-btn]'); pg.wait_for_url(re.compile(r'/bird\?id='), timeout=6000)
        check('[data_loss#3] …and the save detaches the sire', snap(pg, "(id) => window.__zajilDb.getBird(id).sireId", child[0]) is None)
        h.evaluate("async (arg) => { const db = await window.__zajilDb; await new Promise(r => setTimeout(r, 200)); }", 0)
        # ── validation: a cycle is an ERROR → shared-states error dialog + the slot marked ──
        fam = snap(pg, "() => { const db = window.__zajilDb; for (const b of db.allBirds()) { const kid = db.allBirds().find(k => k.sireId === b.id && k.sex !== 'hen' && k.name); if (kid) return [b.id, kid.name]; } return null; }")
        pg.goto(f'{ROOT}bird/edit.html?id={fam[0]}', wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        if pg.locator('[data-testid=parent-sire]').count(): pg.click('[data-testid=parent-sire-change]')
        else: pg.click('[data-testid=parent-sire-pick]')
        pg.fill('[data-testid=picker-input]', fam[1]); pg.wait_for_timeout(150); pg.click('[data-testid=picker-item] >> nth=0'); pg.wait_for_timeout(100)
        pg.click('[data-testid=save-btn]'); pg.wait_for_timeout(300)
        dlg = pg.locator('[data-testid=dialog]').inner_text()
        check('cycle (own offspring as sire) → «لا يمكن الحفظ» dialog listing the engine\'s reason', 'لا يمكن الحفظ' in dlg and 'حلقة نسب' in dlg, dlg.replace('\n', ' ')[:100])
        pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(100)
        check('…and the sire slot carries the error message (role=alert)', pg.locator('[data-testid=slot-sire] [role=alert]').count() == 1)
        # ── duplicate ring: live warnbox (spec) → warnings dialog on save (shared-states) → saved anyway ──
        used = snap(pg, "() => { const b = window.__zajilDb.allBirds().find(x => (x.rings||[]).length && x.name); return [b.rings[0].raw, b.name]; }")
        pg.goto(NEW, wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        pg.fill('[data-testid=ring-input] >> nth=0', used[0]); pg.wait_for_timeout(200)
        check('duplicate ring → live warnbox names the other bird with «عرض الطائر الآخر»', pg.locator('[data-testid=dup-warn]').count() == 1 and used[1] in pg.locator('[data-testid=dup-warn]').inner_text() and pg.locator('[data-testid=dup-view]').get_attribute('href').startswith('/bird?id='))
        pg.screenshot(path=f'{FID}/dup-warn-430.png', full_page=True)
        pg.click('[data-testid=save-btn]'); pg.wait_for_timeout(300)
        check('save → warnings dialog with «حفظ رغم التحذير»', 'تحذيرات' in pg.locator('[data-testid=dialog]').inner_text() and pg.locator('[data-testid=dialog-confirm]').inner_text().strip() == 'حفظ رغم التحذير')
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_url(re.compile(r'/bird\?id='), timeout=6000)
        check('…confirming saves the duplicate (allowWarnings) and lands on the profile', snap(pg, "(raw) => window.__zajilDb.allBirds().filter(x => (x.rings||[]).some(r => r.raw === raw)).length", used[0]) == 2)
        # ── hatch hint from the ring year; second ring row; save-and-new carry-over ──
        pg.goto(NEW, wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        pg.fill('[data-testid=ring-input] >> nth=0', 'JO-2024-77777'); pg.wait_for_timeout(150)
        check('hatch hint offers the ring year', pg.locator('[data-testid=hatch-hint]').inner_text().strip() == 'استخدام سنة الحلقة: 2024')
        pg.click('[data-testid=hatch-hint]'); pg.wait_for_timeout(100)
        check('…one tap sets 1 Jan of that year', pg.locator('[data-testid=f-hatch]').input_value() == '2024-01-01' and pg.locator('[data-testid=hatch-hint]').count() == 0)
        pg.click('[data-testid=ring-add]'); pg.fill('[data-testid=ring-input] >> nth=1', 'CLUB-77'); pg.select_option('[data-testid=ring-type]', 'club')
        pg.fill('[data-testid=f-name]', 'طائر الدفعة'); pg.fill('[data-testid=f-colour]', 'أزرق'); pg.fill('[data-testid=f-strain]', 'يانسن')
        pg.click('[data-testid=sex-btn][data-sex=cock]'); pg.click('[data-testid=status-chip][data-status=stock]')
        pg.locator('[data-testid=f-name]').press('Enter'); pg.wait_for_timeout(100)
        check('Enter in a field advances focus instead of saving', pg.evaluate("() => document.activeElement && document.activeElement.dataset.testid") != 'f-name' and pg.url.rstrip('/').endswith('new.html'))
        pg.click('[data-testid=save-new-btn]'); pg.wait_for_timeout(600)
        saved = snap(pg, "() => window.__zajilDb.allBirds().find(x => x.name === 'طائر الدفعة')")
        check('save-and-new: the bird is saved with both rings (types kept), the toast says «حُفظ … — أدخل التالي»', bool(saved) and len(saved['rings']) == 2 and saved['rings'][1]['type'] == 'club' and 'أدخل التالي' in pg.locator('[data-testid=toast]').inner_text())
        check('…the form resets carrying colour/strain/status/sex-less and the ring prefix JO-2024-', pg.locator('[data-testid=f-name]').input_value() == '' and pg.locator('[data-testid=f-colour]').input_value() == 'أزرق' and pg.locator('[data-testid=f-strain]').input_value() == 'يانسن' and pg.locator('[data-testid=ring-input] >> nth=0').input_value() == 'JO-2024-' and pg.locator('[data-testid=status-chip][data-status=stock]').get_attribute('aria-pressed') == 'true')
        check('…and focus sits in the ring field', pg.evaluate("() => document.activeElement && document.activeElement.dataset.testid") == 'ring-input')
        # ── edit: prefilled, a change persists, note appended ──
        pg.goto(f"{ROOT}bird/edit.html?id={saved['id']}", wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')
        check('edit form: title «تعديل», fields prefilled, no save-and-new', pg.locator('[data-testid=form-title]').inner_text().strip() == 'تعديل' and pg.locator('[data-testid=f-name]').input_value() == 'طائر الدفعة' and pg.locator('[data-testid=save-new-btn]').count() == 0)
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/edit-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        pg.fill('[data-testid=f-colour]', 'أحمر'); pg.fill('[data-testid=f-notes]', 'ملاحظة من النموذج'); pg.click('[data-testid=save-btn]')
        pg.wait_for_url(re.compile(r'/bird\?id='), timeout=6000); pg.wait_for_selector('[data-testid=profile-hero]')
        upd = snap(pg, "(id) => { const b = window.__zajilDb.getBird(id); return [b.colour, (b.notes||[]).length]; }", saved['id'])
        check('edit saves the change and appends the note through saveBird', upd == ['أحمر', 1], upd)
        check('cancel on the edit form returns to the profile', (pg.goto(f"{ROOT}bird/edit.html?id={saved['id']}", wait_until='load'), pg.wait_for_selector('[data-testid=cancel-btn]'), pg.click('[data-testid=cancel-btn]'), pg.wait_for_timeout(500))[0] is not None and ('/bird' in pg.url))
        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
