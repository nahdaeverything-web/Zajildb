#!/usr/bin/env python3
"""Bird profile (/bird?id=…) — intent list re-authored from core_flows, teaching_loft,
example_data, record_factory, change_events (as they apply), plus every tab and
state bird-profile-v1 designs. Binds to data-testid only. Seeds through the
layer on the harness route, then exercises the real screen. Provisions its own
server (R6). Root assertion → new test mapping is in each check's label."""
import os, re, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance, check_toast_clear, scroll_to_bottom
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'bird-profile')); os.makedirs(FID, exist_ok=True)
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

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        h = boot(ctx); wipe(h)
        # seed the 20-bird sample (hand-verified COI cases live here)
        h.evaluate("async () => { const db = await window.__zajilDb; await db.importAll(await (await fetch('./sample-data.json')).json(), 'merge'); }")
        ids = h.evaluate("""() => { const db = window.__zajilDb; const f = n => (db.allBirds().find(b => b.name === n) || {}).id;
            const barq = db.allBirds().find(b => b.name === 'برق'); const orphan = db.allBirds().find(b => !b.sireId && !b.damId);
            return { barq: barq && barq.id, orphan: orphan && orphan.id, orphanName: orphan && orphan.name, n: db.allBirds().length }; }""")
        check('seed: sample loaded (20 birds), برق and a parentless bird found', ids['n'] == 20 and ids['barq'] and ids['orphan'], ids)
        # a blobless media row (bytes on another device) + a vaccination event for برق
        h.evaluate("""async (id) => { const db = await window.__zajilDb;
            await db.idbPut('media', { id: 'media-elsewhere-1', birdId: id, kind: 'photo', subtype: 'portrait', name: 'IMG_4471', addedAt: '2024-05-03T10:00:00Z' });
            await db.Health.save({ id: 'hv-1', eventType: 'vaccination', wholeLoft: false, birdId: id, date: '2026-02-01', medication: 'PMV', notes: '' });
            await db.Health.save({ id: 'ht-1', eventType: 'treatment', wholeLoft: false, birdId: id, date: '2026-05-19', medication: 'ronidazole', notes: '' }); }""", ids['barq'])

        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f"{ROOT}bird.html?id={ids['barq']}", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]', timeout=6000)

        # ── hero ──
        check('hero: name, sex chip, status chip, plate', pg.locator('[data-testid=hero-name]').inner_text().strip() == 'برق' and pg.locator('[data-testid=meta-sex]').count() == 1 and pg.locator('[data-testid=meta-status]').count() == 1 and pg.locator('[data-testid=plate]').count() == 1)
        check('hero: «تعديل» → /bird/edit?id= · «شهادة النسب» → /cert?id=', pg.locator('[data-testid=hero-edit]').get_attribute('href').startswith('/bird/edit?id=') and pg.locator('[data-testid=hero-cert]').get_attribute('href').startswith('/cert?id='))
        check('back link → /birds', pg.locator('[data-testid=back-link]').get_attribute('href') == '/birds')
        # ── tiles (core_flows#5 / teaching_loft#7: hand-verified COI) ──
        coi = pg.locator('[data-testid=tile-coi] [data-testid=coi-badge]')
        check('[core_flows#5] برق COI tile = 25.0% (full-sib mating), band severe', coi.inner_text().strip().startswith('25') and coi.get_attribute('data-band') == 'severe', coi.inner_text())
        check('tiles: races count and hatch year present', pg.locator('[data-testid=tile-races]').count() == 1 and pg.locator('[data-testid=tile-hatch]').count() == 1)
        # [ruling D] the tile label is an invariant noun — «سباق», never the spec's accusative «سباقًا» (wrong at 0, which is exactly this bird)
        check('[ruling D] races tile at a count of 0 reads «0 سباق»', [x.strip() for x in pg.locator('[data-testid=tile-races]').inner_text().split('\n')] == ['0', 'سباق'], pg.locator('[data-testid=tile-races]').inner_text().replace('\n', ' '))
        # ── tabs ──
        tabs = pg.locator('[role=tab]').all_inner_texts()
        check('four tabs: عام · النسب · السباقات · الصحة', [t.strip() for t in tabs] == ['عام', 'النسب', 'السباقات', 'الصحة'], tabs)
        check('overview selected by default', pg.locator('[data-testid=tab-over]').get_attribute('aria-selected') == 'true' and pg.locator('[data-testid=panel-over]').is_visible())
        # ── overview: verified notice, gallery with the elsewhere placeholder, basics, notes read-only ──
        check('«سجل موثق» notice present', 'سجل موثق' in pg.locator('[data-testid=verified-notice]').inner_text())
        check('gallery shows the blobless photo as «الصورة على جهاز آخر»', pg.locator('[data-testid=gallery] [data-testid=media-elsewhere]').count() == 1)
        # ruling 8 (4A acceptance): per-photo delete with undo (bird-detail.js:233)
        pg.click('[data-testid=media-tile] [data-testid=media-delete]'); pg.wait_for_timeout(150)
        check('[ruling 8] tile ✕ asks «تأكيد الحذف؟»', 'تأكيد الحذف' in pg.locator('[data-testid=dialog]').inner_text())
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(400)
        check('[ruling 8] the media row is gone from the gallery and the store', pg.locator('[data-testid=media-tile]').count() == 0 and pg.evaluate("async (id) => (await window.__zajilDb.mediaForBird(id)).length", ids['barq']) == 0)
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(400)
        check('[ruling 8] undo restores the row into the gallery', pg.locator('[data-testid=media-tile] [data-testid=media-elsewhere]').count() == 1)
        # [ruling C] that undo toast is up on a screen with its own fixed CTA — it must clear the CTA, not sit on it
        check_toast_clear(pg, check, 'bird profile (undo toast over the certificate CTA)')
        pg.wait_for_timeout(4500)   # let the confirmation toast expire before the screenshots
        rows = pg.locator('[data-testid=basics] [data-testid^=row-]').count()
        check('basic details rows (loft · colour · hatch · sire · dam · added)', rows >= 5, rows)
        check('sire / dam are links to their profiles', pg.locator('[data-testid=row-sire] a').get_attribute('href').startswith('/bird?id=') and pg.locator('[data-testid=row-dam] a').get_attribute('href').startswith('/bird?id='))
        # ruling 10 (4A acceptance): vanilla's add-note carried into the spec's notes card — saved through the write boundary
        n_notes = pg.locator('[data-testid=note]').count()
        pg.fill('[data-testid=note-input]', 'ملاحظة اختبار — من البروفايل'); pg.click('[data-testid=note-add]'); pg.wait_for_timeout(400)
        saved = pg.evaluate("(id) => (window.__zajilDb.getBird(id).notes || []).some(n => n.text === 'ملاحظة اختبار — من البروفايل')", ids['barq'])
        check_clearance(pg, check, 'bird profile · overview')
        check('[ruling 10] add-note appends to bird.notes and the card re-renders', saved and pg.locator('[data-testid=note]').count() == n_notes + 1 and pg.locator('[data-testid=note-input]').input_value() == '', pg.locator('[data-testid=note]').count())
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/overview-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        # ── pedigree tab ──
        pg.click('[data-testid=tab-ped]'); pg.wait_for_timeout(150)
        check('pedigree tab: COI line over generations + completeness', 'التربية الداخلية' in pg.locator('[data-testid=coi-line]').inner_text())
        check('pedigree tab: mini tree (subject + 2 + 4)', pg.locator('[data-testid=mini-node]').count() == 7)
        check('pedigree tab: «شجرة النسب الكاملة» → /pedigree?id=', pg.locator('[data-testid=full-tree-link]').get_attribute('href').startswith('/pedigree?id='))
        check('[core_flows#6] progeny analysis present', pg.locator('[data-testid=progeny]').count() == 1)
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/pedigree-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        # ── races tab ──
        pg.click('[data-testid=tab-race]'); pg.wait_for_timeout(150)
        nres = pg.evaluate("(id) => [...window.__zajilDb.state.raceResults.values()].filter(r => r.birdId === id).length", ids['barq'])
        if nres:
            check('races tab: best result block + season table', pg.locator('[data-testid=race-best]').count() == 1 and pg.locator('[data-testid=season-card]').count() >= 1, nres)
        else:
            check('races tab: empty state «لا نتائج مسجلة.»', 'لا نتائج' in pg.locator('[data-testid=panel-race]').inner_text())
        pg.screenshot(path=f'{FID}/races-empty-430.png', full_page=True)
        # the designed races tab (best result + season tables): the sample bird with the most results
        racer = h.evaluate("() => { const db = window.__zajilDb; const n = new Map(); for (const r of db.state.raceResults.values()) n.set(r.birdId, (n.get(r.birdId) || 0) + 1); return [...n.entries()].sort((a, b) => b[1] - a[1])[0]; }")
        pg.goto(f"{ROOT}bird.html?id={racer[0]}&tab=race", wait_until='load'); pg.wait_for_selector('[data-testid=race-best]', timeout=6000)
        check('races tab (bird with results): best result + ≥1 season table, ranks as pills', pg.locator('[data-testid=season-card]').count() >= 1 and pg.locator('[data-testid=race-row]').count() == racer[1], racer[1])
        check(f'[ruling D] the same tile label at a count of {racer[1]} is still «سباق»', [x.strip() for x in pg.locator('[data-testid=tile-races]').inner_text().split('\n')] == [str(racer[1]), 'سباق'], pg.locator('[data-testid=tile-races]').inner_text().replace('\n', ' '))
        # ruling 6: one season rule — split-year label with the 1 July turnover, computed here from the bird's own result dates
        exp = pg.evaluate("(id) => { const s = new Set(); for (const r of window.__zajilDb.state.raceResults.values()) if (r.birdId === id && r.date) { const y = +r.date.slice(0, 4), m = +r.date.slice(5, 7); s.add(m >= 7 ? y : y - 1); } return [...s].sort((a, b) => b - a); }", racer[0])
        heads = [h.strip() for h in pg.locator('[data-testid=season-card] h2').all_inner_texts()]
        check('[ruling 6] season cards labelled «موسم a / a+1» by the July rule, newest first', [h.split()[1] for h in heads] == [str(a) for a in exp], heads)
        # ruling 10: the FCI per-bird line as one row in the races tab (bird-detail.js:131)
        q = pg.evaluate("(id) => { const db = window.__zajilDb, e = window.__zajilEngine; const rs = [...db.state.raceResults.values()].filter(r => r.birdId === id); const el = e.fci.birdEligibility(db.getBird(id), rs); return [el.qualifyingResults.length, rs.length]; }", racer[0])
        fci = pg.locator('[data-testid=fci-row]').inner_text()
        check('[ruling 10] «نتائج مؤهلة: n / total» row present with the engine\'s numbers', 'نتائج مؤهلة' in fci and f'{q[0]} / {q[1]}' in fci, fci.replace('\n', ' '))
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/races-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        pg.goto(f"{ROOT}bird.html?id={ids['barq']}", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        # ── health tab: interim next-vaccination rule (ruling 4) ──
        pg.click('[data-testid=tab-hlth]'); pg.wait_for_timeout(150)
        nxt = pg.locator('[data-testid=health-next]')
        check('[ruling 4] next vaccination = last vaccination + 365 d, labelled as an estimate', nxt.count() == 1 and '2027' in nxt.inner_text() and 'تقديري' in nxt.inner_text(), nxt.inner_text().replace('\n', ' ') if nxt.count() else 'absent')
        # vanilla bird-detail.js:162: the bird's own events + whole-loft events of its loft
        nev = pg.evaluate("(id) => { const db = window.__zajilDb; const b = db.getBird(id); return [...db.state.healthEvents.values()].filter(e => e.birdId === id || (e.wholeLoft && e.loftId === b.loftId)).length; }", ids['barq'])
        check('health log lists own + whole-loft events with vanilla type labels', nev >= 2 and pg.locator('[data-testid=health-event]').count() == nev and 'تطعيم' in pg.locator('[data-testid=health-log]').inner_text() and 'علاج' in pg.locator('[data-testid=health-log]').inner_text(), f'{nev} events')
        for w in (430, 900, 1400):
            pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(150); pg.screenshot(path=f'{FID}/health-{w}.png', full_page=True)
        pg.set_viewport_size({'width': 430, 'height': 900})
        # ── ?tab= selects a tab (spec script) ──
        pg.goto(f"{ROOT}bird.html?id={ids['barq']}&tab=race", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        check('?tab=race opens the races tab', pg.locator('[data-testid=tab-race]').get_attribute('aria-selected') == 'true')
        # ── a bird with NO vaccination (own or whole-loft — bird-detail.js:162 counts both): the next block is hidden entirely (ruling 4) ──
        lone = h.evaluate("""async () => { const db = await window.__zajilDb; const b = db.newBird({ name: 'Lone', sex: 'hen', loftId: 'loft-other' });
            await db.saveBird(b, { force: true }); return b.id; }""")
        pg.goto(f"{ROOT}bird.html?id={lone}&tab=hlth", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        check('[ruling 4] no vaccination event → next-vaccination block absent', pg.locator('[data-testid=health-next]').count() == 0 and pg.locator('[data-testid=health-event]').count() == 0)
        h.evaluate("async (id) => { const db = await window.__zajilDb; await db.deleteBird(id); }", lone)
        # ── add-sibling intent (example_data#7–11 / record_factory#2–5) — the FORM is 4B; assert routing + no write ──
        pg.goto(f"{ROOT}bird.html?id={ids['orphan']}", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        n0 = pg.evaluate("() => window.__zajilDb.allBirds().length")
        pg.click('[data-testid=options-menu]'); pg.wait_for_timeout(100); pg.click('[data-testid=menu-add-sibling]'); pg.wait_for_timeout(150)
        check('[example_data#9] parentless bird → placeholder dialog shown', pg.locator('[data-testid=dialog]').count() == 1)
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(400)
        check('[record_factory#2] add-sibling routes to the form WITH an intent (?siblingOf=)', '/bird/new' in pg.url and 'siblingOf=' in pg.url, pg.url)
        pg.goto(f"{ROOT}bird.html?id={ids['orphan']}", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        check('[record_factory#5 / example_data#10] abandoning it created NO records', pg.evaluate("() => window.__zajilDb.allBirds().length") == n0)
        pg.goto(f"{ROOT}bird.html?id={ids['barq']}", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        pg.click('[data-testid=options-menu]'); pg.wait_for_timeout(100); pg.click('[data-testid=menu-add-sibling]'); pg.wait_for_timeout(400)
        check('[example_data#7–8] bird with parents → form prefilled via ?sire=&dam=', '/bird/new' in pg.url and 'sire=' in pg.url and 'dam=' in pg.url, pg.url)
        # ── delete with «علاقات مرتبطة», then undo restores INTO the visible list (change_events#6) ──
        pg.goto(f"{ROOT}bird.html?id={ids['barq']}", wait_until='load'); pg.wait_for_selector('[data-testid=profile-hero]')
        pg.click('[data-testid=options-menu]'); pg.wait_for_timeout(100); pg.click('[data-testid=menu-delete]'); pg.wait_for_timeout(150)
        dtxt = pg.locator('[data-testid=dialog]').inner_text()
        check('delete confirm names the bird and its relation count («علاقات مرتبطة»)', 'برق' in dtxt and 'علاقات مرتبطة' in dtxt, dtxt.replace('\n', ' ')[:120])
        pg.click('[data-testid=dialog-confirm]')
        pg.wait_for_url(re.compile(r'/birds/?(\?.*)?$'), timeout=5000); pg.wait_for_selector('[data-testid=bird-row]', timeout=5000)
        check('after delete: back on /birds and برق is gone', not any('برق' == r.strip().split('\n')[0] for r in pg.locator('[data-testid=bird-row]').all_inner_texts()))
        pg.click('[data-testid=toast-action]'); pg.wait_for_timeout(400)
        check('[change_events#6] undo restores the bird INTO the visible list', pg.evaluate("() => [...document.querySelectorAll('[data-testid=bird-row]')].some(r => r.textContent.includes('برق'))"))
        # ── Remco progeny (teaching_loft#8) on the large loft ──
        wipe(h); h.evaluate("async () => { const db = await window.__zajilDb; await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge'); }")
        rid = h.evaluate("() => { const db = window.__zajilDb; const b = db.allBirds().find(x => /remco/i.test(x.name || '') || /ريمكو/.test(x.name || '')); return b && b.id; }")
        check('seed: Remco found in the teaching loft', bool(rid))
        if rid:
            pg.goto(f"{ROOT}bird.html?id={rid}&tab=ped", wait_until='load'); pg.wait_for_selector('[data-testid=progeny]')
            direct = pg.locator('[data-testid=prog-direct]').inner_text().strip()
            check('[teaching_loft#8] Remco progeny analysis populated (direct offspring > 0)', direct not in ('', '0', '٠'), direct)
        # ── [teaching_loft #7, root line 51 — UNCOVERED until Phase 6] عاصف's 25% COI ──
        # The engine proves 0.25 for g3-asif in next/tests/example-large.test.js:45, and the
        # root's claim is that the DETAIL SCREEN shows it. The port's only 25% assertion is
        # برق's, in the SAMPLE loft, from a different inbreeding path (full sibs vs father ×
        # daughter) — so the screen half of this was carried nowhere.
        asif = h.evaluate("() => { const db = window.__zajilDb; const b = db.allBirds().find(x => (x.name || '').includes('عاصف')); return b && b.id; }")
        check('seed: عاصف found in the teaching loft', bool(asif), str(asif))
        if asif:
            pg.goto(f'{ROOT}bird.html?id={asif}', wait_until='load'); pg.wait_for_selector('[data-testid=tile-coi]', timeout=8000)
            ac = pg.locator('[data-testid=tile-coi] [data-testid=coi-badge]')
            expected = h.evaluate("(id) => window.__zajilEngine.coi.inbreeding(window.__zajilDb.getBird, id, +(window.__zajilDb.state.settings.coiDepth || 10)).coi", asif)
            check('[teaching_loft #7] عاصف\'s detail screen shows 25% COI — father × daughter, from the engine',
                  ac.inner_text().strip().startswith('25') and abs(expected - 0.25) < 1e-9,
                  f'screen {ac.inner_text().strip()!r} engine {expected}')
            check('…and it is banded severe, like any quarter-COI mating',
                  ac.get_attribute('data-band') == 'severe', ac.get_attribute('data-band'))

        # ── [data_loss #4, root line 56 — UNCOVERED until Phase 6] object URLs are revoked ──
        # The gallery mints an object URL per photo it can show, and leaving the view must
        # give them back. Nothing in the port asserted it: the only gallery test seeds a
        # BLOBLESS row, so no URL was ever created on the tested path. A leak here is
        # invisible until a long session runs a device out of memory.
        leak = ctx.new_page()
        leak.add_init_script("""
            window.__urls = { made: [], freed: [] };
            const mk = URL.createObjectURL.bind(URL), rv = URL.revokeObjectURL.bind(URL);
            URL.createObjectURL = (b) => { const u = mk(b); window.__urls.made.push(u); return u; };
            URL.revokeObjectURL = (u) => { window.__urls.freed.push(u); return rv(u); };
        """)
        withphoto = h.evaluate("""async () => { const db = await window.__zajilDb;
            const b = db.allBirds()[0];
            const bytes = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), c => c.charCodeAt(0));
            await db.addMedia(b.id, 'photo', 'body', 'real.png', new Blob([bytes], { type: 'image/png' }));
            return b.id; }""")
        leak.goto(f'{ROOT}bird.html?id={withphoto}', wait_until='load')
        leak.wait_for_selector('[data-testid=gallery]', timeout=8000)
        leak.wait_for_function("() => window.__urls.made.length > 0", timeout=8000)
        made = leak.evaluate("() => window.__urls.made.length")
        check('[data_loss #4] the gallery mints an object URL for a photo it can actually show',
              made >= 1 and leak.locator('[data-testid=gallery] img').count() >= 1,
              f'{made} made, {leak.locator("[data-testid=gallery] img").count()} img(s)')
        # Leaving the view through the app's own back link — a CLIENT-side navigation, so
        # React unmounts the gallery and the effect's cleanup runs while the counters
        # survive. A document navigation would destroy the page and the evidence with it.
        leak.click('[data-testid=back-link]')
        leak.wait_for_selector('[data-testid=bird-row], [data-testid=empty-add]', timeout=8000)
        leak.wait_for_timeout(1200)
        freed = leak.evaluate("() => ({ made: window.__urls.made, freed: window.__urls.freed })")
        outstanding = [u for u in freed['made'] if u not in freed['freed']]
        check('[data_loss #4] …and leaving the view gives every one of them back',
              freed['made'] and not outstanding,
              f"{len(freed['made'])} made, {len(freed['freed'])} freed, {len(outstanding)} outstanding")
        leak.close()

        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
