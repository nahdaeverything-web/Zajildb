#!/usr/bin/env python3
"""Stats (/stats) — intent list re-authored from core_flows and teaching_loft (as they
apply) plus every state stats-v1 designs, and the FIVE departures design/README.md
rules deliberate: COI honesty, «غير محددة» in the strain card, the fifth sex tile, a
whole-view empty state, and the two season cards. Every number is checked against the
engine or the layer, never against a transcription. Binds to data-testid only.
Provisions its own server (R6)."""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve
from _layout import check_clearance
FID = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'fidelity', 'stats')); os.makedirs(FID, exist_ok=True)
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")

srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')
STATS = f'{ROOT}stats.html'
def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }"); return pg
def wipe(pg):
    pg.reload(wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("""async () => { await window.__zajilReady; const db = await window.__zajilDb;
        for (const p of [...db.state.pairs.values()]) await db.Pairs.remove(p.id);
        for (const r of [...db.state.raceResults.values()]) await db.Races.remove(r.id);
        for (const b of db.allBirds()) await db.deleteBird(b.id); }""")
def load(pg, file):
    pg.evaluate("async (f) => { const db = await window.__zajilDb; await db.importAll(await (await fetch(f)).json(), 'merge'); }", file)
def shots(pg, name, widths=(430, 900, 1400)):
    for w in widths:
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(200); pg.screenshot(path=f'{FID}/{name}-{w}.png', full_page=True)
    pg.set_viewport_size({'width': 430, 'height': 900})

# what the screen must show, computed here from the engine + the layer
EXPECT = """() => {
  const db = window.__zajilDb, e = window.__zajilEngine;
  const birds = db.allBirds().filter(b => !b.external);
  const depth = +(db.state.settings.coiDepth || 10);
  const known = birds.filter(b => b.sireId && b.damId);
  const cois = known.map(b => e.coi.inbreeding(db.getBird, b.id, depth).coi);
  const avg = cois.length ? cois.reduce((a, c) => a + c, 0) / cois.length : 0;
  const band = (c) => c === 0 ? 0 : c < 0.03125 ? 1 : c < 0.0625 ? 2 : c < 0.125 ? 3 : c < 0.25 ? 4 : 5;
  const bands = [0, 0, 0, 0, 0, 0]; for (const c of cois) bands[band(c)]++;
  // the season rule: 1 July turnover
  const seasonOf = (iso) => { const y = +iso.slice(0, 4), m = +iso.slice(5, 7); return m >= 7 ? y : y - 1; };
  const today = new Date().toISOString().slice(0, 10);
  const season = seasonOf(today);
  const rs = [...db.state.raceResults.values()].filter(r => r.date && seasonOf(r.date) === season && r.raceType !== 'training');
  const vels = rs.map(r => r.velocity).filter(Boolean);
  const pos = rs.map(r => r.position).filter(Boolean);
  const ps = [...db.state.pairs.values()].filter(p => p.season === String(season));
  const eggs = ps.flatMap(p => (p.rounds || []).flatMap(r => r.eggs || []));
  return {
    total: birds.length, cocks: birds.filter(b => b.sex === 'cock').length, hens: birds.filter(b => b.sex === 'hen').length,
    unknownSex: birds.filter(b => b.sex !== 'cock' && b.sex !== 'hen').length,
    fci: birds.filter(b => e.fci.hasFCIRing(b)).length,
    known: known.length, unknownPed: birds.length - known.length, depth,
    avg: (avg * 100).toFixed(2), bands, zeroCoi: cois.filter(c => c === 0).length,
    strainless: birds.filter(b => !(b.strain || '').trim()).length,
    strains: new Set(birds.map(b => (b.strain || '').trim()).filter(Boolean)).size,
    statuses: new Set(birds.map(b => b.status)).size,
    entries: rs.length, avgVel: vels.length ? Math.round(vels.reduce((a, v) => a + v, 0) / vels.length) : 0,
    best: pos.length ? Math.min(...pos) : null, top10: pos.filter(p => p <= 10).length,
    trainings: [...db.state.raceResults.values()].filter(r => r.raceType === 'training' && r.date && seasonOf(r.date) === season).length,
    pairs: ps.filter(p => p.status === 'active').length, eggs: eggs.length,
    hatched: eggs.filter(x => x.state === 'hatched').length, weaned: eggs.filter(x => x.weaned).length,
  };
}"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 430, 'height': 900})
        h = boot(ctx); wipe(h)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))

        # ── [departure 4] the whole-view empty state ──
        pg.goto(STATS, wait_until='load'); pg.wait_for_selector('[data-testid=count-line]', timeout=6000)
        check('[README departure 4] an empty loft shows ONE explained empty state — not four zeros and six empty bars',
              pg.locator('[data-testid=empty-panel]').count() == 1 and pg.locator('[data-testid=content]').count() == 0
              and 'لا توجد بيانات كافية بعد' in pg.locator('[data-testid=empty-panel]').inner_text() and pg.locator('[data-testid=count-line]').inner_text().strip() == 'لا طيور بعد')
        check('[README departure 4] …with two ways out: add a bird, or load the teaching loft', pg.locator('[data-testid=empty-add]').get_attribute('href') == '/bird/new' and pg.locator('[data-testid=empty-example]').count() == 1)
        shots(pg, 'empty')
        pg.click('[data-testid=empty-example]'); pg.wait_for_selector('[data-testid=content]', timeout=15000)
        check('…and loading the teaching loft fills the screen in place', pg.locator('[data-testid=tile-total]').count() == 1 and pg.locator('[data-testid=empty-panel]').count() == 0)

        # ── the teaching loft: every number against the engine ──
        exp = pg.evaluate(EXPECT)
        num = lambda sel: pg.locator(sel).inner_text().strip().split('\n')[0].replace(',', '').replace('\u066c', '')
        check(f'[departure 3] five tiles that reconcile: {exp["total"]} = {exp["cocks"]} + {exp["hens"]} + {exp["unknownSex"]}',
              num('[data-testid=tile-total]') == str(exp['total']) and num('[data-testid=tile-cocks]') == str(exp['cocks'])
              and num('[data-testid=tile-hens]') == str(exp['hens']) and num('[data-testid=tile-unknown]') == str(exp['unknownSex'])
              and exp['cocks'] + exp['hens'] + exp['unknownSex'] == exp['total'],
              f"{num('[data-testid=tile-total]')} vs {exp['total']}")
        check('[departure 3] …and the total tile states the sum it is made of', pg.locator('[data-testid=tile-sum]').inner_text().strip() == f"{exp['cocks']} + {exp['hens']} + {exp['unknownSex']}", pg.locator('[data-testid=tile-sum]').inner_text())
        check('FCI tile from the engine\'s hasFCIRing', num('[data-testid=tile-fci]') == str(exp['fci']), exp['fci'])
        check('count line «n طيرًا · محدّثة <today>»', pg.locator('[data-testid=count-line]').inner_text().startswith(f"{exp['total']} طيرًا") and 'محدّثة' in pg.locator('[data-testid=count-line]').inner_text(), pg.locator('[data-testid=count-line]').inner_text())

        # ── [departure 1] COI honesty ──
        check(f'[README departure 1] the scope line says what was computable: {exp["known"]} of {exp["total"]}',
              str(exp['known']) in pg.locator('[data-testid=coi-scope]').inner_text() and str(exp['total']) in pg.locator('[data-testid=coi-scope]').inner_text(), pg.locator('[data-testid=coi-scope]').inner_text())
        rows = pg.locator('[data-testid=coi-bars] [data-testid=bar-row]')
        counts = [x.strip() for x in rows.locator('.cnt, [class*=cnt]').all_inner_texts()] if rows.count() else []
        got_bands = pg.evaluate("() => [...document.querySelectorAll('[data-testid=coi-bars] [data-testid=bar-row]')].map(r => r.lastElementChild.textContent.trim())")
        check('[README departure 1] seven bands: the six COI bands + «نسب غير معروف», each matching the engine',
              rows.count() == 7 and got_bands[:6] == [str(x) for x in exp['bands']] and got_bands[6] == str(exp['unknownPed']),
              f"bands={got_bands} engine={exp['bands']}+{exp['unknownPed']}")
        check('[README departure 1] …the unknown-pedigree band is the LAST row and is marked apart', pg.locator('[data-testid=coi-bars] [data-testid=bar-row][data-kind=unk]').count() == 1 and 'نسب غير معروف' in pg.locator('[data-testid=coi-bars] [data-testid=bar-row]').last.inner_text())
        if exp['unknownPed']:
            check('[README departure 1] …and a note states the count and that they are excluded from both figures',
                  str(exp['unknownPed']) in pg.locator('[data-testid=coi-note]').inner_text() and 'غير محتسبة في المتوسط' in pg.locator('[data-testid=coi-note]').inner_text())
        check('[README departure 1] the average is over the computable birds only', pg.locator('[data-testid=avg-coi]').inner_text().strip().startswith(exp['avg']), f"screen={pg.locator('[data-testid=avg-coi]').inner_text()} engine={exp['avg']}%")
        check('[README departure 1] the «صفر» band holds exactly the birds the engine computes as 0 — no one else', int(got_bands[0]) == exp['zeroCoi'], f"zero band={got_bands[0]}, engine={exp['zeroCoi']}, unknown-pedigree={exp['unknownPed']}")
        top = pg.locator('[data-testid=top-coi] li')
        check('«أعلى COI» lists the highest first, each linking to its bird', top.count() >= 1 and top.count() <= 5 and top.first.locator('a').get_attribute('href').startswith('/bird?id='))

        # ── [departure 2] both breakdowns, with a total and a «غير محددة» row ──
        check('[README departure 2] the status card states its total = every bird', pg.locator('[data-testid=status-card]').inner_text().replace('\n', ' ').find(str(exp['total'])) > 0 and pg.locator('[data-testid=status-bars] [data-testid=bar-row]').count() == exp['statuses'], f"{exp['statuses']} statuses")
        strain_rows = pg.locator('[data-testid=strain-bars] [data-testid=bar-row]')
        check(f'[README departure 2] the strain card keeps strain-less birds as «غير محددة» ({exp["strainless"]}), not dropped',
              strain_rows.count() == exp['strains'] + (1 if exp['strainless'] else 0)
              and (pg.locator('[data-testid=strain-bars] [data-testid=bar-row][data-kind=unk]').count() == (1 if exp['strainless'] else 0)),
              f"{strain_rows.count()} rows for {exp['strains']} strains + {exp['strainless']} unset")
        if exp['strainless']:
            unk = pg.locator('[data-testid=strain-bars] [data-testid=bar-row][data-kind=unk]')
            check('[README departure 2] …and that row carries the real count, so the card totals the loft', unk.inner_text().strip().split('\n')[-1].strip() == str(exp['strainless']), unk.inner_text().replace('\n', ' '))

        # ── [departure 5] the two season cards ──
        check(f'[README departure 5] the race card: {exp["entries"]} entries, avg {exp["avgVel"]} m/min, best {exp["best"]}, {exp["top10"]} in the top ten',
              num('[data-testid=kpi-entries]') == str(exp['entries']) and num('[data-testid=kpi-velocity]').startswith(str(exp['avgVel']))
              and num('[data-testid=kpi-best]') == (str(exp['best']) if exp['best'] else '—') and num('[data-testid=kpi-top10]') == str(exp['top10']),
              f"entries={num('[data-testid=kpi-entries]')} vel={num('[data-testid=kpi-velocity]')}")
        check('[README departure 5] …states the rule «لا تُحتسب نتائج التدريب.» and honours it', 'لا تُحتسب نتائج التدريب' in pg.locator('[data-testid=race-note]').inner_text() and exp['entries'] == pg.evaluate("""() => { const seasonOf = (iso) => { const y = +iso.slice(0,4), m = +iso.slice(5,7); return m >= 7 ? y : y - 1; }; const t = new Date().toISOString().slice(0,10);
            return [...window.__zajilDb.state.raceResults.values()].filter(r => r.date && seasonOf(r.date) === seasonOf(t) && r.raceType !== 'training').length; }"""))
        check('[README departure 5] …the best-five table is ranked, the leader highlighted, each row linking to its bird',
              pg.locator('[data-testid=race-table] [data-testid=race-row]').count() <= 5 and (pg.locator('[data-testid=race-row]').count() == 0 or pg.locator('[data-testid=race-row]').first.locator('a').get_attribute('href').startswith('/bird?id=')))
        check(f'[README departure 5] the breeding card: {exp["pairs"]} active pairs, {exp["eggs"]} eggs, {exp["hatched"]} hatched, {exp["weaned"]} weaned',
              num('[data-testid=kpi-pairs]') == str(exp['pairs']) and num('[data-testid=kpi-eggs]') == str(exp['eggs'])
              and num('[data-testid=kpi-hatched]') == str(exp['hatched']) and num('[data-testid=kpi-weaned]') == str(exp['weaned']),
              f"pairs={num('[data-testid=kpi-pairs]')} eggs={num('[data-testid=kpi-eggs]')}")
        rate = round(exp['hatched'] / exp['eggs'] * 100, 1) if exp['eggs'] else 0
        check(f'[README departure 5] …and «نسبة الفقس» is hatched / eggs = {rate}%', num('[data-testid=kpi-rate]').startswith(str(rate)), f"{num('[data-testid=kpi-rate]')} vs {rate}%")
        # [Phase 6, fidelity audit] the COI card's two columns at >=1100. The spec puts the bars
        # in a 3fr column and the aside beside them in a 2fr (stats-v1.html CSS). The port wraps
        # the two halves in an unstyled .main, which made them ONE grid item — so the aside sat
        # UNDER the bars, in the same column, and the card's designed shape never appeared.
        pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(600)
        two = pg.evaluate("""() => { const card = document.querySelector('[data-testid=coi-card]');
            const bars = document.querySelector('[data-testid=coi-bars]');
            const top = card && card.querySelector('[data-testid=top-coi]');
            if (!card || !bars || !top) return null;
            const r = (e) => { const b = e.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width) }; };
            return { bars: r(bars), aside: r(top.parentElement) }; }""")
        check('[spec layout] @1400: the COI bars and the aside are two COLUMNS, bars in the wider one',
              two and abs(two['bars']['y'] - two['aside']['y']) < 60
              and two['bars']['x'] != two['aside']['x']
              and two['bars']['w'] > two['aside']['w'], str(two))
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(400)

        check_clearance(pg, check, 'stats')
        shots(pg, 'data')

        # ── [core_flows#10 / teaching_loft#12] the sample loft renders too, with its own numbers ──
        wipe(h); load(h, './sample-data.json')
        pg.goto(STATS, wait_until='load'); pg.wait_for_selector('[data-testid=content]')
        exp2 = pg.evaluate(EXPECT)
        check('[core_flows#10 / teaching_loft#12] the sample loft renders its own bars (≥6 in the COI card)', pg.locator('[data-testid=coi-bars] [data-testid=bar-row]').count() == 7 and num('[data-testid=tile-total]') == str(exp2['total']), f"{exp2['total']} birds")
        got2 = pg.evaluate("() => [...document.querySelectorAll('[data-testid=coi-bars] [data-testid=bar-row]')].map(r => r.lastElementChild.textContent.trim())")
        check(f'[README departure 1] on a loft that HAS birds with a missing parent ({exp2["unknownPed"]}), they land in the honesty band, not «صفر»',
              exp2['unknownPed'] > 0 and int(got2[6]) == exp2['unknownPed'] and int(got2[0]) == exp2['zeroCoi'],
              f"unknown band={got2[6]} engine={exp2['unknownPed']} · zero band={got2[0]} engine={exp2['zeroCoi']}")
        check('[README departure 1] …and the average is over the rest only, not dragged to zero by them',
              pg.locator('[data-testid=avg-coi]').inner_text().strip().startswith(exp2['avg']) and float(exp2['avg']) > 0,
              f"screen={pg.locator('[data-testid=avg-coi]').inner_text()} engine={exp2['avg']}%")
        check('the external birds vanilla excludes are excluded here too (stats.js:12)', exp2['total'] == pg.evaluate("() => window.__zajilDb.allBirds().filter(b => !b.external).length") and pg.evaluate("() => window.__zajilDb.allBirds().some(b => b.external)"))
        check('zero page errors', not errs, errs)
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
