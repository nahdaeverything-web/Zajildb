#!/usr/bin/env python3
"""PLACEHOLDER PARENTS (RULED 2026-11-23, src/family.js). «إضافة شقيق/شقيقة» on a bird with no recorded parents makes
two records for the unknown father and mother, so that both birds can point to them — kinship is derived from shared
sireId / damId and from nothing else. Until this change set they were ordinary reference birds: rows in the bird list,
counted, offered by every picker, reachable by typing «أب غير معروف», and printed under the name they were given in
whatever language the app was in. Now they carry `placeholder: true` (always with external: true; missing means false):

  item 1  the flag is set where the two records are made
  item 2  no row in the bird list or anything fed by it; not in the bird counts; two placeholder parents are not a
          recorded pedigree in the statistics
  item 3  no picker offers, matches or returns one — typing the label creates or offers nothing that exists
  item 4  the pedigree, the profile's mini pedigree, the certificate and its parent photo boxes read «غير معروف» /
          "Unknown" from the flag, in the language of the screen, and stay a link to the record's edit form
  item 5  the flag clears when the form saves the record with a ring, or with another name
  item 6  deleting a bird deletes a placeholder parent left with no other child, in the same transaction, with its
          own tombstone — and the undo restores it
  item 7  the duplicate-ring search and the integrity check still see them

The sign-in gate's count and the CLEAR question's count are asserted in screens/gate.py, which has the stub backend.
Fixture names are invented; nothing is configured, so nothing leaves the page.

    python3 tests/e2e/screens/placeholders.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import os, re, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _typography import SCAN                 # noqa: E402
passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:460]) if not ok and d != '' else ''}")
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))

SIRE, DAM = 'أب غير معروف', 'أم غير معروفة'          # the names the app stores, in Arabic (bird.unknownSire / bird.unknownDam)
SEED = """async (db) => {
    const loftId = db.currentLoft() && db.currentLoft().id;
    const mk = async (name, sex, extra = {}) => (await db.saveBird(db.newBird({ name, sex, loftId, ...extra }))).id;
    const ring = (raw) => ({ raw, type: 'national', country: 'JO', year: 2026, serial: raw.split('-')[2] });
    const ids = { najm: await mk('نجم', 'cock'), raad: await mk('رعد', 'cock', { rings: [ring('JO-2026-100001')] }), hadeel: await mk('هديل', 'hen'),
                  ref: await mk('جد مرجعي', 'cock', { external: true }) };
    const pair = await db.Pairs.save({ sireId: ids.raad, damId: ids.hadeel, season: '2026', nestBox: '3', status: 'active', loftId,
      rounds: [{ id: db.uuid(), number: 1, eggs: [{ id: db.uuid(), laidDate: '2026-03-01', state: 'hatched', hatchDate: '2026-03-19', chickId: null }] }] });
    ids.pair = pair.id;
    await db.Health.save({ id: db.uuid(), eventType: 'vaccination', wholeLoft: true, birdId: null, loftId, date: '2026-02-01', medication: '', notes: '' });
    await db.Races.save({ id: db.uuid(), birdId: ids.raad, loftId, date: '2026-04-01', raceName: 'سباق', raceType: 'race', distanceKm: 200, velocity: 1200, position: 4, birdsEntered: 50 });
    return ids; }"""
FAMILY = """async (db, id) => { const x = db.getBird(id); const sib = db.allBirds().find(b => b.id !== id && b.sireId && b.sireId === x.sireId && !b.placeholder && b.name === 'سحابة');
    const view = (b) => b ? { id: b.id, name: b.name, placeholder: b.placeholder, external: b.external, status: b.status, hasKey: Object.prototype.hasOwnProperty.call(b, 'placeholder') } : null;
    return { sib: sib ? sib.id : null, sire: view(db.getBird(x.sireId)), dam: view(db.getBird(x.damId)), same: !!sib && sib.sireId === x.sireId && sib.damId === x.damId }; }"""
REC = """async (db, id) => { const b = db.getBird(id); return b ? { name: b.name, placeholder: b.placeholder, hasKey: Object.prototype.hasOwnProperty.call(b, 'placeholder'), external: b.external, status: b.status, sireId: b.sireId, damId: b.damId, rings: (b.rings || []).map(r => r.raw) } : null; }"""
NODES = """() => [...document.querySelectorAll('[data-testid=node],[data-testid=node-subject]')].map(e => ({ gen: e.dataset.gen, known: e.dataset.known, ph: e.dataset.placeholder || null,
    common: e.dataset.common || null, dot: !!e.querySelector('i'), tag: e.tagName, href: e.getAttribute('href'), text: e.innerText.trim().replace(/\\s+/g, ' ') }))"""

def wait(pg, js, ms=8000):
    try: pg.wait_for_function(js, timeout=ms); return True
    except Exception: return False
def texts(pg, sel): return [x.strip() for x in pg.locator(sel).all_inner_texts()]
def text(pg, sel): return pg.evaluate("(s) => { const e = document.querySelector(s); return e ? e.innerText.trim().replace(/\\s+/g, ' ') : null; }", sel)
def click(pg, sel, ms=6000):
    try: pg.click(sel, timeout=ms); return True
    except Exception: return False
def fill(pg, sel, v, ms=6000):
    try: pg.fill(sel, v, timeout=ms); pg.wait_for_timeout(250); return True
    except Exception: return False

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e, _p=pg: errs.append(perr(e, _p)))
        def go(path, sel=None, ms=10000):
            pg.goto(ROOT + path, wait_until='load')
            if sel:
                try: pg.wait_for_selector(sel, timeout=ms)
                except Exception: return False
            return True
        def delete_from_profile(bid):
            """The profile's own «حذف»: menu, the question, the destructive answer. True when the list came back."""
            go(f'bird/?id={bid}', '[data-testid=profile-hero]'); click(pg, '[data-testid=options-menu]'); click(pg, '[data-testid=menu-delete]')
            wait(pg, "() => document.querySelector('[data-testid=dialog]')"); click(pg, '[data-testid=dialog-confirm]')
            return wait(pg, "() => /\\/birds\\/?$/.test(location.pathname)")
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_function('window.__zajilReady')
        ids = run(pg, SEED)

        # ══ item 1 — the existing «إضافة شقيق/شقيقة» sets the flag where it makes the two records ══
        go(f"bird/?id={ids['najm']}", '[data-testid=profile-hero]')
        click(pg, '[data-testid=options-menu]'); click(pg, '[data-testid=menu-add-sibling]'); wait(pg, "() => document.querySelector('[data-testid=dialog]')")
        click(pg, '[data-testid=dialog-confirm]'); wait(pg, "() => document.querySelector('[data-testid=bird-form]')")
        fill(pg, '[data-testid=f-name]', 'سحابة'); click(pg, '[data-testid=sex-btn][data-sex=hen]'); click(pg, '[data-testid=save-btn]')
        wait(pg, "() => /\\/bird\\/\\?id=/.test(location.href)")
        fam = run(pg, FAMILY, ids['najm']); ps, pd = fam['sire'] or {}, fam['dam'] or {}
        ids['sahaba'], ids['ps'], ids['pd'] = fam['sib'], ps.get('id'), pd.get('id')
        check('[item 1 · M-noflag fails here] «إضافة شقيق/شقيقة» makes the two parents with placeholder: true, each external and with the reference status, and links both birds to them',
              fam['same'] and ps.get('placeholder') is True and pd.get('placeholder') is True and ps.get('external') is True and pd.get('external') is True
              and ps.get('status') == 'reference' and pd.get('status') == 'reference' and (ps.get('name'), pd.get('name')) == (SIRE, DAM), fam)
        fac = run(pg, "async (db) => { const a = db.newBird({ placeholder: true }), n = db.newBird({}); return { ext: a.external, st: a.status, ph: a.placeholder, plainHasKey: Object.prototype.hasOwnProperty.call(n, 'placeholder'), isA: db.isPlaceholder(a), isN: db.isPlaceholder(n), isNull: db.isPlaceholder(null) }; }")
        check('[item 1] the factory: a placeholder is always external with the reference status; an ordinary bird carries no such key, and missing means false',
              fac == {'ext': True, 'st': 'reference', 'ph': True, 'plainHasKey': False, 'isA': True, 'isN': False, 'isNull': False}, fac)

        # ══ item 2 — the bird list and everything fed by it ══
        go('birds/', '[data-testid=bird-row]'); pg.wait_for_timeout(300)
        rows = texts(pg, '[data-testid=row-name]'); line = text(pg, '[data-testid=count-line]')
        total = run(pg, "async (db) => db.allBirds().length")
        check('[item 2 · list · M-list fails here] the bird list has a row for each of the five birds and none for a placeholder parent — the register holds seven records',
              sorted(rows) == sorted(['نجم', 'سحابة', 'رعد', 'هديل', 'جد مرجعي']) and total == 7, (rows, total))
        check('[item 2 · list] …the count line counts what the list shows: «5 طائرًا · 3 ذكرًا · 2 أنثى»', line == '5 طائرًا · 3 ذكرًا · 2 أنثى', line)
        click(pg, '[data-testid=filter-pill][data-filter=ext]'); pg.wait_for_timeout(250); ext_rows = texts(pg, '[data-testid=row-name]')
        check('[item 2 · list] …«خارجي» shows the ordinary reference bird, which is NOT hidden, and no placeholder', ext_rows == ['جد مرجعي'], ext_rows)
        click(pg, '[data-testid=filter-pill][data-filter=all]'); fill(pg, '[data-testid=search-input]', 'غير معروف'); found = texts(pg, '[data-testid=row-name]')
        check('[item 2 · list] …and searching «غير معروف» finds no row', found == [] and pg.locator('[data-testid=year-label]').count() == 1, found)

        # ── the restore list's «{n} طيرًا» for a snapshot ──
        snap_birds = run(pg, "async (db) => { await db.autoBackup(); const all = await db.listBackups(); return all[0].payload.birds.length; }")
        go('tools/restore/', '[data-testid=snap-row]'); pg.wait_for_timeout(400)
        meta = pg.evaluate("() => { const r = document.querySelector('[data-testid=snap-row] span > div'); return r ? r.innerText.trim() : null; }")
        check('[item 2 · count · M-backup fails here] الأدوات → «استرجاع»: a snapshot is counted without its placeholder parents — «5 طيرًا» for a snapshot that holds 7 records',
              meta == '5 طيرًا' and snap_birds == 7, (meta, snap_birds))

        # ── the statistics: two placeholder parents are not a recorded pedigree; one placeholder beside a recorded parent is ──
        ids['half'] = run(pg, "async (db, s, d) => (await db.saveBird(db.newBird({ name: 'فرخ بأم معروفة', sex: 'cock', loftId: db.currentLoft().id, sireId: s, damId: d }), { allowWarnings: true })).id", ids['ps'], ids['hadeel'])
        go('stats/', '[data-testid=coi-scope]'); pg.wait_for_timeout(300)
        scope = text(pg, '[data-testid=coi-scope]'); sline = text(pg, '[data-testid=count-line]') or ''
        unk = pg.evaluate("() => { const r = document.querySelector('[data-testid=coi-bars] [data-testid=bar-row][data-kind=unk]'); return r ? r.innerText.replace(/\\s+/g, ' ').trim() : null; }")
        check('[item 2 · stats · M-stats fails here] نجم and سحابة, whose parents are both placeholders, have NO recorded pedigree: «محسوب لـ 1 طيرًا بنسب مسجل من أصل 5» — the one is the bird with a recorded mother',
              scope == 'محسوب لـ 1 طيرًا بنسب مسجل من أصل 5', scope)
        check('[item 2 · stats] …the four others are in the «نسب غير معروف» row, and the statistics count 5 birds', bool(unk) and 'نسب غير معروف' in unk and '4' in unk and sline.startswith('5 طيرًا'), (unk, sline))

        # ══ item 3 — the six pickers ══
        def probe(name, input_sel, item_sel, real='نجم'):
            """Type the placeholder label, then a real bird's name: (candidates for the label, «exists» notes, candidates for the real name)."""
            ok = fill(pg, input_sel, 'غير معروف'); n_ph = pg.locator(item_sel).count(); notes = pg.locator('[data-testid=picker-note]').count()
            fill(pg, input_sel, real); n_real = pg.locator(item_sel).count()
            fill(pg, input_sel, ''); listed = ' | '.join(texts(pg, item_sel))
            return ok, n_ph, notes, n_real, listed
        go('bird/new/', '[data-testid=bird-form]'); click(pg, '[data-testid=parent-sire-pick]')
        got = probe('form', '[data-testid=picker-input]', '[data-testid=picker-item]')
        check('[item 3 · the label · M-pick fails here] the bird form\'s father picker: typing «غير معروف» offers no bird and no «موجود» note; «نجم» is found; the open list holds no placeholder',
              got[0] and got[1] == 0 and got[2] == 0 and got[3] == 1 and 'غير معروف' not in got[4] and 'رعد' in got[4], got)
        click(pg, '[data-testid=parent-sire-create]'); fill(pg, '[data-testid=picker-input]', SIRE)
        can = pg.evaluate("() => { const c = document.querySelector('[data-testid=picker-create]'); return c ? !c.disabled : null; }"); note = pg.locator('[data-testid=picker-note]').count()
        click(pg, '[data-testid=picker-create]'); wait(pg, "() => document.querySelector('[data-testid=parent-sire-name]')")
        made = run(pg, "async (db, ph, name) => { const same = db.allBirds().filter(b => b.name === name); const fresh = same.find(b => b.id !== ph); return { n: same.length, fresh: fresh ? { ph: fresh.placeholder === true, ext: fresh.external } : null, id: fresh ? fresh.id : null }; }", ids['ps'], SIRE)
        check('[item 3 · the label · M-create fails here] typing the stored label «أب غير معروف» and pressing «إنشاء» makes a NEW reference bird of that name — the placeholder is neither offered nor returned',
              can is True and note == 0 and made['n'] == 2 and made['fresh'] == {'ph': False, 'ext': True} and text(pg, '[data-testid=parent-sire-name]') == SIRE, (can, note, made))
        if made.get('id'): run(pg, "async (db, id) => { await db.deleteBird(id); }", made['id'])      # the stub that press made; the form is abandoned

        go('breeding/', '[data-testid=new-pair-fab]'); click(pg, '[data-testid=new-pair-fab]'); wait(pg, "() => document.querySelector('[data-testid=sheet-new]')")
        click(pg, '[data-testid=f-sire-btn]'); s_ = probe('pair sire', '[data-testid=f-sire-input]', '[data-testid=f-sire-item]')
        click(pg, '[data-testid=f-dam-btn]'); d_ = probe('pair dam', '[data-testid=f-dam-input]', '[data-testid=f-dam-item]', real='هديل')
        check('[item 3 · new pair] «زوج جديد»: neither the father picker nor the mother picker offers a placeholder; each finds a real bird',
              s_[0] and d_[0] and (s_[1], s_[2], s_[3]) == (0, 0, 1) and (d_[1], d_[2], d_[3]) == (0, 0, 1) and 'غير معروف' not in s_[4] + d_[4], (s_, d_))
        go(f"pair/?id={ids['pair']}", '[data-testid=egg-link]'); click(pg, '[data-testid=egg-link]'); wait(pg, "() => document.querySelector('[data-testid=sheet-link]')")
        click(pg, '[data-testid=f-link-btn]'); l_ = probe('link', '[data-testid=f-link-input]', '[data-testid=f-link-item]')
        check('[item 3 · link a chick] «ربط طير مسجَّل»: no placeholder is offered as the chick', l_[0] and (l_[1], l_[2], l_[3]) == (0, 0, 1) and 'غير معروف' not in l_[4], l_)
        go('health/', '[data-testid=new-event-fab]'); click(pg, '[data-testid=new-event-fab]'); wait(pg, "() => document.querySelector('[data-testid=event-sheet]')")
        click(pg, '[data-testid=bird-pick]'); h_ = probe('health', '[data-testid=bird-search]', '[data-testid=bird-item]')
        check('[item 3 · health] the health event\'s bird picker offers no placeholder', h_[0] and (h_[1], h_[3]) == (0, 1) and 'غير معروف' not in h_[4], h_)
        go('races/', '[data-testid=new-result-fab]'); click(pg, '[data-testid=new-result-fab]'); wait(pg, "() => document.querySelector('[data-testid=result-sheet]')")
        click(pg, '[data-testid=bird-pick]'); r_ = probe('races', '[data-testid=bird-search]', '[data-testid=bird-item]')
        check('[item 3 · races] the race result\'s bird picker offers no placeholder', r_[0] and (r_[1], r_[3]) == (0, 1) and 'غير معروف' not in r_[4], r_)
        go(f"pedigree/?id={ids['raad']}", '[data-testid=finder-input]')
        fill(pg, '[data-testid=finder-input]', 'غير معروف'); f_ph = pg.locator('[data-testid=finder-item]').count()
        fill(pg, '[data-testid=finder-input]', 'نجم'); f_real = pg.locator('[data-testid=finder-item]').count()
        check('[item 3 · relationship finder · M-finder fails here] the pedigree screen\'s relationship finder offers no placeholder', (f_ph, f_real) == (0, 1), (f_ph, f_real))

        # ══ item 4 — «غير معروف» from the flag, in the language of the screen; a link to the record's edit form ══
        go(f"pedigree/?id={ids['sahaba']}", '[data-testid=chart]'); pg.wait_for_timeout(300)
        nodes = pg.evaluate(NODES); g1 = [n for n in nodes if n['gen'] == '1']; chart = text(pg, '[data-testid=chart]') or ''
        check('[item 4 · pedigree · M-ped fails here] سحابة\'s two parents read «غير معروف» — the stored names «أب غير معروف» / «أم غير معروفة» are nowhere in the chart',
              [n['text'] for n in g1] == ['غير معروف', 'غير معروف'] and all(n['ph'] == '1' for n in g1) and SIRE not in chart and DAM not in chart, g1)
        check('[item 4 · pedigree] …each stays a link, to ITS OWN edit form', [n['tag'] for n in g1] == ['A', 'A'] and [n['href'] for n in g1] == [f"/bird/edit/?id={ids['ps']}", f"/bird/edit/?id={ids['pd']}"], [n['href'] for n in g1])
        ty = [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]
        check('[item 4 · pedigree] …in a face that has Arabic', not ty, ty[:3])
        ids['kid'] = run(pg, "async (db, s, d) => (await db.saveBird(db.newBird({ name: 'حفيد', sex: 'cock', loftId: db.currentLoft().id, sireId: s, damId: d }), { allowWarnings: true })).id", ids['najm'], ids['sahaba'])
        go(f"pedigree/?id={ids['kid']}&gens=3", '[data-testid=chart]'); pg.wait_for_timeout(300)
        g2 = [n for n in pg.evaluate(NODES) if n['gen'] == '2']
        check('[item 4 · pedigree] a placeholder that is a common ancestor keeps the common-ancestor dot: the four grandparents of the offspring of نجم × سحابة',
              len(g2) == 4 and all(n['ph'] == '1' and n['common'] == '1' and n['dot'] and n['text'] == 'غير معروف' for n in g2), g2)
        go(f"bird/?id={ids['sahaba']}&tab=ped", '[data-testid=mini-node]'); pg.wait_for_timeout(300)
        mini = pg.evaluate("() => [...document.querySelectorAll('[data-testid=mini-node][data-placeholder]')].map(e => ({ href: e.getAttribute('href'), text: e.innerText.trim().replace(/\\s+/g, ' ') }))")
        panel = text(pg, '[data-testid=panel-ped]') or ''
        check('[item 4 · profile · M-mini fails here] the profile\'s mini pedigree: «الأب غير معروف» and «الأم غير معروف» — the role, then the label; no stored name; each a link to its edit form',
              [m['text'] for m in mini] == ['الأب غير معروف', 'الأم غير معروف'] and [m['href'] for m in mini] == [f"/bird/edit/?id={ids['ps']}", f"/bird/edit/?id={ids['pd']}"] and DAM not in panel, mini)
        go(f"cert/?id={ids['sahaba']}", '[data-testid=sheet-node]'); pg.wait_for_timeout(500)
        sheet = pg.evaluate("() => [...document.querySelector('[data-testid=sheet-node]').closest('[data-testid=sheet], body').querySelectorAll('[data-testid=sheet-node]')].slice(0, 2).map(e => ({ rec: e.dataset.recorded, ph: e.dataset.placeholder || null, text: e.innerText.trim().replace(/\\s+/g, ' ') }))")
        whole = pg.evaluate("() => document.body.innerText")
        check('[item 4 · certificate · M-cert fails here] the certificate prints «غير معروف» for both parents, marked not recorded; the stored names are nowhere on the screen',
              sheet == [{'rec': 'no', 'ph': '1', 'text': 'غير معروف'}, {'rec': 'no', 'ph': '1', 'text': 'غير معروف'}] and SIRE not in whole and DAM not in whole, sheet)
        who = [text(pg, f'[data-testid=who-{w}]') for w in ('sire', 'dam')]
        check('[item 4 · certificate photo boxes · M-certbox fails here] …and the two parent photo boxes are labelled «غير معروف»', who == ['غير معروف', 'غير معروف'], who)
        ty = [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]
        check('[item 4 · certificate] …in a face that has Arabic', not ty, ty[:3])
        # the language of the screen, not of the day the record was made
        run(pg, "async (db) => { await db.setSetting('lang', 'en'); }")
        go(f"pedigree/?id={ids['sahaba']}", '[data-testid=chart]'); pg.wait_for_timeout(400)
        en1 = [n['text'] for n in pg.evaluate(NODES) if n['gen'] == '1']
        go(f"bird/?id={ids['sahaba']}&tab=ped", '[data-testid=mini-node]'); pg.wait_for_timeout(300)
        en2 = pg.evaluate("() => [...document.querySelectorAll('[data-testid=mini-node][data-placeholder]')].map(e => e.innerText.trim().replace(/\\s+/g, ' '))")
        stored = run(pg, "async (db, a, b) => [(db.getBird(a) || {}).name, (db.getBird(b) || {}).name]", ids['ps'], ids['pd'])
        check('[item 4 · language · M-ped fails here too] with the app in English the same boxes read "Unknown" — while the records still hold «أب غير معروف» and «أم غير معروفة»',
              en1 == ['Unknown', 'Unknown'] and all(x.endswith('Unknown') for x in en2) and len(en2) == 2 and stored == [SIRE, DAM], (en1, en2, stored))
        run(pg, "async (db) => { await db.setSetting('lang', 'ar'); }")

        # ══ item 6 — a second family, made directly: بدر and قمر, two placeholder parents, and the father's own placeholder mother ══
        fam2 = run(pg, """async (db) => { const loftId = db.currentLoft().id;
            const g = await db.saveBird(db.newBird({ name: 'أم غير معروفة', sex: 'hen', placeholder: true }));
            const p3 = await db.saveBird(db.newBird({ name: 'أب غير معروف', sex: 'cock', placeholder: true, damId: g.id }));
            const p4 = await db.saveBird(db.newBird({ name: 'أم غير معروفة', sex: 'hen', placeholder: true }));
            const x = await db.saveBird(db.newBird({ name: 'بدر', sex: 'cock', loftId, sireId: p3.id, damId: p4.id }));
            const y = await db.saveBird(db.newBird({ name: 'قمر', sex: 'hen', loftId, sireId: p3.id, damId: p4.id }));
            return { g: g.id, p3: p3.id, p4: p4.id, x: x.id, y: y.id }; }""")
        HOLD = """async (db, ids) => { const idb = await new Promise((res, rej) => { const r = indexedDB.open('zajil'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
            const all = (n) => new Promise((res) => { const q = idb.transaction(n).objectStore(n).getAll(); q.onsuccess = () => res(q.result); });
            const stored = new Set((await all('birds')).map(b => b.id)); const tombs = new Set((await all('tombstones')).map(t => t.id)); const ops = (await all('oplog')).sort((a, b) => a.seq - b.seq); idb.close();
            const out = {}; for (const [k, id] of Object.entries(ids)) { const b = db.getBird(id);
              out[k] = { mem: !!b, stored: stored.has(id), tomb: tombs.has('birds:' + id), ph: b ? b.placeholder === true : null, sire: b ? b.sireId : null, dam: b ? b.damId : null }; }
            out.tail = ops.slice(-4).map(o => [o.store, o.op, Object.keys(ids).find(k => ids[k] === o.recordId) || '?', o.seq]); return out; }"""
        ok1 = delete_from_profile(fam2['y']); h1 = run(pg, HOLD, fam2)
        check('[item 6 · M-greedy fails here] deleting قمر, one of two siblings, leaves both placeholder parents and the placeholder grandmother: بدر still names them',
              ok1 and not h1['y']['mem'] and all(h1[k]['mem'] and h1[k]['stored'] and not h1[k]['tomb'] for k in ('x', 'p3', 'p4', 'g')), h1)
        ok2 = delete_from_profile(fam2['x']); h2 = run(pg, HOLD, fam2)
        check('[item 6 · M-noorphan fails here] deleting بدر, the last sibling, deletes the two placeholder parents left with no child — and the father\'s own placeholder mother: none is in memory or in storage',
              ok2 and all(not h2[k]['mem'] and not h2[k]['stored'] for k in ('x', 'p3', 'p4', 'g')), h2)
        seqs = [t[3] for t in h2['tail']]
        check('[item 6] …each with its own tombstone, and its own deletion logged with the bird\'s: four consecutive operations — بدر, then the three placeholders',
              all(h2[k]['tomb'] for k in ('x', 'p3', 'p4', 'g')) and [t[:3] for t in h2['tail']] == [['birds', 'delete', 'x'], ['birds', 'delete', 'p3'], ['birds', 'delete', 'p4'], ['birds', 'delete', 'g']]
              and seqs == list(range(seqs[0], seqs[0] + 4)), h2['tail'])
        click(pg, '[data-testid=toast-action]'); wait(pg, "() => [...document.querySelectorAll('[data-testid=row-name]')].some(r => r.textContent.trim() === 'بدر')"); pg.wait_for_timeout(300)
        h3 = run(pg, HOLD, fam2)
        check('[item 6 · undo · M-noundo fails here] «تراجع» restores بدر AND the three placeholders: in memory and in storage, still placeholders, the tombstones gone',
              all(h3[k]['mem'] and h3[k]['stored'] and not h3[k]['tomb'] for k in ('x', 'p3', 'p4', 'g')) and all(h3[k]['ph'] for k in ('p3', 'p4', 'g')), h3)
        check('[item 6 · undo] …with the links as they were: بدر names both parents, the father names his mother',
              h3['x']['sire'] == fam2['p3'] and h3['x']['dam'] == fam2['p4'] and h3['p3']['dam'] == fam2['g'], (h3['x'], h3['p3']))
        dangling = pg.evaluate("() => { const db = window.__zajilDb, e = window.__zajilEngine; return e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents, lofts: db.state.lofts }).length; }")
        check('[item 6] …and the register is referentially clean after the delete and its undo', dangling == 0, dangling)

        # ══ item 7 — NOT hidden from the duplicate-ring search or the integrity check ══
        # a record a mutant has taken away is not written to: every step below reads what is there and says so in its check
        run(pg, "async (db, id) => { const b = db.getBird(id); if (b) await db.saveBird({ ...b, rings: [{ raw: 'JO-2026-100001', type: 'national', country: 'JO', year: 2026, serial: '100001' }] }, { allowWarnings: true }); }", fam2['p3'])
        still = run(pg, REC, fam2['p3'])
        warn = run(pg, "async (db, id) => db.checkBird(db.getBird(id)).warnings.map(w => [w.key, w.params.otherId])", ids['raad'])
        go('tools/duplicates/', None); wait(pg, "() => /JO-2026-100001|100001/.test(document.body.innerText)", 8000); dup = pg.evaluate("() => document.body.innerText")
        check('[item 7 · M-dupblind fails here] a placeholder given a ring another bird carries is still a placeholder, and the duplicate-ring search still finds it: the save check warns, and الأدوات lists the ring',
              still and still['placeholder'] is True and warn == [['val.dupRing', fam2['p3']]] and '100001' in dup and 'رعد' in dup, (still, warn))
        run(pg, "async (db, id) => { const b = db.getBird(id); if (b) await db.saveBird({ ...b, rings: [], sireId: 'no-such-bird' }, { force: true }); }", fam2['p3'])
        found = pg.evaluate("() => { const db = window.__zajilDb, e = window.__zajilEngine; return e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents, lofts: db.state.lofts }).map(x => [x.key, JSON.stringify(x.params)]); }")
        check('[item 7] …and the integrity check still reads placeholders: a placeholder naming a father that does not exist is reported', len(found) == 1 and fam2['p3'] in found[0][1], found)
        run(pg, "async (db, id) => { const b = db.getBird(id); if (b) await db.saveBird({ ...b, sireId: null }, { force: true }); }", fam2['p3'])

        # ══ item 5 — the flag clears when the FORM saves the record with a ring, or with another name ══
        def edit_save(bid, do=None):
            go(f'bird/edit/?id={bid}', '[data-testid=bird-form]'); pg.wait_for_timeout(200)
            if do: do()
            click(pg, '[data-testid=save-btn]')
            if wait(pg, "() => document.querySelector('[data-testid=dialog]') || /\\/bird\\/\\?id=/.test(location.href)", 6000) and pg.locator('[data-testid=dialog]').count(): click(pg, '[data-testid=dialog-confirm]')
            wait(pg, "() => /\\/bird\\/\\?id=/.test(location.href)", 6000); return run(pg, REC, bid)
        r0 = edit_save(ids['ps'])
        check('[item 5] saved through the form with nothing changed, a placeholder stays one', r0 and r0['placeholder'] is True and r0['name'] == SIRE, r0)
        r1 = edit_save(ids['ps'], lambda: fill(pg, '[data-testid=ring-input] >> nth=0', 'JO-2020-555001'))
        go('birds/', '[data-testid=bird-row]'); pg.wait_for_timeout(300); rows = texts(pg, '[data-testid=row-name]')
        check('[item 5 · a ring · M-noclear fails here] saved through the form with a ring, it is no longer a placeholder: the key is gone, it is still a reference bird, and the bird list has its row',
              r1 and r1['hasKey'] is False and r1['rings'] == ['JO-2020-555001'] and r1['external'] is True and r1['status'] == 'reference' and SIRE in rows, (r1, rows))
        r2 = edit_save(ids['pd'], lambda: fill(pg, '[data-testid=f-name]', 'أم نجم'))
        check('[item 5 · another name · M-noclearname fails here] saved through the form under another name, it is no longer a placeholder', r2 and r2['hasKey'] is False and r2['name'] == 'أم نجم' and r2['external'] is True, r2)
        r3 = edit_save(fam2['p4'], lambda: click(pg, '[data-testid=external-switch]'))
        check('[item 5 · PROPOSED, not ruled] saved through the form as a bird of the loft (external switched off), it is no longer a placeholder — the flag never stays without external',
              r3 and r3['hasKey'] is False and r3['external'] is False, r3)
        go(f"pedigree/?id={ids['sahaba']}", '[data-testid=chart]'); pg.wait_for_timeout(300)
        g1 = [(n['text'], n['known'], n['href']) for n in pg.evaluate(NODES) if n['gen'] == '1']
        check('[item 5] …and the pedigree now prints them as the recorded birds they are, linked to their profiles',
              [x[1] for x in g1] == ['1', '1'] and SIRE in g1[0][0] and 'أم نجم' in g1[1][0] and g1[0][2] == f"/bird/?id={ids['ps']}", g1)

        check('zero page errors overall', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
