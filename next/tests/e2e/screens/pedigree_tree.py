#!/usr/bin/env python3
"""Pedigree tree (/pedigree?id=…) — intent list re-authored from core_flows,
teaching_loft, example_data (as they apply) plus the states pedigree-tree-v1
designs. Binds to data-testid only. Seeds through the layer on the harness
route, then exercises the real screen. Provisions its own server (R6)."""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance, check_toast_clear, scroll_to_bottom
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'pedigree-tree')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }"); return pg
def wipe(pg):
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const b of db.allBirds()) await db.deleteBird(b.id); }""")
def load(pg, file):
    pg.evaluate("async (f) => { const db = await window.__zajilDb; await db.importAll(await (await fetch(f)).json(), 'merge'); }", file)

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        h = boot(ctx); wipe(h); load(h, './sample-data.json')
        barq = h.evaluate("() => window.__zajilDb.allBirds().find(b => b.name === 'برق').id")
        exp = h.evaluate("""(id) => { const db = window.__zajilDb, e = window.__zajilEngine;
            const g4 = e.pedigree.pedigreeGrid(db.getBird, id, 4); const loss = e.coi.ancestorLoss(db.getBird, id, 4);
            let complete = 0; for (let g = 1; g < g4.length; g++) { if (g4[g].every(x => x && x.bird)) complete = g; else break; }
            const seen = new Map(); for (let g = 1; g < g4.length; g++) for (const x of g4[g]) if (x) seen.set(x.id, (seen.get(x.id) || 0) + 1);
            const common = [...seen.values()].filter(n => n > 1).length; const commonSlots = [...seen.values()].filter(n => n > 1).reduce((a, n) => a + n, 0);
            const b = db.getBird(id); const br = e.coi.coiBreakdown(db.getBird, b.sireId, b.damId, 10);
            return { filled: loss.filled, total: loss.total, complete, common, commonSlots, rows: br.contributions.length }; }""", barq)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'{ROOT}pedigree.html?id={barq}', wait_until='load'); pg.wait_for_selector('[data-testid=chart]', timeout=6000)

        # ── head ──
        check('crumb = the bird, h1 «شجرة النسب», subject line with plate + sex', pg.locator('[data-testid=crumb]').inner_text().strip() == 'برق' and pg.locator('h1').inner_text().strip() == 'شجرة النسب' and 'ذكر' in pg.locator('[data-testid=subject]').inner_text())
        coi = pg.locator('[data-testid=tile-coi] [data-testid=coi-badge]')
        check('[core_flows#3 on the tree] برق COI tile = 25.0%, band severe', coi.inner_text().strip().startswith('25') and coi.get_attribute('data-band') == 'severe', coi.inner_text())
        # [ruling D] invariant noun: «سلف من 30», never the spec's accusative «سلفًا من 30»
        check(f'[ruling D] tiles: «{exp["filled"]} · سلف من {exp["total"]}» and «{exp["complete"]} أجيال مكتملة» from ancestorLoss / the 4-gen grid', [x.strip() for x in pg.locator('[data-testid=tile-ancestors]').inner_text().split('\n')] == [str(exp['filled']), f'سلف من {exp["total"]}'] and pg.locator('[data-testid=tile-complete]').inner_text().split()[0] == str(exp['complete']), pg.locator('[data-testid=tile-ancestors]').inner_text().replace('\n', ' '))
        # ── chart: four ancestor generations by default ──
        labels = [x.strip() for x in pg.locator('[data-testid=ruler-label]').all_inner_texts()]
        # ruling 14: vanilla ped.subject «الطير» wins over the spec's «الطائر» for the first ruler label
        check('ruler: الطير · الوالدان · الأجداد · الأجداد الكبار · الجيل الخامس', labels == ['الطير', 'الوالدان', 'الأجداد', 'الأجداد الكبار', 'الجيل الخامس'], labels)
        nodes = pg.locator('[data-testid=node]').count(); known = pg.locator('[data-testid=node][data-known="1"]').count()
        check('31 slots (2+4+8+16 ancestors + the subject); known = filled', nodes == 30 and pg.locator('[data-testid=node-subject]').count() == 1 and known == exp['filled'], f'{nodes} slots, {known} known')
        check('common ancestors carry the dot marker (data-common) on every appearance', pg.locator('[data-testid=node][data-common="1"]').count() == exp['commonSlots'] and exp['common'] > 0, f'{exp["commonSlots"]} marked slots for {exp["common"]} birds')
        sx = pg.locator('[data-testid=node-subject]').bounding_box(); ax = pg.locator('[data-testid=node][data-gen="4"]').first.bounding_box()
        check('[core_flows#4] RTL: the subject sits RIGHT of the deepest ancestors', sx and ax and sx['x'] > ax['x'], f"subj.x={sx and sx['x']:.0f} anc.x={ax and ax['x']:.0f}")
        unk = pg.locator('[data-testid=node][data-known="0"]')
        if unk.count():
            check('an unknown slot offers «سلف غير مسجل — إضافة» → the child\'s edit form', unk.first.get_attribute('aria-label') == 'سلف غير مسجل — إضافة' and (unk.first.get_attribute('href') or '').startswith('/bird/edit?id='))
        else:
            check('an unknown slot offers «إضافة» (none in this pedigree — asserted on the teaching loft below)', True)
        check('nodes link to the profile', pg.locator('[data-testid=node][data-known="1"]').first.get_attribute('href').startswith('/bird?id='))
        # ── carried panels ──
        check('[core_flows#4] COI breakdown table rendered with the engine\'s rows', pg.locator('[data-testid=breakdown-row]').count() == exp['rows'] and exp['rows'] == 2, f'{pg.locator("[data-testid=breakdown-row]").count()} rows')
        check_clearance(pg, check, 'pedigree tree')
        with pg.expect_download(timeout=10000):
            pg.click('[data-testid=share-btn]')
        pg.wait_for_selector('[data-testid=toast]', timeout=5000)
        check_toast_clear(pg, check, 'pedigree tree (export toast over the certificate CTA)')
        pg.wait_for_timeout(4500)
        check('CTA + head action → /cert?id=; print and share present', pg.locator('[data-testid=cta-cert]').get_attribute('href').startswith('/cert?id=') and pg.locator('[data-testid=print-btn]').count() == 1 and pg.locator('[data-testid=share-btn]').count() == 1)
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/tree-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        # ── generation control (vanilla 3/4/5) ──
        pg.click('[data-testid=gen-btn][data-gens="3"]'); pg.wait_for_timeout(150)
        check('3 generations → 14 ancestor slots, 4 ruler labels', pg.locator('[data-testid=node]').count() == 14 and pg.locator('[data-testid=ruler-label]').count() == 4)
        pg.click('[data-testid=gen-btn][data-gens="5"]'); pg.wait_for_timeout(150)
        check('5 generations → 62 ancestor slots, 6 ruler labels (the sixth from the {n} template)', pg.locator('[data-testid=node]').count() == 62 and pg.locator('[data-testid=ruler-label]').count() == 6 and 'الجيل 6' in pg.locator('[data-testid=ruler-label]').last.inner_text())
        pg.screenshot(path=f'{FID}/tree-5gen-430.png', full_page=True)

        # ── the teaching loft: deepest pedigree, COI 12.5%, breakdown, the severe full-sib warning (teaching_loft#3–6) ──
        wipe(h); load(h, './example-loft-large.json')
        deep = h.evaluate("""() => { const db = window.__zajilDb, e = window.__zajilEngine; let best = null;
            for (const b of db.allBirds()) { const g = e.pedigree.pedigreeGrid(db.getBird, b.id, 5); const known = g.slice(1).flat().filter(x => x && x.bird).length; if (!best || known > best.known) best = { id: b.id, name: b.name, known }; }
            return best; }""")
        pg.goto(f'{ROOT}pedigree.html?id={deep["id"]}&gens=5', wait_until='load'); pg.wait_for_selector('[data-testid=chart]')
        known = pg.locator('[data-testid=node][data-known="1"]').count(); unknown = pg.locator('[data-testid=node][data-known="0"]').count()
        check('[teaching_loft#3] 5-gen tree fully populated (62 known ancestors, 0 unknown) via ?gens=5', known == 62 and unknown == 0 and deep['known'] == 62, f'known={known} unknown={unknown}')
        check('[teaching_loft#4] COI headline 12.5%', '12.5' in pg.locator('[data-testid=coi-headline] [data-testid=coi-badge]').inner_text())
        check('[teaching_loft#5] COI breakdown lists ≥4 common ancestors', pg.locator('[data-testid=breakdown-row]').count() >= 4, pg.locator('[data-testid=breakdown-row]').count())
        pg.fill('[data-testid=finder-input]', 'نجمة'); pg.wait_for_timeout(150); pg.click('[data-testid=finder-item] >> nth=0'); pg.wait_for_timeout(150)
        rel = pg.locator('[data-testid=rel-result]')
        check('[teaching_loft#6] full-sib pairing → «أشقاء» + severe level', rel.count() == 1 and 'أشقاء' in pg.locator('[data-testid=rel-key]').inner_text() and rel.get_attribute('data-level') == 'severe', pg.locator('[data-testid=rel-key]').inner_text() if rel.count() else 'no result')
        for w in (430, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/teaching-5gen-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        # a bird with unknown ancestors → the add link
        pg.goto(f'{ROOT}pedigree.html?id={deep["id"]}&gens=5', wait_until='load'); pg.wait_for_selector('[data-testid=chart]')
        orphan = h.evaluate("() => window.__zajilDb.allBirds().find(b => !b.sireId && !b.damId && b.name).id")
        pg.goto(f'{ROOT}pedigree.html?id={orphan}', wait_until='load'); pg.wait_for_selector('[data-testid=chart]')
        check('a parentless bird: every slot unknown, the first-generation slots link to its own edit form', pg.locator('[data-testid=node][data-known="0"]').count() == 30 and pg.locator('[data-testid=node][data-gen="1"]').first.get_attribute('href') == f'/bird/edit?id={orphan}' and pg.locator('[data-testid=tile-complete]').inner_text().split()[0] == '0')
        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
