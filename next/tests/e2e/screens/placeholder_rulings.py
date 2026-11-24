#!/usr/bin/env python3
"""PLACEHOLDER PARENTS — THE RULINGS OF 2026-11-24 (commit 3 on the sibling/clutch work; src/family.js, src/db/records.js).

  B2  one display helper (placeholderName): a box of the tree, the mini pedigree or the certificate reads «غير معروف»;
      everywhere else that prints a bird's name reads «أب غير معروف» / «أم غير معروفة» by sex — from the flag and the
      language of the screen, never the stored name
  B3  a placeholder is not a known ancestor: the pedigree's two tiles and the completeness figures count without it;
      the coefficient of inbreeding and AVK are not changed
  B4  a save that changes or clears a parent and leaves a placeholder with no child deletes it in the same
      transaction, with a tombstone — and its own placeholder parents in turn
  B5  a placeholder that holds anything of its own is never deleted that way (nor by a deletion): its flag is cleared
      and it stays, a reference bird the register lists
  B6  a held sibling link whose other bird no longer exists stops the save, names the bird, and writes nothing
  C3  (RULED 2026-11-24, later) a placeholder's own edit form: the name field shows empty with the display label as its
      hint; any name typed, or a ring, clears the flag on save; saved with the field still empty it stays a placeholder

B1 and B7 — the counts of the teaching-data removal, the import, the replace and the loaders — are in
screens/placeholder_counts.py. Fixture names are invented; nothing is configured, so nothing leaves the page.

    python3 tests/e2e/screens/placeholder_rulings.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import os, sys
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

SIRE, DAM, BOX = 'أب غير معروف', 'أم غير معروفة', 'غير معروف'
HELPERS = """const loftId = db.currentLoft() && db.currentLoft().id;
    const mk = async (name, sex, extra = {}) => (await db.saveBird(db.newBird({ name, sex, loftId, ...extra }), { allowWarnings: true })).id;
    const ph = async (name, sex, extra = {}) => (await db.saveBird(db.newBird({ name, sex, placeholder: true, ...extra }))).id;
    const ring = (raw) => ({ raw, type: 'national', country: 'JO', year: +raw.split('-')[1], serial: raw.split('-')[2] });"""
SEED = "async (db) => { " + HELPERS + """
    const ids = {};
    ids.jad = await mk('جد مرجعي', 'cock', { external: true });
    ids.sultan = await mk('سلطان', 'cock');
    ids.raad = await mk('رعد', 'cock', { rings: [ring('JO-2026-100001')] }); ids.hadeel = await mk('هديل', 'hen');
    ids.saqr = await mk('صقر', 'cock', { sireId: ids.raad, damId: ids.hadeel });
    // the first family: the father's record was made while the app was in ENGLISH, the mother's in ARABIC — so in either
    // language one of the two proves that what is stored is not what is shown
    ids.ps = await ph('Unknown sire', 'cock'); ids.pd = await ph('أم غير معروفة', 'hen');
    ids.najm = await mk('نجم', 'cock', { sireId: ids.ps, damId: ids.pd }); ids.sahaba = await mk('سحابة', 'hen', { sireId: ids.ps, damId: ids.pd });
    ids.chick = await mk('فرخ الأشقاء', 'cock', { sireId: ids.najm, damId: ids.sahaba });       // the offspring of two full siblings
    ids.pg1 = await ph('أب غير معروف', 'cock', { sireId: ids.jad });                            // a placeholder father whose own father IS recorded
    ids.hafeed = await mk('حفيد', 'cock', { sireId: ids.pg1 });
    ids.pu = await ph('أب غير معروف', 'unknown');                                               // one whose sex is not recorded
    return ids; }"""
B4SEED = "async (db, sultan) => { " + HELPERS + """
    const pg = await ph('أم غير معروفة', 'hen');                      // the placeholder father's own placeholder mother
    // ياسر's placeholder father was made while the app was in English; the question about him is asked in Arabic
    const pa = await ph('أب غير معروف', 'cock', { damId: pg }); const pb = await ph('أم غير معروفة', 'hen');
    const waheed = await mk('وحيد', 'cock', { sireId: pa, damId: pb }); const rafeeq = await mk('رفيق', 'cock', { sireId: pa });
    const pc = await ph('Unknown sire', 'cock'); const yasser = await mk('ياسر', 'cock', { sireId: pc }); const mazen = await mk('مازن', 'cock', { sireId: sultan });
    const pn = await ph('أم غير معروفة', 'hen'); await db.saveBird({ ...db.getBird(pn), colour: 'أزرق' }); const munfarid = await mk('منفرد', 'cock', { damId: pn });
    return { pg, pa, pb, waheed, rafeeq, pc, yasser, mazen, pn, munfarid }; }"""
# every record named, as memory and storage hold it now — read, never written; a record a mutant took away reads as absent
HOLD = """async (db, ids) => { const idb = await new Promise((res, rej) => { const r = indexedDB.open('zajil'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
    const all = (n) => new Promise((res) => { const q = idb.transaction(n).objectStore(n).getAll(); q.onsuccess = () => res(q.result); });
    const stored = new Map((await all('birds')).map(b => [b.id, b])); const tombs = new Set((await all('tombstones')).map(t => t.id)); const ops = (await all('oplog')).length; idb.close();
    const out = { ops, birds: db.allBirds().length, listed: db.listedBirds().length };
    for (const [k, id] of Object.entries(ids)) { const b = db.getBird(id); const s = stored.get(id);
      out[k] = { mem: !!b, stored: !!s, tomb: tombs.has('birds:' + id), ph: b ? b.placeholder === true : null, hasKey: b ? Object.prototype.hasOwnProperty.call(b, 'placeholder') : null,
                 storedKey: s ? Object.prototype.hasOwnProperty.call(s, 'placeholder') : null, external: b ? b.external : null, status: b ? b.status : null,
                 sire: b ? (b.sireId || null) : null, dam: b ? (b.damId || null) : null, colour: b ? (b.colour || '') : null, at: b ? b.updatedAt : null, listed: db.listedBirds().some(x => x.id === id) }; }
    return out; }"""
# what one IndexedDB transaction wrote: every put and delete, tagged with the transaction it ran in
PROBE = """() => { if (window.__idbLog) { window.__idbLog.length = 0; return; } const log = window.__idbLog = []; let n = 0; const seen = new WeakMap();
    const tid = (tx) => { if (!seen.has(tx)) seen.set(tx, ++n); return seen.get(tx); };
    for (const m of ['put', 'delete']) { const orig = IDBObjectStore.prototype[m];
      IDBObjectStore.prototype[m] = function (...a) { const v = a[0]; log.push([this.name, m, tid(this.transaction), m === 'put' ? ((v && (v.id || v.recordId || v.key)) || null) : v]); return orig.apply(this, a); }; } }"""
def tids(log, *wanted):
    """The transaction each wanted (store, op, key) write ran in — None for one that was never made."""
    return [next((e[2] for e in (log or []) if e[0] == s and e[1] == o and e[3] == k), None) for (s, o, k) in wanted]
def one_tx(found): return all(x is not None for x in found) and len(set(found)) == 1
NODES = """() => [...document.querySelectorAll('[data-testid=node],[data-testid=node-subject]')].map(e => ({ gen: e.dataset.gen, known: e.dataset.known, ph: e.dataset.placeholder || null, text: e.innerText.trim().replace(/\\s+/g, ' ') }))"""
INTEGRITY = "() => { const db = window.__zajilDb, e = window.__zajilEngine; return e.integrity.checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs, raceResults: db.state.raceResults, healthEvents: db.state.healthEvents, lofts: db.state.lofts }).length; }"

def wait(pg, js, ms=8000):
    try: pg.wait_for_function(js, timeout=ms); return True
    except Exception: return False
def texts(pg, sel): return [' '.join(x.split()) for x in pg.locator(sel).all_inner_texts()]
def text(pg, sel): return pg.evaluate("(s) => { const e = document.querySelector(s); return e ? e.innerText.trim().replace(/\\s+/g, ' ') : null; }", sel)
def click(pg, sel, ms=5000):
    try: pg.click(sel, timeout=ms); return True
    except Exception: return False
def fill(pg, sel, v, ms=5000):
    try: pg.fill(sel, v, timeout=ms); pg.wait_for_timeout(250); return True
    except Exception: return False
def faces(pg): return [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e, _p=pg: errs.append(perr(e, _p)))
        def go(path, sel, ms=10000):
            pg.goto(ROOT + path, wait_until='load')
            try: pg.wait_for_selector(sel, timeout=ms); pg.wait_for_timeout(250); return True
            except Exception: return False
        def dialog():
            d = pg.locator('[data-testid=dialog]')
            return ' / '.join(x.strip() for x in d.inner_text().split('\n') if x.strip()) if d.count() else ''
        def save():
            """Press save; say what followed within 6 s: ('dialog', text), ('page', url) or ('nothing', url)."""
            click(pg, '[data-testid=save-btn]')
            if not wait(pg, "() => document.querySelector('[data-testid=dialog]') || /\\/bird\\/\\?id=/.test(location.href)", 6000): return ('nothing', pg.url)
            return ('dialog', dialog()) if pg.locator('[data-testid=dialog]').count() else ('page', pg.url)
        def set_parent(role, q):
            """Choose a recorded bird for a parent slot, whether the slot holds one now or not."""
            if not click(pg, f'[data-testid=parent-{role}-change]', 1500): click(pg, f'[data-testid=parent-{role}-pick]', 1500)
            fill(pg, '[data-testid=picker-input]', q); ok = click(pg, '[data-testid=picker-item] >> nth=0'); pg.wait_for_timeout(200); return ok
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_function('window.__zajilReady')
        ids = run(pg, SEED)
        stored = run(pg, "async (db, a, b) => [db.getBird(a).name, db.getBird(b).name]", ids['ps'], ids['pd'])

        # ══ B2 — ONE NAME, from the flag and the language of the screen ══
        go(f"bird/edit/?id={ids['najm']}", '[data-testid=bird-form]')
        slots = [text(pg, '[data-testid=parent-sire-name]'), text(pg, '[data-testid=parent-dam-name]')]
        check('[B2 · the form\'s parent slots · M-b2-name and M-b2-slot fail here] نجم\'s two slots read «أب غير معروف» and «أم غير معروفة» — the father\'s record holds "Unknown sire", and that is nowhere on the form',
              slots == [SIRE, DAM] and stored == ['Unknown sire', DAM] and 'Unknown' not in (text(pg, '[data-testid=bird-form]') or ''), (slots, stored))
        go(f"bird/?id={ids['najm']}", '[data-testid=profile-hero]')
        rows = [text(pg, '[data-testid=row-sire] a'), text(pg, '[data-testid=row-dam] a')]
        check('[B2 · the profile\'s «الأب» / «الأم» rows · M-b2-row fails here] they read «أب غير معروف» and «أم غير معروفة»', rows == [SIRE, DAM], rows)
        go(f"bird/?id={ids['najm']}&tab=ped", '[data-testid=mini-node]')
        mini = texts(pg, '[data-testid=mini-node]')
        check('[B2 · boxes · M-b2-box fails here] …while the mini pedigree\'s two parent boxes stay «غير معروف», under «الأب» and «الأم»',
              len(mini) >= 3 and mini[0] == 'نجم' and mini[1] == f'الأب {BOX}' and mini[2] == f'الأم {BOX}', mini[:3])
        heroes = []
        for k in ('ps', 'pd', 'pu'):
            go(f"bird/?id={ids[k]}&tab=ped", '[data-testid=profile-hero]'); heroes.append((text(pg, '[data-testid=hero-name]'), (texts(pg, '[data-testid=mini-node]') or [''])[0]))
        check('[B2 · its own profile · M-b2-title fails here] a placeholder\'s own profile is headed «أب غير معروف» / «أم غير معروفة» by its sex, and so is the first box of its mini pedigree',
              heroes[0] == (SIRE, SIRE) and heroes[1] == (DAM, DAM), heroes[:2])
        check('[B2 · sex not recorded] one whose sex is not recorded is headed «غير معروف»', heroes[2][0] == BOX, heroes[2])
        go(f"pedigree/?id={ids['ps']}", '[data-testid=chart]')
        own = [text(pg, '[data-testid=crumb]'), text(pg, '[data-testid=subject]'), text(pg, '[data-testid=node-subject]')]
        check('[B2 · its own pedigree page · M-b2-pedpage fails here] the page of the father\'s record names it «أب غير معروف» in the bar, the heading and the first box', own == [SIRE, f'{SIRE} ذكر', SIRE], own)
        go(f"pedigree/?id={ids['najm']}", '[data-testid=chart]')
        g1 = [(n['text'], n['ph']) for n in pg.evaluate(NODES) if n['gen'] == '1']
        check('[B2 · boxes] the tree\'s two parent boxes stay «غير معروف»', g1 == [(BOX, '1'), (BOX, '1')], g1)
        go(f"cert/?id={ids['najm']}", '[data-testid=sheet-node]')
        sheet = [' '.join(x.split()) for x in pg.locator('[data-testid=sheet-node]').all_text_contents()][:2]
        who = [text(pg, '[data-testid=who-sire]'), text(pg, '[data-testid=who-dam]')]
        check('[B2 · boxes] the certificate\'s two parent boxes and its two photo rows stay «غير معروف»', sheet == [BOX, BOX] and who == [BOX, BOX], (sheet, who))
        go(f"cert/?id={ids['ps']}", '[data-testid=sheet-node]')
        check('[B2 · its own certificate · M-b2-label fails here] the certificate of the father\'s record is headed «أب غير معروف»', text(pg, '[data-testid=crumb]') == SIRE, text(pg, '[data-testid=crumb]'))
        go(f"pedigree/?id={ids['chick']}", '[data-testid=breakdown-row]')
        common = sorted(texts(pg, '[data-testid=breakdown-row] td:first-child'))
        check('[B2 · the COI breakdown table · M-b2-biglabel fails here] the offspring of نجم × سحابة: the two common ancestors are listed as «أب غير معروف» and «أم غير معروفة»', common == sorted([SIRE, DAM]), common)

        # a validation message that names one: the father's record is given a ring (not through the form, so it stays a placeholder)
        run(pg, "async (db, id) => { const b = db.getBird(id); if (b) await db.saveBird({ ...b, rings: [{ raw: 'JO-2020-777001', type: 'national', country: 'JO', year: 2020, serial: '777001' }] }, { allowWarnings: true }); }", ids['ps'])
        go('bird/new/', '[data-testid=bird-form]'); fill(pg, '[data-testid=ring-input] >> nth=0', 'JO-2020-777001'); wait(pg, "() => document.querySelector('[data-testid=dup-warn]')", 4000)
        live = text(pg, '[data-testid=dup-warn]') or ''
        fill(pg, '[data-testid=f-name]', 'ضيف'); seen = save()
        check('[B2 · validation messages · M-b2-val fails here] a new bird given that record\'s ring: the question before saving says the ring is used by «أب غير معروف» — not by "Unknown sire"',
              seen[0] == 'dialog' and f'({SIRE})' in seen[1] and 'Unknown' not in seen[1], seen)
        check('[B2 · validation messages] …and so does the warning under the ring field while typing', SIRE in live and 'Unknown' not in live, live)
        click(pg, '[data-testid=dialog-cancel]')
        # the duplicate-ring list: a second, ordinary bird with the same ring
        ids['twin'] = run(pg, "async (db) => (await db.saveBird(db.newBird({ name: 'توأم الحلقة', sex: 'hen', loftId: db.currentLoft().id, rings: [{ raw: 'JO-2020-777001', type: 'national', country: 'JO', year: 2020, serial: '777001' }] }), { allowWarnings: true })).id")
        go('tools/duplicates/', '[data-testid=dup-copy]'); names = sorted(texts(pg, '[data-testid=dup-name]'))
        click(pg, f'[data-testid=dup-copy]:has-text("{SIRE}") [data-testid=dup-delete]', 3000); wait(pg, "() => document.querySelector('[data-testid=dialog]')", 4000); asked = dialog()
        check('[B2 · the duplicate-ring list · M-b2-dup fails here] الأدوات lists the two copies of the ring as «أب غير معروف» and «توأم الحلقة», and its delete question names «أب غير معروف»',
              names == sorted([SIRE, 'توأم الحلقة']) and SIRE in asked and 'Unknown' not in asked, (names, asked))
        click(pg, '[data-testid=dialog-cancel]')
        run(pg, "async (db, id) => { const b = db.getBird(id); if (b) await db.saveBird({ ...b, rings: [] }, { allowWarnings: true }); }", ids['ps'])
        # English: now the MOTHER's stored name is the one that is not shown
        run(pg, "async (db) => { await db.setSetting('lang', 'en'); }")
        go(f"bird/edit/?id={ids['najm']}", '[data-testid=bird-form]'); en_slots = [text(pg, '[data-testid=parent-sire-name]'), text(pg, '[data-testid=parent-dam-name]')]
        go(f"pedigree/?id={ids['najm']}", '[data-testid=chart]'); en_g1 = [n['text'] for n in pg.evaluate(NODES) if n['gen'] == '1']
        run(pg, "async (db) => { await db.setSetting('lang', 'ar'); }")
        check('[B2 · language] with the app in English the slots read "Unknown sire" and "Unknown dam" — the mother\'s record holds «أم غير معروفة» — and the boxes read "Unknown"',
              en_slots == ['Unknown sire', 'Unknown dam'] and en_g1 == ['Unknown', 'Unknown'], (en_slots, en_g1))

        # ══ B3 — A PLACEHOLDER IS NOT A KNOWN ANCESTOR ══
        def tiles(bid):
            go(f'pedigree/?id={bid}', '[data-testid=chart]')
            return [text(pg, f'[data-testid=tile-{k}]') for k in ('coi', 'ancestors', 'complete')], text(pg, '[data-testid=avk-completeness]')
        def profile(bid):
            go(f'bird/?id={bid}&tab=ped', '[data-testid=coi-line]'); return text(pg, '[data-testid=coi-line]') or '', text(pg, '[data-testid=avk-line]') or ''
        t_sahaba, _ = tiles(ids['sahaba'])
        check('[B3 · the tiles · M-b3-known and M-b3-tiles fail here] سحابة, whose parents are both placeholders: «0 سلف من 30» and «0 أجيال مكتملة»',
              t_sahaba[1:] == ['0 سلف من 30', '0 أجيال مكتملة'], t_sahaba)
        t_hafeed, _ = tiles(ids['hafeed'])
        check('[B3 · behind a placeholder] حفيد, whose placeholder father has a recorded father: that grandfather IS a known ancestor — «1 سلف من 30», and no complete generation',
              t_hafeed[1:] == ['1 سلف من 30', '0 أجيال مكتملة'], t_hafeed)
        t_saqr, _ = tiles(ids['saqr'])
        eng = run(pg, "async (db, id) => { const e = window.__zajilEngine.coi; const a4 = e.ancestorLoss(db.getBird, id, 4), a5 = e.ancestorLoss(db.getBird, id, 5), k4 = db.knownAncestors(id, 4), k5 = db.knownAncestors(id, 5); return { same4: a4.filled === k4.filled && a4.total === k4.total, same5: a5.filled === k5.filled && a5.total === k5.total && a5.completeness === k5.completeness, filled: k4.filled }; }", ids['saqr'])
        check('[B3 · no placeholder, no change] صقر, with two recorded parents: «2 سلف من 30», «1 أجيال مكتملة» — the engine\'s own count, to the digit, over four and five generations',
              t_saqr[1:] == ['2 سلف من 30', '1 أجيال مكتملة'] and eng == {'same4': True, 'same5': True, 'filled': 2}, (t_saqr, eng))
        line_s, avk_s = profile(ids['sahaba'])
        check('[B3 · the profile\'s completeness · M-b3-profile fails here] سحابة\'s profile: «اكتمال الشجرة 0%»', line_s.endswith('اكتمال الشجرة 0%'), line_s)
        t_chick, comp_chick = tiles(ids['chick']); line_c, avk_c = profile(ids['chick'])
        avk_eng = run(pg, "async (db, id) => { const a = window.__zajilEngine.coi.ancestorLoss(db.getBird, id, 5); return [a.filled, a.distinct, Math.round(a.avk * 10) / 10, Math.round(a.completeness)]; }", ids['chick'])
        check('[B3 · COI untouched] the offspring of the two full siblings still reads 25.0% — the shared placeholder parents are common ancestors, as they are meant to be',
              t_chick[0] == '25.0% التربية الداخلية' and '25.0%' in line_c, (t_chick, line_c))
        check('[B3 · AVK untouched] …and its AVK is the engine\'s own, placeholders counted: 66.7% (4 different ancestors in 6 filled places) — on a profile whose completeness is 3% (2 known of 62), where the engine\'s would be 10%',
              avk_c.endswith('66.7%') and avk_eng == [6, 4, 66.7, 10] and line_c.endswith('اكتمال الشجرة 3%'), (avk_c, avk_eng, line_c))
        check('[B3 · the tiles · PROPOSED for the figure beside AVK] its tree: «2 سلف من 30», «1 أجيال مكتملة», and «(اكتمال الشجرة: 3%)» beside AVK',
              t_chick[1:] == ['2 سلف من 30', '1 أجيال مكتملة'] and comp_chick == '(اكتمال الشجرة: 3%)', (t_chick, comp_chick))
        go(f"cert/?id={ids['sahaba']}", '[data-testid=sheet-node]')
        over = [' '.join(x.split()) for x in pg.locator('[data-testid=coi]').all_text_contents()]
        check('[B3 · PROPOSED, not ruled · M-b3-cert fails here] سحابة\'s certificate counts the same way: «0 من 30 سلفًا»', any('0 من 30 سلفًا' in x for x in over), over)

        # ══ B4 — A SAVE THAT LEAVES A PLACEHOLDER WITH NO CHILD ══
        f = run(pg, B4SEED, ids['sultan']); fam = {k: f[k] for k in ('pg', 'pa', 'pb', 'waheed', 'rafeeq', 'pc', 'yasser', 'mazen', 'pn', 'munfarid')}
        go(f"bird/edit/?id={f['waheed']}", '[data-testid=bird-form]'); pg.evaluate(PROBE); click(pg, '[data-testid=parent-dam-clear]'); s1 = save(); h1 = run(pg, HOLD, fam); log1 = pg.evaluate('() => window.__idbLog')
        check('[B4 · a parent cleared · M-b4-off fails here] وحيد saved without his mother: her placeholder, which no bird names now, is deleted — not in memory, not in storage, tombstoned',
              s1[0] == 'page' and h1['waheed']['dam'] is None and not h1['pb']['mem'] and not h1['pb']['stored'] and h1['pb']['tomb'], (s1, h1['waheed'], h1['pb']))
        check('[B4 · still named] …and his father\'s placeholder stays: both birds still name it — and so does its own placeholder mother',
              all(h1[k]['mem'] and h1[k]['stored'] and not h1[k]['tomb'] and h1[k]['ph'] for k in ('pa', 'pg')) and h1['waheed']['sire'] == f['pa'], (h1['pa'], h1['pg']))
        tx1 = tids(log1, ('birds', 'put', f['waheed']), ('birds', 'delete', f['pb']), ('tombstones', 'put', 'birds:' + f['pb']))
        check('[B4 · ONE TRANSACTION · M-b4-split fails here] the bird\'s record, the placeholder\'s deletion and its tombstone were written in the same IndexedDB transaction', one_tx(tx1), tx1)
        go(f"bird/edit/?id={f['waheed']}", '[data-testid=bird-form]'); set_parent('sire', 'سلطان'); s2 = save(); h2 = run(pg, HOLD, fam)
        check('[B4 · a parent changed, another child left · M-b4-greedy fails here] وحيد re-pointed to سلطان: the father\'s placeholder still stays — رفيق names it',
              s2[0] == 'page' and h2['waheed']['sire'] == ids['sultan'] and h2['pa']['mem'] and h2['pa']['ph'] and not h2['pa']['tomb'] and h2['pg']['mem'], (s2, h2['waheed'], h2['pa']))
        go(f"bird/edit/?id={f['rafeeq']}", '[data-testid=bird-form]'); pg.evaluate(PROBE); set_parent('sire', 'سلطان'); s3 = save(); h3 = run(pg, HOLD, fam); log3 = pg.evaluate('() => window.__idbLog')
        check('[B4 · a parent changed, the last child · M-b4-off fails here too] رفيق re-pointed to سلطان: the placeholder father, left with no child, is deleted with a tombstone',
              s3[0] == 'page' and h3['rafeeq']['sire'] == ids['sultan'] and not h3['pa']['mem'] and not h3['pa']['stored'] and h3['pa']['tomb'], (s3, h3['rafeeq'], h3['pa']))
        tx3 = tids(log3, ('birds', 'put', f['rafeeq']), ('birds', 'delete', f['pa']), ('birds', 'delete', f['pg']), ('tombstones', 'put', 'birds:' + f['pg']))
        check('[B4 · transitive · M-b4-chain fails here] …and so is ITS placeholder mother, left childless in turn — in the same transaction, with her own tombstone',
              not h3['pg']['mem'] and not h3['pg']['stored'] and h3['pg']['tomb'] and one_tx(tx3), (h3['pg'], tx3))
        # the sibling link's own writer (saveBirds): a placeholder father replaced by the other bird's recorded father
        go(f"bird/edit/?id={f['yasser']}", '[data-testid=bird-form]'); click(pg, '[data-testid=sib-open]'); fill(pg, '[data-testid=sib-input]', 'مازن'); click(pg, '[data-testid=sib-item] >> nth=0')
        click(pg, '[data-testid=sib-which-btn][data-which=sire]'); click(pg, '[data-testid=sib-apply]'); wait(pg, "() => document.querySelector('[data-testid=dialog]')", 4000); asked = dialog()
        check('[B2 · a question · M-b2-label fails here too] «أخ/أخت لطير مسجَّل…» — ياسر has a placeholder father and مازن\'s is سلطان: the question names them «أب غير معروف» and «سلطان»',
              f'أب هذا الطير المسجَّل هو «{SIRE}»، وأب «مازن» هو «سلطان»' in asked and f'استبدال «{SIRE}» بـ «سلطان»' in asked, asked)
        click(pg, '[data-testid=dialog-confirm]'); pg.wait_for_timeout(350); pg.evaluate(PROBE); s4 = save(); h4 = run(pg, HOLD, fam); log4 = pg.evaluate('() => window.__idbLog')
        tx4 = tids(log4, ('birds', 'put', f['yasser']), ('birds', 'delete', f['pc']), ('tombstones', 'put', 'birds:' + f['pc']))
        check('[B4 · the sibling link · M-b4-link fails here] saved with «استبدال»: ياسر\'s father is سلطان, and the placeholder he replaced is deleted, tombstoned, in the link\'s own transaction',
              s4[0] == 'page' and h4['yasser']['sire'] == ids['sultan'] and not h4['pc']['mem'] and not h4['pc']['stored'] and h4['pc']['tomb'] and one_tx(tx4), (s4, h4['yasser'], h4['pc'], tx4))

        # ══ B5 — ONE THAT HOLDS ANYTHING OF ITS OWN IS NEVER DELETED THAT WAY ══
        go('birds/', '[data-testid=count-line]'); line0 = text(pg, '[data-testid=count-line]'); rows0 = texts(pg, '[data-testid=row-name]')
        go(f"bird/edit/?id={f['munfarid']}", '[data-testid=bird-form]'); pg.evaluate(PROBE); click(pg, '[data-testid=parent-dam-clear]'); s5 = save(); h5 = run(pg, HOLD, fam); log5 = pg.evaluate('() => window.__idbLog')
        check('[B5 · through the form · M-b5-off and M-b5-fields fail here] منفرد saved without his mother, whose placeholder holds a colour: it is NOT deleted — it is in memory and in storage, has no tombstone, and keeps its colour',
              s5[0] == 'page' and h5['munfarid']['dam'] is None and h5['pn']['mem'] and h5['pn']['stored'] and not h5['pn']['tomb'] and h5['pn']['colour'] == 'أزرق', (s5, h5['munfarid'], h5['pn']))
        check('[B5 · the flag · M-b5-keepflag fails here] …its flag is cleared — the key is gone, in memory and in storage — and it is still a reference bird',
              h5['pn']['hasKey'] is False and h5['pn']['storedKey'] is False and h5['pn']['external'] is True and h5['pn']['status'] == 'reference', h5['pn'])
        tx5 = tids(log5, ('birds', 'put', f['munfarid']), ('birds', 'put', f['pn']))
        check('[B5 · ONE TRANSACTION] …written in the same transaction as the bird\'s own record', one_tx(tx5), tx5)
        go('birds/', '[data-testid=count-line]'); line1 = text(pg, '[data-testid=count-line]'); rows1 = texts(pg, '[data-testid=row-name]')
        n0 = int((line0 or '0').split()[0]); n1 = int((line1 or '0').split()[0])
        check('[B5 · visible] …and the bird list now has its row, under the name its record holds, and counts one bird more', n1 == n0 + 1 and sorted(rows1) == sorted(rows0 + [DAM]), (line0, line1, sorted(set(rows1) - set(rows0))))
        # every kind of thing it can hold: the last child is DELETED (item 6) and the placeholder must stay, unflagged, with what it holds
        kinds = run(pg, "async (db, jad) => { " + HELPERS + """
            const blob = () => new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' });
            const hen = await mk('أنثى الزوج', 'hen');
            const give = {
              note: (p) => db.saveBird({ ...db.getBird(p), notes: [{ id: db.uuid(), at: db.nowISO(), text: 'ملاحظة' }] }),
              colour: (p) => db.saveBird({ ...db.getBird(p), colour: 'أحمر' }),
              status: (p) => db.saveBird({ ...db.getBird(p), status: 'dead' }),
              photo: (p) => db.addMedia(p, 'photo', 'body', 'p.png', blob()),
              document: (p) => db.addMedia(p, 'document', 'other', 'd.png', blob()),
              result: (p) => db.Races.save({ id: db.uuid(), birdId: p, loftId, date: '2026-04-01', raceName: 'سباق', raceType: 'race', distanceKm: 100, velocity: 1000, position: 1, birdsEntered: 10 }),
              health: (p) => db.Health.save({ id: db.uuid(), eventType: 'check', wholeLoft: false, birdId: p, loftId, date: '2026-02-01', medication: '', notes: '' }),
              pair: (p) => db.Pairs.save({ sireId: p, damId: hen, season: '2026', nestBox: '9', status: 'active', loftId, rounds: [] }),
              parent: (p) => db.saveBird({ ...db.getBird(p), sireId: jad }),
            };
            const holds = async (k, p) => { const b = db.getBird(p); if (!b) return false;
              if (k === 'note') return (b.notes || []).length === 1; if (k === 'colour') return b.colour === 'أحمر'; if (k === 'status') return b.status === 'dead'; if (k === 'parent') return b.sireId === jad;
              if (k === 'photo' || k === 'document') return (await db.mediaForBird(p)).length === 1;
              if (k === 'result') return [...db.state.raceResults.values()].some(r => r.birdId === p); if (k === 'health') return [...db.state.healthEvents.values()].some(e => e.birdId === p);
              return [...db.state.pairs.values()].some(x => x.sireId === p); };
            const tomb = async (id) => !!(await db.idbGet('tombstones', 'birds:' + id));
            const out = {};
            for (const k of Object.keys(give)) {
              const p = await ph('أب غير معروف', 'cock'); await give[k](p); const c = await mk('فرخ ' + k, 'hen', { sireId: p }); await db.deleteBird(c); const b = db.getBird(p);
              out[k] = { stays: !!b && !!(await db.idbGet('birds', p)) && !(await tomb(p)), flag: b ? Object.prototype.hasOwnProperty.call(b, 'placeholder') : null, external: b ? b.external : null, listed: db.listedBirds().some(x => x.id === p), holds: await holds(k, p), childGone: !db.getBird(c) };
            }
            const bare = await ph('أب غير معروف', 'cock'); const cb = await mk('فرخ بلا شيء', 'hen', { sireId: bare }); await db.deleteBird(cb);
            out.bare = { gone: !db.getBird(bare) && !(await db.idbGet('birds', bare)), tomb: await tomb(bare) };
            return out; }""", ids['jad'])
        own_kinds = ['note', 'colour', 'status', 'photo', 'document', 'result', 'health', 'pair', 'parent']
        good = {'stays': True, 'flag': False, 'external': True, 'listed': True, 'holds': True, 'childGone': True}
        bad = {k: kinds.get(k) for k in own_kinds if kinds.get(k) != good}
        check('[B5 · item 6 · M-b5-off fails here] a placeholder father whose last child is deleted STAYS when it holds a note, a colour, a status of its own, a photo, a document, a result, a health event, a pair, or a recorded parent — nine records, each kept, unflagged, listed, and still holding it',
              not bad, bad)
        check('[B5 · its fields · M-b5-fields fails here] …the note, the colour and the status among them', all(kinds.get(k) == good for k in ('note', 'colour', 'status')), {k: kinds.get(k) for k in ('note', 'colour', 'status')})
        check('[B5 · its photos and documents · M-b5-media fails here] …the photo and the document', all(kinds.get(k) == good for k in ('photo', 'document')), {k: kinds.get(k) for k in ('photo', 'document')})
        check('[B5 · its records · M-b5-records fails here] …the result, the health event and the pair', all(kinds.get(k) == good for k in ('result', 'health', 'pair')), {k: kinds.get(k) for k in ('result', 'health', 'pair')})
        check('[B5 · a parent recorded for it · M-b5-parent fails here] …and the recorded father', kinds.get('parent') == good, kinds.get('parent'))
        check('[B5 · one that holds nothing] …while one that holds nothing still goes with its last child, tombstoned (item 6 as it was)', kinds.get('bare') == {'gone': True, 'tomb': True}, kinds.get('bare'))
        # a bare father and a mother that holds a note, one child: the father goes, the mother stays — and the undo puts both back as they were
        mix = run(pg, "async (db) => { " + HELPERS + """
            const pf = await ph('أب غير معروف', 'cock'); const pm = await ph('أم غير معروفة', 'hen'); await db.saveBird({ ...db.getBird(pm), notes: [{ id: db.uuid(), at: db.nowISO(), text: 'أمّ لها ملاحظة' }] });
            const c = await mk('مزدوج', 'cock', { sireId: pf, damId: pm }); const snap = await db.deleteBird(c);
            const view = () => ({ child: !!db.getBird(c), father: !!db.getBird(pf), mother: !!db.getBird(pm), motherFlag: db.getBird(pm) ? db.getBird(pm).placeholder === true : null, motherNote: db.getBird(pm) ? (db.getBird(pm).notes || []).length : null, fatherFlag: db.getBird(pf) ? db.getBird(pf).placeholder === true : null });
            const after = view(); const snapSays = { went: (snap.placeholders || []).map(x => x.id === pf), unflagged: (snap.unflagged || []).map(x => x.id === pm) };
            await db.restoreBird(snap); const undone = view(); const tombs = [!!(await db.idbGet('tombstones', 'birds:' + pf)), !!(await db.idbGet('tombstones', 'birds:' + c))];
            const links = db.getBird(c) ? [db.getBird(c).sireId === pf, db.getBird(c).damId === pm] : null;
            return { after, snapSays, undone, tombs, links }; }""")
        check('[B5 · beside a bare one] a bare placeholder father and a placeholder mother with a note, their one child deleted: the father goes, the mother stays without the flag and with her note',
              mix['after'] == {'child': False, 'father': False, 'mother': True, 'motherFlag': False, 'motherNote': 1, 'fatherFlag': None} and mix['snapSays'] == {'went': [True], 'unflagged': [True]}, (mix['after'], mix['snapSays']))
        check('[B5 · undo · M-b5-undo fails here] «تراجع» puts all three back as they were: the child naming both, the father a placeholder, and the mother A PLACEHOLDER AGAIN, still with her note — no tombstone left',
              mix['undone'] == {'child': True, 'father': True, 'mother': True, 'motherFlag': True, 'motherNote': 1, 'fatherFlag': True} and mix['tombs'] == [False, False] and mix['links'] == [True, True], (mix['undone'], mix['tombs'], mix['links']))
        check('[B4 · B5] the register is referentially clean after all of it', pg.evaluate(INTEGRITY) == 0, pg.evaluate(INTEGRITY))

        # ══ B6 — A HELD SIBLING LINK WHOSE OTHER BIRD IS GONE ══
        g = run(pg, "async (db) => { " + HELPERS + " return { alif: await mk('ألف', 'cock'), ba: await mk('باء', 'hen') }; }")
        go(f"bird/edit/?id={g['alif']}", '[data-testid=bird-form]'); click(pg, '[data-testid=sib-open]'); fill(pg, '[data-testid=sib-input]', 'باء'); click(pg, '[data-testid=sib-item] >> nth=0'); click(pg, '[data-testid=sib-apply]'); pg.wait_for_timeout(350)
        held = pg.get_attribute('[data-testid=sibling-notice]', 'data-link') if pg.locator('[data-testid=sibling-notice]').count() else None
        before = run(pg, HOLD, {'alif': g['alif']})
        run(pg, "async (db, id) => { if (db.getBird(id)) await db.deleteBird(id); }", g['ba']); pg.wait_for_timeout(500)
        mid = run(pg, HOLD, {'alif': g['alif']})
        note_kind = pg.get_attribute('[data-testid=sibling-notice]', 'data-link') if pg.locator('[data-testid=sibling-notice]').count() else None
        note = text(pg, '[data-testid=sibling-notice]') or ''; ty_note = faces(pg)
        GONE = 'لم يعد «باء» مسجَّلًا، فلا يمكن حفظ هذا الطير أخًا أو أختًا له. ألغِ الربط أو اختر طيرًا آخر.'
        check('[B6 · the notice · M-b6-notice fails here] ألف\'s form holds a link to باء; باء is deleted behind it: the notice now says «لم يعد «باء» مسجَّلًا…» and offers «إلغاء الربط» — in a face that has Arabic',
              held == 'both' and note_kind == 'gone' and GONE in note and 'إلغاء الربط' in note and not ty_note, (held, note_kind, note, ty_note[:2]))
        s6 = save(); ty_dlg = faces(pg); after = run(pg, HOLD, {'alif': g['alif']})
        check('[B6 · the save stops · M-b6-drop fails here] saving: «لا يمكن الحفظ» — the same sentence, naming باء — with «رجوع للنموذج» and no way to save past it',
              s6[0] == 'dialog' and 'لا يمكن الحفظ' in s6[1] and GONE in s6[1] and 'رجوع للنموذج' in s6[1] and pg.locator('[data-testid=dialog-confirm]').count() == 0 and not ty_dlg, (s6, ty_dlg[:2]))
        check('[B6 · nothing written · M-b6-drop fails here] …and nothing was written: ألف\'s record is as it was, no placeholder was made, no operation was logged',
              after['alif']['at'] == mid['alif']['at'] == before['alif']['at'] and after['alif']['sire'] is None and after['alif']['dam'] is None and after['birds'] == mid['birds'] and after['ops'] == mid['ops'], (before['alif'], after['alif'], (mid['birds'], after['birds']), (mid['ops'], after['ops'])))
        click(pg, '[data-testid=dialog-cancel]'); pg.wait_for_timeout(250); removed = click(pg, '[data-testid=sib-remove]', 3000); pg.wait_for_timeout(250); s7 = save(); end = run(pg, HOLD, {'alif': g['alif']})
        check('[B6 · the way out] «إلغاء الربط», then save: ألف is saved on its own — no parents, and no placeholder made',
              removed and s7[0] == 'page' and end['alif']['sire'] is None and end['alif']['dam'] is None and end['birds'] == mid['birds'] and end['alif']['at'] != mid['alif']['at'], (removed, s7, end['alif'], (mid['birds'], end['birds'])))

        # ══ C3 — A PLACEHOLDER'S OWN EDIT FORM: the name field ══
        REC = """async (db, id) => { const b = db.getBird(id); return b ? { name: b.name, flag: b.placeholder === true, hasKey: Object.prototype.hasOwnProperty.call(b, 'placeholder'), colour: b.colour || '', rings: (b.rings || []).map(r => r.raw), external: b.external } : null; }"""
        def name_field(): return [pg.input_value('[data-testid=f-name]'), pg.get_attribute('[data-testid=f-name]', 'placeholder')] if pg.locator('[data-testid=f-name]').count() else None
        go(f"bird/edit/?id={ids['ps']}", '[data-testid=bird-form]'); shown = name_field(); held = run(pg, REC, ids['ps'])
        check('[C3 · the field · M-c3-field and M-c3-hint fail here] the edit form of the father\'s placeholder — its record holds "Unknown sire" — shows the name field EMPTY, with «أب غير معروف» as its hint',
              shown == ['', SIRE] and bool(held) and held['name'] == 'Unknown sire' and held['flag'] is True, (shown, held))
        s8 = save(); kept = run(pg, REC, ids['ps'])
        check('[C3 · saved empty · M-c3-keepname fails here] saved with the field still empty it stays a placeholder — and its record keeps the name it held',
              s8[0] == 'page' and bool(kept) and kept['flag'] is True and kept['name'] == 'Unknown sire', (s8, kept))
        run(pg, "async (db) => { await db.setSetting('lang', 'en'); }")
        go(f"bird/edit/?id={ids['pd']}", '[data-testid=bird-form]'); shown_en = name_field()
        run(pg, "async (db) => { await db.setSetting('lang', 'ar'); }")
        check('[C3 · language] in English the mother\'s placeholder — its record holds «أم غير معروفة» — shows the field empty with "Unknown dam" as its hint', shown_en == ['', 'Unknown dam'], shown_en)
        go(f"bird/edit/?id={ids['pd']}", '[data-testid=bird-form]'); fill(pg, '[data-testid=f-colour]', 'رمادي'); s9 = save(); col = run(pg, REC, ids['pd'])
        check('[C3 · another field] a colour given and the name left empty: still a placeholder, the colour saved, the stored name untouched',
              s9[0] == 'page' and bool(col) and col['flag'] is True and col['colour'] == 'رمادي' and col['name'] == DAM, (s9, col))
        go(f"bird/edit/?id={ids['pd']}", '[data-testid=bird-form]'); fill(pg, '[data-testid=f-name]', 'أم نجم'); s10 = save(); named = run(pg, REC, ids['pd'])
        check('[C3 · a name typed · M-c3-noname fails here] a name typed: the flag is cleared on save and the bird carries that name', s10[0] == 'page' and bool(named) and named['hasKey'] is False and named['name'] == 'أم نجم' and named['external'] is True, (s10, named))
        # typing the very label the app shows is typing a name: the fancier has said what the bird is called
        go(f"bird/edit/?id={ids['pg1']}", '[data-testid=bird-form]'); fill(pg, '[data-testid=f-name]', SIRE); s11 = save(); same = run(pg, REC, ids['pg1'])
        check('[C3 · any name · M-c3-any fails here] typing «أب غير معروف» itself — the name its record already holds — is a name typed: the flag is cleared', s11[0] == 'page' and bool(same) and same['hasKey'] is False and same['name'] == SIRE, (s11, same))
        go(f"bird/edit/?id={ids['ps']}", '[data-testid=bird-form]'); fill(pg, '[data-testid=ring-input] >> nth=0', 'JO-2019-333001'); s12 = save(); ringed = run(pg, REC, ids['ps'])
        check('[C3 · a ring · PROPOSED for the name] a ring added and the name left empty: the flag is cleared, and the bird is saved as the form showed it — the ring, and no name',
              s12[0] == 'page' and bool(ringed) and ringed['hasKey'] is False and ringed['rings'] == ['JO-2019-333001'] and ringed['name'] == '', (s12, ringed))

        check('zero page errors overall', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
