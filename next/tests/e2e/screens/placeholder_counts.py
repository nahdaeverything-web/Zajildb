#!/usr/bin/env python3
"""PLACEHOLDER PARENTS — THE COUNTS A FANCIER IS TOLD (RULED 2026-11-24, B1 and B7; src/example-data.js, src/db/io.js).

  B1  the teaching-data removal: «لديك {m} من سجلاتك داخل اللوفت التجريبي؛ لا تُحذف، بل تُنقل إلى لوفتك» counts real
      birds only, never placeholder parents, and is true of every record it counts — on the first-run device, where
      the teaching loft is the current loft and everything the fancier makes is filed in it. Before this ruling it
      said 5 of a device that held one bird of the fancier's and four placeholders; 3 were moved and 2 were deleted.
  B7  the import toast, the replace question, the restore question and its toast, and the two teaching loaders'
      toast count real birds only.

Each scenario is its own device (its own browser context). Fixture names are invented; nothing is configured, so
nothing leaves the page — the two loader scenarios answer the dataset file themselves, from the build's own copy.

    python3 tests/e2e/screens/placeholder_counts.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import json, os, re, sys, uuid
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _typography import SCAN                 # noqa: E402
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:520]) if not ok and d != '' else ''}")
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s or '')
def wait(pg, js, ms=8000):
    try: pg.wait_for_function(js, timeout=ms); return True
    except Exception: return False
def click(pg, sel, ms=6000):
    try: pg.click(sel, timeout=ms); return True
    except Exception: return False
def faces(pg): return [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]
def dialog(pg):
    d = pg.locator('[data-testid=dialog]')
    return digits(' '.join(d.inner_text().split())) if d.count() else ''
def toast_with(pg, word, ms=15000):
    """The newest toast that carries `word`, digits made Western — '' when none came."""
    wait(pg, f"() => [...document.querySelectorAll('[data-testid=toast]')].some(t => (t.textContent || '').includes({json.dumps(word)}))", ms)
    found = [x for x in pg.locator('[data-testid=toast]').all_inner_texts() if word in x]
    return digits(' '.join(found[-1].split())) if found else ''

LOAD = "async (db) => { const r = await fetch(new URL('example-loft-large.json', document.querySelector('link[rel=manifest]').href)); return (await db.loadExampleDataset(await r.json())).birds; }"
# what the fancier filed in a dataset loft that is NOT a dataset record — the records the question's promise is about
MINE = """async (db) => { const IDS = await db.exampleIds(); const lofts = new Set(await db.exampleLoftIds()); const out = {};
    for (const [store, map] of [['birds', db.state.birds], ['pairs', db.state.pairs], ['raceResults', db.state.raceResults], ['healthEvents', db.state.healthEvents]])
      out[store] = [...map.values()].filter(r => lofts.has(r.loftId) && !IDS[store].has(r.id)).map(r => ({ id: r.id, placeholder: r.placeholder === true }));
    return out; }"""
HERE_NOW = """async (db, ids) => { const out = {}; for (const [k, id] of Object.entries(ids)) { const b = db.getBird(id);
      out[k] = b ? { here: true, ph: b.placeholder === true, loft: b.loftId } : { here: false, tomb: !!(await db.idbGet('tombstones', 'birds:' + id)) }; }
    return out; }"""
INTEGRITY = "() => { const db = window.__zajilDb, e = window.__zajilEngine; return e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents, lofts: db.state.lofts }).length; }"
def placeholder_record(loft_id):
    return {'id': str(uuid.uuid4()), 'rings': [], 'name': 'أب غير معروف', 'sex': 'cock', 'hatchDate': '', 'colour': '', 'strain': '', 'eyeSign': '', 'status': 'reference', 'sireId': None, 'damId': None,
            'external': True, 'placeholder': True, 'breeder': '', 'owner': '', 'acquiredFrom': '', 'acquiredDate': '', 'notes': [], 'loftId': loft_id, 'createdAt': '2026-11-24T08:00:00.000Z', 'updatedAt': '2026-11-24T08:00:00.000Z'}

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); ERRS = []
        def device(routes=None):
            ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, service_workers='block')
            for pattern, handler in (routes or {}).items(): ctx.route(pattern, handler)
            pg = ctx.new_page(); pg.on('pageerror', lambda e, _p=pg: ERRS.append(perr(e, _p)))
            pg.goto(HARNESS, wait_until='load'); pg.wait_for_function('window.__zajilReady'); return ctx, pg
        def tools(pg, row=None):
            pg.goto(ROOT + 'tools/', wait_until='load')
            try: pg.wait_for_selector('[data-testid=tools-list]', timeout=15000)
            except Exception: return False
            pg.wait_for_timeout(700)
            if row:
                r = pg.locator(f'[data-row={row}]')
                if not r.count(): return False
                if r.get_attribute('open') is None: r.locator('summary').click(); pg.wait_for_timeout(300)
            return True
        def removal_question(pg):
            """Open the removal's question and read it; the question is left open."""
            if not tools(pg, 'example-remove'): return ''
            click(pg, '[data-testid=example-remove]'); wait(pg, "() => document.querySelector('[data-testid=dialog]')", 8000); return dialog(pg)

        # ══ B1 — THE FIRST-RUN DEVICE: the teaching loft is the current loft, so what the fancier makes is filed in it ══
        c1, d1 = device(); loaded = run(d1, LOAD)
        setup = run(d1, """async (db) => { const IDS = await db.exampleIds(); const founders = db.allBirds().filter(x => IDS.birds.has(x.id) && !x.sireId && !x.damId).sort((x, y) => x.id.localeCompare(y.id)); const [t1, t2, t3] = founders;
            const two = async () => [await db.saveBird(db.newBird({ name: 'أب غير معروف', sex: 'cock', placeholder: true })), await db.saveBird(db.newBird({ name: 'أم غير معروفة', sex: 'hen', placeholder: true }))];
            const [as, ad] = await two();                               // their children are both teaching birds
            for (const t of [t1, t2]) await db.saveBird({ ...db.getBird(t.id), sireId: as.id, damId: ad.id }, { allowWarnings: true });
            const [bs, bd] = await two();                               // one teaching child, and one bird of the fancier's own
            await db.saveBird({ ...db.getBird(t3.id), sireId: bs.id, damId: bd.id }, { allowWarnings: true });
            const own = await db.saveBird(db.newBird({ name: 'طيري', sex: 'hen', sireId: bs.id, damId: bd.id }), { allowWarnings: true });
            return { ids: { as: as.id, ad: ad.id, bs: bs.id, bd: bd.id, own: own.id }, teachingIsCurrent: (await db.exampleLoftIds()).includes(db.currentLoft().id), filedThere: [as, ad, bs, bd, own].every(x => x.loftId === db.currentLoft().id) }; }""")
        ids = setup['ids']; mine0 = run(d1, MINE)
        pres = run(d1, "async (db) => { const p = await db.examplePresence(); return p && { birds: p.birds, own: p.own, ownBirds: p.ownBirds, current: p.current }; }")
        check('[B1 · setup] a first-run device: 38 teaching birds loaded, the teaching loft is current, and the fancier\'s one bird and four placeholder parents are all filed in it — five records of his in the teaching loft',
              loaded == 38 and setup['teachingIsCurrent'] and setup['filedThere'] and len(mine0['birds']) == 5 and sum(1 for x in mine0['birds'] if x['placeholder']) == 4, (loaded, setup, mine0['birds']))
        check('[B1 · the count · M-b1-own fails here] the removal counts ONE record of the fancier\'s in the teaching loft — his bird; the four placeholder parents are not counted (it said 5)',
              pres == {'birds': 38, 'own': 1, 'ownBirds': 1, 'current': True}, pres)
        asked = removal_question(d1); ty = faces(d1)
        check('[B1 · the question] …and the question says so: «لديك 1 من سجلاتك داخل اللوفت التجريبي؛ لا تُحذف، بل تُنقل إلى لوفتك.» — beside «سيُحذف 38 طيرًا», in a face that has Arabic',
              'لديك 1 من سجلاتك داخل اللوفت التجريبي؛ لا تُحذف، بل تُنقل إلى لوفتك.' in asked and 'سيُحذف 38 طيرًا' in asked and not ty, (asked, ty[:2]))
        click(d1, '[data-testid=dialog-cancel]'); d1.wait_for_timeout(300)
        res = run(d1, "async (db) => { const r = await db.removeExampleData(); return r && { birds: r.birds, moved: r.moved, kept: r.kept, target: r.target }; }") or {}
        now = run(d1, HERE_NOW, ids); target = res.get('target')
        check('[B1 · «لا تُحذف» is true of every record counted] the one record it counted is still here, and was moved to the fancier\'s loft',
              now['own'].get('here') and now['own'].get('loft') == target and bool(target), (now['own'], target))
        check('[B1 · the result · M-b1-moved fails here] the removal reports 38 birds removed and ONE record moved — real birds only (it said 3)', res.get('birds') == 38 and res.get('moved') == 1, res)
        check('[B1 · the four placeholders] the two whose children were all teaching birds went with them, tombstoned; the two the fancier\'s bird names are kept, still placeholders, and re-filed with it — 5 became 3 moved and 2 deleted, of which the fancier is told 1',
              now['as'] == {'here': False, 'tomb': True} and now['ad'] == {'here': False, 'tomb': True} and all(now[k].get('here') and now[k].get('ph') and now[k].get('loft') == target for k in ('bs', 'bd')), now)
        left = run(d1, "async (db) => ({ records: db.allBirds().length, listed: db.listedBirds().map(x => x.name) })")
        check('[B1] …three bird records are left, one of them a bird a fancier counts, and the register is referentially clean', left == {'records': 3, 'listed': ['طيري']} and d1.evaluate(INTEGRITY) == 0, (left, d1.evaluate(INTEGRITY)))
        c1.close()

        # ══ B1 — «لا تُحذف» AND THE FANCIER'S OWN RESULTS, HEALTH EVENTS AND PAIRS (not placeholders: found while building B1) ══
        c2, d2 = device(); run(d2, LOAD)
        s2 = run(d2, """async (db) => { const IDS = await db.exampleIds(); const loftId = db.currentLoft().id;
            const child = new Set(); for (const x of db.allBirds()) { child.add(x.sireId); child.add(x.damId); }
            const leaf = db.allBirds().filter(x => IDS.birds.has(x.id) && !child.has(x.id)).sort((x, y) => x.id.localeCompare(y.id));     // teaching birds no bird descends from: the removal deletes them
            const t1 = leaf.find(x => x.sex === 'cock'), t2 = leaf.find(x => x.sex === 'hen');
            const mine = await db.saveBird(db.newBird({ name: 'طيرتي', sex: 'hen' }));
            const race = (birdId) => db.Races.save({ id: db.uuid(), birdId, loftId, date: '2026-04-01', raceName: 'سباق', raceType: 'race', distanceKm: 100, velocity: 1000, position: 1, birdsEntered: 10 });
            const r1 = await race(mine.id), r2 = await race(t2.id);
            const h2 = await db.Health.save({ id: db.uuid(), eventType: 'check', wholeLoft: false, birdId: t2.id, loftId, date: '2026-02-01', medication: '', notes: '' });
            const p2 = await db.Pairs.save({ sireId: t1.id, damId: mine.id, season: '2026', nestBox: '1', status: 'active', loftId, rounds: [] });
            return { mine: mine.id, r1: r1.id, r2: r2.id, h2: h2.id, p2: p2.id, own: (await db.examplePresence()).own }; }""")
        mine2 = run(d2, MINE); asked2 = removal_question(d2); click(d2, '[data-testid=dialog-cancel]'); d2.wait_for_timeout(300)
        run(d2, "async (db) => { await db.removeExampleData(); }")
        kept2 = run(d2, "async (db, s) => ({ mine: !!db.getBird(s.mine), r1: db.state.raceResults.has(s.r1), r2: db.state.raceResults.has(s.r2), h2: db.state.healthEvents.has(s.h2), p2: db.state.pairs.has(s.p2) })", s2)
        check('[B1 · «لا تُحذف» is true of every record counted · M-b1-cascade fails here] a bird of the fancier\'s with a result, and — for teaching birds the removal deletes — a result, a health event and a pair with his hen: five records of his in the teaching loft, of which the question counts the TWO it does not delete',
              s2['own'] == 2 and 'لديك 2 من سجلاتك داخل اللوفت التجريبي' in asked2 and sum(len(v) for v in mine2.values()) == 5, (s2['own'], asked2, {k: len(v) for k, v in mine2.items()}))
        check('[B1] …and those two are what is left: his bird and its result; the three that named a deleted teaching bird went with it, as deleteBird has always done',
              kept2 == {'mine': True, 'r1': True, 'r2': False, 'h2': False, 'p2': False}, kept2)
        c2.close()

        # ══ B7 — the source: three birds a fancier counts, two placeholder parents ══
        c3, d3 = device()
        payload = run(d3, """async (db) => { const loftId = db.currentLoft().id; await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت المصدر' });
            const mk = async (name, sex, extra = {}) => (await db.saveBird(db.newBird({ name, sex, loftId, ...extra }), { allowWarnings: true })).id;
            const ps = await mk('أب غير معروف', 'cock', { placeholder: true }), pd = await mk('أم غير معروفة', 'hen', { placeholder: true });
            await mk('نجم', 'cock', { sireId: ps, damId: pd }); await mk('سحابة', 'hen', { sireId: ps, damId: pd }); await mk('رعد', 'cock');
            return await db.exportAll(); }""")
        c3.close()
        in_file = (len(payload.get('birds') or []), sum(1 for x in payload.get('birds') or [] if x.get('placeholder') is True))
        def import_file(pg, data, mode):
            pg.goto(ROOT + 'tools/import/', wait_until='load')
            try: pg.wait_for_selector('[data-testid=import-mode]', timeout=15000)
            except Exception: return
            if mode == 'replace': click(pg, '[data-testid=import-mode] [data-value=replace]')
            pg.set_input_files('[data-testid=file-input]', files=[{'name': 'file.json', 'mimeType': 'application/json', 'buffer': json.dumps(data).encode()}]); click(pg, '[data-testid=import-file]')
        c4, d4 = device(); import_file(d4, payload, 'merge'); said = toast_with(d4, 'تم الاستيراد'); held = run(d4, "async (db) => [db.allBirds().length, db.listedBirds().length]")
        check('[B7 · the import toast · M-b7-toast, M-b7-count and M-b7-site-import fail here] a file of five bird records, two of them placeholder parents: «تم الاستيراد: 3 طير، 0 زوج، 0 نتيجة.» — and all five records are in',
              in_file == (5, 2) and said == 'تم الاستيراد: 3 طير، 0 زوج، 0 نتيجة.' and held == [5, 3], (in_file, said, held))
        # a replace by a file that holds one other bird: the question counts what goes
        other = dict(next((x for x in payload['birds'] if x.get('name') == 'رعد'), {}), id=str(uuid.uuid4()), name='بديل', updatedAt='2030-01-01T00:00:00.000Z')
        import_file(d4, dict(payload, birds=[other]), 'replace'); wait(d4, "() => document.querySelector('[data-testid=dialog]')", 8000); asked = dialog(d4)
        check('[B7 · the replace question · M-b7-replace fails here] replacing with a file that holds one other bird: «سيُحذف من السجلّ 3 طيرًا و2 سجلًا آخر غير موجودة في الملف» — the two placeholder parents are records that go, not birds',
              'سيُحذف من السجلّ 3 طيرًا و2 سجلًا آخر غير موجودة في الملف' in asked, asked)
        click(d4, '[data-testid=dialog-confirm]'); said2 = toast_with(d4, '1 طير'); held2 = run(d4, "async (db) => db.allBirds().map(x => x.name)")
        check('[B7] …and the replace says «تم الاستيراد: 1 طير، 0 زوج، 0 نتيجة.»', said2 == 'تم الاستيراد: 1 طير، 0 زوج، 0 نتيجة.' and held2 == ['بديل'], (said2, held2))
        # the restore of the snapshot the replace took: what comes back
        d4.goto(ROOT + 'tools/restore/', wait_until='load'); wait(d4, "() => document.querySelector('[data-testid=snap-row][data-id^=pre-import]')", 15000); d4.wait_for_timeout(400)
        meta = digits(' '.join((d4.locator('[data-testid=snap-row][data-id^=pre-import] span > div').first.inner_text() if d4.locator('[data-testid=snap-row][data-id^=pre-import]').count() else '').split()))
        click(d4, '[data-testid=snap-row][data-id^=pre-import] [data-testid=snap-restore]'); wait(d4, "() => document.querySelector('[data-testid=dialog]')", 8000); asked3 = dialog(d4)
        check('[B7 · the restore question · M-b7-returning fails here] restoring that snapshot: «يعود 3 طيرًا غير موجود الآن:» — نجم, سحابة and رعد are named, and no placeholder parent is',
              'يعود 3 طيرًا غير موجود الآن:' in asked3 and all(n in asked3 for n in ('نجم', 'سحابة', 'رعد')) and 'غير معروف' not in asked3 and meta == '3 طيرًا', (asked3, meta))
        click(d4, '[data-testid=dialog-confirm]'); said3 = toast_with(d4, '3 طير'); held3 = run(d4, "async (db) => [db.allBirds().length, db.listedBirds().length]")
        check('[B7 · the restore toast · M-b7-site-restore fails here] …and the restore says «تم الاستيراد: 3 طير، 0 زوج، 0 نتيجة.» — five records are back', said3 == 'تم الاستيراد: 3 طير، 0 زوج، 0 نتيجة.' and held3 == [5, 3], (said3, held3))
        c4.close()

        # ══ B7 — the two teaching loaders. No shipped dataset holds a placeholder, so the file is answered here: the build's own copy, plus one ══
        def with_one_more(route):
            resp = route.fetch(); data = resp.json(); data['birds'] = list(data['birds']) + [placeholder_record(data['lofts'][0]['id'])]
            route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
        c5, d5 = device({'**/sample-data.json': with_one_more}); ok5 = tools(d5, 'teaching'); click(d5, '[data-testid=load-sample]'); said5 = toast_with(d5, 'حُمّلت'); held5 = run(d5, "async (db) => [db.allBirds().length, db.listedBirds().length]")
        check('[B7 · the loader in الأدوات · M-b7-site-loader fails here] the small teaching loft with one placeholder parent added to the file: 21 records are in, and the toast says «20 طيرًا»',
              ok5 and held5 == [21, 20] and '20 طيرًا' in said5 and '21' not in said5, (ok5, held5, said5))
        c5.close()
        c6, d6 = device({'**/example-loft-large.json': with_one_more}); d6.goto(ROOT + 'birds/', wait_until='load'); wait(d6, "() => document.querySelector('[data-testid=empty-example]')", 10000)
        click(d6, '[data-testid=empty-example]'); said6 = toast_with(d6, 'حُمّلت'); held6 = run(d6, "async (db) => [db.allBirds().length, db.listedBirds().length]")
        check('[B7 · the loader on the empty register · M-b7-site-empty fails here] the large teaching loft with one placeholder parent added: 39 records are in, and the toast says «38 طيرًا»',
              held6 == [39, 38] and '38 طيرًا' in said6 and '39' not in said6, (held6, said6))
        c6.close()

        check('zero page errors overall', not ERRS, '; '.join(ERRS[:2]))
        b.close()
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
