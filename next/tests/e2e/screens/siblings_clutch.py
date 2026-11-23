#!/usr/bin/env python3
"""SIBLING OF / SAME CLUTCH, for new and existing birds (RULED 2026-11-23, src/family.js, src/engine/clutch.js).

Until this change set the only way to record two birds as siblings without knowing their parents was the profile's
«إضافة شقيق/شقيقة», which makes a NEW bird. Two birds already in the register could not be linked at all, and nothing
could say that two birds hatched from the same clutch (بطن) unless a pair record with a round held them both.

  item 9   `clutchId` on the bird: a group id (uuid). It points at no record.
  item 10  clutchMates(bird): the birds sharing its clutchId, plus the birds whose ids are chickId in the same round of
           a pair. Nothing writes clutchId when a chick is ringed.
  item 11  «أخ/أخت لطير مسجَّل…» on the bird form: pick a bird, then both parents / father only / mother only, and
           «من نفس البطن», which forces both. Where the other bird has the parent it is copied; where it has none a
           placeholder is made and written to both; a different parent on this bird is asked about, both named; the
           other bird's ancestor or descendant is refused; a clutch of more than two and two different hatch dates
           warn and never block. ALL OF IT IS WRITTEN IN ONE TRANSACTION, WITH THE SAVE — nothing before, nothing on
           cancel.
  item 12  the save check warns when clutch-mates do not share sire and dam.
  item 13  the profile lists full siblings, half siblings and clutch-mates.
  item 14  «إضافة شقيق/شقيقة» still works (also screens/placeholders.py and screens/bird_form.py).
  item 15  every new string, in Arabic and English, in a face that has Arabic.

Fixture names are invented; nothing is configured, so nothing leaves the page.

    python3 tests/e2e/screens/siblings_clutch.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import json, os, re, sys
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

SEED = """async (db) => {
    const loftId = db.currentLoft().id; const ids = {};
    const mk = async (name, sex, extra = {}) => (await db.saveBird(db.newBird({ name, sex, loftId, ...extra }), { allowWarnings: true })).id;
    ids.alif = await mk('ألف', 'cock'); ids.ba = await mk('باء', 'hen', { hatchDate: '2026-03-10' });
    ids.sultan = await mk('سلطان', 'cock', { hatchDate: '2022-02-01' }); ids.durra = await mk('درة', 'hen', { hatchDate: '2022-03-01' }); ids.marjan = await mk('مرجان', 'cock', { hatchDate: '2021-05-01' });
    ids.jim = await mk('جيم', 'cock', { sireId: ids.sultan, damId: ids.durra, hatchDate: '2025-04-01' });
    ids.dal = await mk('دال', 'hen', { sireId: ids.marjan, hatchDate: '2025-05-01' });
    ids.ta = await mk('طاء', 'hen');
    ids.kabir = await mk('كبير', 'cock', { hatchDate: '2020-01-01' }); ids.saghir = await mk('صغير', 'cock', { sireId: ids.kabir, hatchDate: '2024-01-01' });
    ids.qadim = await mk('قديم', 'cock', { hatchDate: '2019-01-01' });
    ids.c1 = await mk('فرخ أول', 'cock', { sireId: ids.sultan, damId: ids.durra, hatchDate: '2026-03-19' });
    ids.c2 = await mk('فرخ ثان', 'hen', { sireId: ids.sultan, damId: ids.durra, hatchDate: '2026-03-19' });
    const egg = (chickId) => ({ id: db.uuid(), laidDate: '2026-03-01', state: 'hatched', hatchDate: '2026-03-19', chickId, ringed: !!chickId });
    const pair = await db.Pairs.save({ sireId: ids.sultan, damId: ids.durra, season: '2026', nestBox: '7', status: 'active', loftId,
      rounds: [{ id: db.uuid(), number: 1, eggs: [egg(ids.c1), egg(ids.c2)] }, { id: db.uuid(), number: 2, eggs: [egg(null), egg(null)] }] });
    ids.pair = pair.id; return ids; }"""
REC = """async (db, id) => { const b = db.getBird(id); if (!b) return null; const par = (pid) => { const p = pid ? db.getBird(pid) : null; return p ? { name: p.name, sex: p.sex, ph: p.placeholder === true, ext: p.external } : null; };
    return { name: b.name, sireId: b.sireId || null, damId: b.damId || null, sire: par(b.sireId), dam: par(b.damId), clutchId: b.clutchId || null, hasClutch: Object.prototype.hasOwnProperty.call(b, 'clutchId'), hatch: b.hatchDate || '', updatedAt: b.updatedAt }; }"""
BYNAME = "async (db, name) => { const b = db.allBirds().find(x => x.name === name); return b ? b.id : null; }"
COUNT = "async (db) => db.allBirds().length"
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
SIRE, DAM = 'أب غير معروف', 'أم غير معروفة'

def wait(pg, js, ms=8000):
    try: pg.wait_for_function(js, timeout=ms); return True
    except Exception: return False
def texts(pg, sel): return [' '.join(x.split()) for x in pg.locator(sel).all_inner_texts()]
def text(pg, sel): return pg.evaluate("(s) => { const e = document.querySelector(s); return e ? e.innerText.trim().replace(/\\s+/g, ' ') : null; }", sel)
def click(pg, sel, ms=6000):
    try: pg.click(sel, timeout=ms); return True
    except Exception: return False
def fill(pg, sel, v, ms=6000):
    try: pg.fill(sel, v, timeout=ms); pg.wait_for_timeout(250); return True
    except Exception: return False
def faces(pg): return [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e, _p=pg: errs.append(perr(e, _p)))
        def go(path, sel='[data-testid=bird-form]', ms=10000):
            pg.goto(ROOT + path, wait_until='load')
            try: pg.wait_for_selector(sel, timeout=ms); pg.wait_for_timeout(200); return True
            except Exception: return False
        def choose(q, which=None, clutch=False):
            """Open the panel, pick the bird the query finds, set the choice. Returns the names offered for the query."""
            if not pg.locator('[data-testid=sib-panel]').count(): click(pg, '[data-testid=sib-open]')
            fill(pg, '[data-testid=sib-input]', q); offered = texts(pg, '[data-testid=sib-item]')
            click(pg, '[data-testid=sib-item] >> nth=0')
            if which: click(pg, f'[data-testid=sib-which-btn][data-which={which}]')
            if clutch:
                try: pg.check('[data-testid=sib-clutch]', timeout=4000)
                except Exception: pass
            return offered
        def apply_(): click(pg, '[data-testid=sib-apply]'); pg.wait_for_timeout(350)
        def dialog():
            d = pg.locator('[data-testid=dialog]')
            return ' / '.join(x.strip() for x in d.inner_text().split('\n') if x.strip()) if d.count() else ''
        def save(name=None):
            """Press save; say what followed within 6 s: ('dialog', text), ('page', url) or ('nothing', url)."""
            if name is not None: fill(pg, '[data-testid=f-name]', name)
            click(pg, '[data-testid=save-btn]')
            if not wait(pg, "() => document.querySelector('[data-testid=dialog]') || /\\/bird\\/\\?id=/.test(location.href)", 6000): return ('nothing', pg.url)
            return ('dialog', dialog()) if pg.locator('[data-testid=dialog]').count() else ('page', pg.url)
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_function('window.__zajilReady')
        ids = run(pg, SEED); n0 = run(pg, COUNT)

        # ══ item 14 — the menu's intent arrives as before, with its own sentence ══
        go(f"bird/new/?siblingOf={ids['ta']}")
        legacy = text(pg, '[data-testid=sibling-notice]') or ''
        check('[item 14] «إضافة شقيق/شقيقة» on a bird with no parents still opens the form with its own notice — «سيُسجَّل هذا الطير شقيقًا لـ «طاء»…» — and nothing is written by opening it',
              legacy.startswith('سيُسجَّل هذا الطير شقيقًا لـ «طاء».') and pg.locator('[data-testid=sib-remove]').count() == 0 and run(pg, COUNT) == n0, legacy)

        # ══ item 11 — the plan itself (src/family.js): what «من نفس البطن» alone asks for, and that planning writes nothing ══
        plan = run(pg, """async (db, x) => { const n = db.allBirds().length; const me = db.newBird({ name: 'تجربة', sex: 'cock' });
            const p = db.planSiblingLink(me, db.getBird(x), { clutch: true }, { sire: 'س', dam: 'م' });
            return { reject: p.reject, made: p.placeholders.map(q => [q.sex, q.placeholder, q.external, q.name]), sire: !!p.bird.sireId && !!p.x && p.bird.sireId === p.x.sireId, dam: !!p.bird.damId && !!p.x && p.bird.damId === p.x.damId,
                     clutch: !!p.x && p.bird.clutchId === p.x.clutchId ? p.bird.clutchId : null, hatch: p.bird.hatchDate || '', wrote: db.allBirds().length - n, stored: [db.getBird(x).sireId, db.getBird(x).clutchId || null] }; }""", ids['ba'])
        check('[item 11 · the plan · M-clutchboth fails here] «من نفس البطن» alone plans BOTH parents: a placeholder father and mother, the same two ids on both birds — and planning writes nothing',
              plan['reject'] is None and plan['made'] == [['cock', True, True, 'س'], ['hen', True, True, 'م']] and plan['sire'] and plan['dam'] and plan['wrote'] == 0 and plan['stored'] == [None, None], plan)
        check('[item 9 · item 11 · M-noclutchid fails here too] …one clutchId, a uuid, on both birds; and this bird\'s empty hatch date takes the other\'s (M-planhatch fails here)',
              bool(plan['clutch']) and bool(UUID.match(plan['clutch'] or '')) and plan['hatch'] == '2026-03-10', plan)

        # ══ item 11 — THE CASE IT WAS RULED FOR: two birds already in the register, no parents known, the same clutch ══
        go(f"bird/edit/?id={ids['alif']}")
        opener = text(pg, '[data-testid=sib-open]'); click(pg, '[data-testid=sib-open]')
        fill(pg, '[data-testid=sib-input]', 'ألف'); own = texts(pg, '[data-testid=sib-item]')
        offered = choose('باء', which='sire')
        labels = texts(pg, '[data-testid=sib-which-btn]'); box = text(pg, '[data-testid=sib-panel] label')
        check('[item 11 · pick] the panel finds «باء» and never offers the bird being edited', len(offered) == 1 and offered[0].startswith('باء') and own == [], (offered, own))
        check('[item 15] the action and the panel in Arabic: «أخ/أخت لطير مسجَّل…», «الأبوان معًا» · «الأب فقط» · «الأم فقط», «من نفس البطن» — in a face that has Arabic',
              opener == 'أخ/أخت لطير مسجَّل…' and labels == ['الأبوان معًا', 'الأب فقط', 'الأم فقط'] and box == 'من نفس البطن' and not faces(pg), (opener, labels, box, faces(pg)[:2]))
        try: pg.check('[data-testid=sib-clutch]', timeout=4000)
        except Exception: pass
        seg = pg.evaluate("() => [...document.querySelectorAll('[data-testid=sib-which-btn]')].map(e => [e.dataset.which, e.getAttribute('aria-pressed'), e.disabled])")
        check('[item 11 · the checkbox] «من نفس البطن» forces both parents: «الأب فقط» was chosen, and now «الأبوان معًا» is the pressed one and the three are locked',
              seg == [['both', 'true', True], ['sire', 'false', True], ['dam', 'false', True]], seg)
        before = run(pg, "async (db, a, b) => JSON.stringify([db.getBird(a), db.getBird(b), db.allBirds().length])", ids['alif'], ids['ba'])
        apply_()
        notice = text(pg, '[data-testid=sibling-notice]') or ''; kind = pg.evaluate("() => document.querySelector('[data-testid=sibling-notice]')?.dataset.link || null")
        hatch = pg.evaluate("() => document.querySelector('[data-testid=f-hatch]').value")
        check('[item 11 · the notice] after «تأكيد» the form says what the save will do: «أخ/أخت لـ «باء»» · same clutch, same father and mother · an «غير معروف» record for each unrecorded parent',
              kind == 'clutch' and 'أخ/أخت لـ «باء»' in notice and 'يُسجَّل الطيران من البطن نفسه، بالأب نفسه والأم نفسها' in notice and 'يُنشأ له سجلّ «غير معروف»' in notice and 'إلغاء الربط' in notice and not faces(pg), (kind, notice, faces(pg)[:2]))
        check('[item 11 · hatch date] this bird had no hatch date, so the form now shows the other bird\'s: 2026-03-10', hatch == '2026-03-10', hatch)
        same = run(pg, "async (db, a, b) => JSON.stringify([db.getBird(a), db.getBird(b), db.allBirds().length])", ids['alif'], ids['ba']) == before
        check('[item 11 · nothing before the save · M-eager fails here] choosing and confirming wrote NOTHING: both records and the bird count are byte for byte what they were', same)
        go('birds/', '[data-testid=bird-row]')
        same = run(pg, "async (db, a, b) => JSON.stringify([db.getBird(a), db.getBird(b), db.allBirds().length])", ids['alif'], ids['ba']) == before
        check('[item 11 · cancel] leaving the form without saving wrote nothing either', same)

        go(f"bird/edit/?id={ids['alif']}"); choose('باء', clutch=True); apply_()
        ops0 = run(pg, "async (db) => (await db.listOps()).length"); seen = save()
        a, bb = run(pg, REC, ids['alif']), run(pg, REC, ids['ba']); n1 = run(pg, COUNT)
        check('[item 11 · same clutch · M-noother fails here] saved: ألف and باء name the SAME father and the SAME mother — two new placeholders, a cock and a hen, flagged and external',
              seen[0] == 'page' and a['sireId'] and a['sireId'] == bb['sireId'] and a['damId'] and a['damId'] == bb['damId'] and a['sire'] == {'name': SIRE, 'sex': 'cock', 'ph': True, 'ext': True}
              and a['dam'] == {'name': DAM, 'sex': 'hen', 'ph': True, 'ext': True} and n1 == n0 + 2, (seen, a, bb, n1 - n0))
        check('[item 9 · M-noclutchid fails here] …and one clutchId, a uuid, on both birds', bool(a['clutchId']) and a['clutchId'] == bb['clutchId'] and bool(UUID.match(a['clutchId'])), (a['clutchId'], bb['clutchId']))
        check('[item 11 · hatch date] …ألف was saved with باء\'s hatch date; باء\'s own is untouched', a['hatch'] == '2026-03-10' and bb['hatch'] == '2026-03-10', (a['hatch'], bb['hatch']))
        tail = run(pg, """async (db, n, ids) => (await db.listOps()).slice(n).map(o => [o.store, o.op, o.recordId === ids.alif ? 'ألف' : o.recordId === ids.ba ? 'باء' : (db.getBird(o.recordId) || {}).placeholder ? 'placeholder' : '?', o.seq])""", ops0, ids)
        seqs = [t[3] for t in tail]
        check('[item 11 · what the save logged] four operations, in order — the two placeholders, باء, ألف — and nothing else',
              [t[:3] for t in tail] == [['birds', 'put', 'placeholder'], ['birds', 'put', 'placeholder'], ['birds', 'put', 'باء'], ['birds', 'put', 'ألف']] and seqs == list(range(seqs[0], seqs[0] + 4)) if tail else False, tail)
        kin = pg.evaluate("""(ids) => { const db = window.__zajilDb, e = window.__zajilEngine; const g = (id) => db.getBird(id);
            return { coi: e.coi.pairCOI(g, ids.alif, ids.ba).coi, rel: e.relationship.describeRelationship(g, ids.alif, ids.ba).key }; }""", ids)
        check('[item 11 · kinship] the engine reads them as full siblings: pairCOI(ألف, باء) = 0.25', kin == {'coi': 0.25, 'rel': 'rel.fullSiblings'}, kin)

        # ══ item 10 — clutchMates(): the group id, and the round of a pair ══
        mates = run(pg, "async (db, ids) => ({ alif: db.clutchMates(db.getBird(ids.alif)).map(b => b.name), c1: db.clutchMates(db.getBird(ids.c1)).map(b => b.name), lone: db.clutchMates(db.getBird(ids.ta)).map(b => b.name), c1Key: Object.prototype.hasOwnProperty.call(db.getBird(ids.c1), 'clutchId') })", ids)
        check('[item 10 · M-nogroup fails here] clutchMates(ألف) is باء — the shared clutchId', mates['alif'] == ['باء'], mates)
        check('[item 10 · M-noround fails here] clutchMates(فرخ أول) is فرخ ثان — the same round of a pair, with no clutchId on either; a bird in no clutch has none',
              mates['c1'] == ['فرخ ثان'] and mates['c1Key'] is False and mates['lone'] == [], mates)
        go(f"pair/?id={ids['pair']}", '[data-testid=egg-ring]')
        for ring, nm in (('JO-2026-900001', 'مرقَّم أول'), ('JO-2026-900002', 'مرقَّم ثان')):
            click(pg, '[data-testid=egg-ring] >> nth=0'); wait(pg, "() => document.querySelector('[data-testid=sheet-ring]')")
            fill(pg, '[data-testid=f-ring]', ring); fill(pg, '[data-testid=f-name]', nm); click(pg, '[data-testid=sheet-save]')
            wait(pg, "() => !document.querySelector('[data-testid=sheet-ring]')"); pg.wait_for_timeout(300)
        rung = run(pg, """async (db) => { const a = db.allBirds().find(b => b.name === 'مرقَّم أول'), c = db.allBirds().find(b => b.name === 'مرقَّم ثان'); if (!a || !c) return null;
            return { keys: [Object.prototype.hasOwnProperty.call(a, 'clutchId'), Object.prototype.hasOwnProperty.call(c, 'clutchId')], mates: db.clutchMates(a).map(b => b.name), warn: db.checkBird(a).warnings.map(w => w.key) }; }""")
        check('[item 10 · ringing] two chicks ringed from the eggs of one round carry NO clutchId — the round is the record — and are each other\'s clutch-mate',
              rung == {'keys': [False, False], 'mates': ['مرقَّم ثان'], 'warn': []}, rung)

        # ══ item 12 — the save check: clutch-mates share sire and dam ══
        v = run(pg, """async (db, ids) => { const ba = db.getBird(ids.ba), c1 = db.getBird(ids.c1); const w = (b) => db.checkBird(b).warnings.map(x => [x.key, (db.getBird(x.params.otherId) || {}).name]);
            return { asIs: w(ba), noSire: w({ ...ba, sireId: null }), round: w({ ...c1, damId: null }), errors: db.checkBird({ ...ba, sireId: null }).errors.length }; }""", ids)
        check('[item 12 · M-noclutchwarn fails here] باء as it is raises nothing; باء with its father removed warns val.clutchParents, naming ألف — a warning, never an error',
              v['asIs'] == [] and v['noSire'] == [['val.clutchParents', 'ألف']] and v['errors'] == 0, v)
        check('[item 12 · the round too · M-noround fails here too] فرخ أول with its mother removed warns the same way, naming فرخ ثان, its mate in the round', v['round'] == [['val.clutchParents', 'فرخ ثان']], v['round'])
        go(f"bird/edit/?id={ids['ba']}"); click(pg, '[data-testid=parent-sire-clear]'); seen = save()
        check('[item 12 · the form] saving باء without its father asks first: «هذا الطير و«ألف» من البطن نفسه، لكن أبويهما المسجَّلين مختلفان.» — with «حفظ رغم التحذير», in a face that has Arabic',
              seen[0] == 'dialog' and 'هذا الطير و«ألف» من البطن نفسه، لكن أبويهما المسجَّلين مختلفان.' in seen[1] and 'حفظ رغم التحذير' in seen[1] and not faces(pg), (seen, faces(pg)[:2]))
        click(pg, '[data-testid=dialog-cancel]'); pg.wait_for_timeout(200)
        check('[item 12 · the form] …and backing out leaves باء as it was', run(pg, REC, ids['ba'])['sireId'] == bb['sireId'])

        # ══ item 11 — where the other bird HAS the parent, its id is copied ══
        go('bird/new/'); choose('جيم'); apply_()
        slots = [text(pg, '[data-testid=parent-sire-name]'), text(pg, '[data-testid=parent-dam-name]')]; j0 = run(pg, REC, ids['jim']); n2 = run(pg, COUNT)
        seen = save('هاء'); ids['ha'] = run(pg, BYNAME, 'هاء'); ha = run(pg, REC, ids['ha']) or {}
        check('[item 11 · the other bird has both · M-nocopy fails here] «أخ/أخت» of جيم, both parents: the slots show سلطان and درة at once, and the new bird is saved with exactly those two ids',
              slots == ['سلطان', 'درة'] and seen[0] == 'page' and ha.get('sireId') == ids['sultan'] and ha.get('damId') == ids['durra'], (slots, seen, ha))
        check('[item 11 · the other bird has both] …no placeholder was made, جيم was not rewritten, and no clutchId was set', run(pg, COUNT) == n2 + 1 and run(pg, REC, ids['jim'])['updatedAt'] == j0['updatedAt'] and ha.get('hasClutch') is False, (run(pg, COUNT) - n2, ha))
        go('bird/new/'); choose('جيم', which='sire'); apply_(); kind = pg.evaluate("() => document.querySelector('[data-testid=sibling-notice]')?.dataset.link || null"); note = text(pg, '[data-testid=sibling-notice]') or ''
        seen = save('واو'); ids['waw'] = run(pg, BYNAME, 'واو'); waw = run(pg, REC, ids['waw']) or {}
        check('[item 11 · father only] «الأب فقط»: the notice says the same father, and the new bird is saved with جيم\'s father and no mother',
              kind == 'sire' and 'يُسجَّل للطيرين الأب نفسه.' in note and seen[0] == 'page' and waw.get('sireId') == ids['sultan'] and waw.get('damId') is None, (kind, note, waw))

        # ══ item 11 — where the other bird LACKS the parent, a placeholder is made and written to BOTH ══
        go('bird/new/'); choose('دال', which='dam'); apply_(); note = text(pg, '[data-testid=sibling-notice]') or ''; n3 = run(pg, COUNT)
        seen = save('زاي'); ids['zay'] = run(pg, BYNAME, 'زاي'); zay = run(pg, REC, ids['zay']) or {}; dal = run(pg, REC, ids['dal'])
        check('[item 11 · the other bird lacks it · M-noother fails here too] «الأم فقط» with دال, which has no mother: ONE placeholder mother is made and both birds name it; دال keeps its father, the new bird has none',
              'تُسجَّل للطيرين الأم نفسها.' in note and 'يُنشأ له سجلّ «غير معروف»' in note and seen[0] == 'page' and zay.get('damId') and zay.get('damId') == dal['damId'] and zay.get('dam') == {'name': DAM, 'sex': 'hen', 'ph': True, 'ext': True}
              and dal['sireId'] == ids['marjan'] and zay.get('sireId') is None and run(pg, COUNT) == n3 + 2, (note, zay, dal, run(pg, COUNT) - n3))

        # ══ item 11 — a DIFFERENT parent on this bird: stop and ask, naming both; never replaced silently ══
        go(f"bird/edit/?id={ids['jim']}"); choose('دال', which='sire'); apply_(); asked = dialog(); ty = faces(pg)
        check('[item 11 · a different parent · M-noask fails here] جيم\'s father is سلطان and دال\'s is مرجان: the form STOPS and asks — «اختلاف في الأبوين», naming سلطان, مرجان and دال, with «استبدال»',
              asked.startswith('اختلاف في الأبوين') and 'أب هذا الطير المسجَّل هو «سلطان»، وأب «دال» هو «مرجان». هل تريد استبدال «سلطان» بـ «مرجان» أبًا لهذا الطير؟' in asked and 'استبدال' in asked and not ty, (asked, ty[:2]))
        click(pg, '[data-testid=dialog-cancel]'); pg.wait_for_timeout(250)
        check('[item 11 · a different parent] «إلغاء»: nothing changed — the slot still says سلطان, no link is held, the panel is still open',
              text(pg, '[data-testid=parent-sire-name]') == 'سلطان' and pg.locator('[data-testid=sibling-notice]').count() == 0 and pg.locator('[data-testid=sib-panel]').count() == 1)
        apply_(); click(pg, '[data-testid=dialog-confirm]'); pg.wait_for_timeout(300)
        check('[item 11 · a different parent] «استبدال»: the slot now says مرجان and the link is held — in the form only', text(pg, '[data-testid=parent-sire-name]') == 'مرجان' and pg.locator('[data-testid=sibling-notice]').count() == 1 and run(pg, REC, ids['jim'])['sireId'] == ids['sultan'])
        go('birds/', '[data-testid=bird-row]')
        check('[item 11 · a different parent] …and leaving without saving leaves جيم with سلطان', run(pg, REC, ids['jim'])['sireId'] == ids['sultan'])
        go('bird/new/'); choose('دال', which='sire'); apply_()
        click(pg, '[data-testid=parent-sire-change]'); fill(pg, '[data-testid=picker-input]', 'سلطان'); click(pg, '[data-testid=picker-item] >> nth=0'); pg.wait_for_timeout(200)
        n4 = run(pg, COUNT); seen = save('حاء')
        check('[item 11 · asked again at the save] the father was changed in the form after the link was made: the SAVE asks the same question, and «إلغاء» writes nothing',
              seen[0] == 'dialog' and seen[1].startswith('اختلاف في الأبوين') and 'سلطان' in seen[1] and 'مرجان' in seen[1], seen)
        click(pg, '[data-testid=dialog-cancel]'); pg.wait_for_timeout(300)
        check('[item 11 · asked again at the save] …no bird was made', run(pg, COUNT) == n4 and run(pg, BYNAME, 'حاء') is None and '/bird/new' in pg.url, (run(pg, COUNT) - n4, pg.url))

        # ══ item 11 — PROPOSED, not ruled: the other bird lacks the parent and THIS bird has it → the other bird is given it ══
        go(f"bird/new/?sire={ids['sultan']}"); choose('طاء', which='sire'); apply_(); had = dialog(); n5 = run(pg, COUNT)
        seen = save('خاء'); ids['kha'] = run(pg, BYNAME, 'خاء'); kha = run(pg, REC, ids['kha']) or {}; ta = run(pg, REC, ids['ta'])
        check('[item 11 · PROPOSED, not ruled · M-give fails here] this bird has a father and طاء has none: no question, no placeholder — طاء is given this bird\'s father, سلطان',
              had == '' and seen[0] == 'page' and kha.get('sireId') == ids['sultan'] and ta['sireId'] == ids['sultan'] and run(pg, COUNT) == n5 + 1, (had, seen, kha, ta))

        # ══ item 11 — the two warnings of a clutch: more than two birds, and two different hatch dates. They never block. ══
        go('bird/new/'); fill(pg, '[data-testid=f-hatch]', '2026-04-01'); choose('ألف', clutch=True); apply_()
        seen = save('ياء'); ty = faces(pg)
        check('[item 11 · more than two · M-nowarnsize fails here] a third bird in ألف\'s clutch: the save warns «سيصير في هذا البطن 3 طيور، والبطن في العادة بيضتان.»',
              seen[0] == 'dialog' and 'سيصير في هذا البطن 3 طيور، والبطن في العادة بيضتان.' in seen[1], seen)
        check('[item 11 · hatch dates · M-nowarnhatch fails here] …and that its hatch date differs from ألف\'s, both dates written out, in a face that has Arabic',
              seen[0] == 'dialog' and 'يختلف عن تاريخ فقس «ألف»' in seen[1] and 'وهما من البطن نفسه' in seen[1] and seen[1].count('2026') >= 2 and not ty, (seen, ty[:2]))
        click(pg, '[data-testid=dialog-confirm]'); wait(pg, "() => /\\/bird\\/\\?id=/.test(location.href)", 6000)
        ids['ya'] = run(pg, BYNAME, 'ياء'); ya = run(pg, REC, ids['ya']) or {}
        ym = run(pg, "async (db, id) => id ? db.clutchMates(db.getBird(id)).map(b => b.name).sort() : null", ids['ya'])
        check('[item 11 · a warning never blocks] «حفظ رغم التحذير» saves it: the third bird carries the clutchId, keeps its own hatch date, and its clutch-mates are ألف and باء',
              ya.get('clutchId') == a['clutchId'] and ya.get('hatch') == '2026-04-01' and ym == ['ألف', 'باء'] and ya.get('sireId') == a['sireId'], (ya, ym))

        # ══ item 11 — refused: the other bird is this bird's ancestor, or its descendant ══
        go(f"bird/edit/?id={ids['saghir']}"); choose('كبير'); apply_(); up = text(pg, '[data-testid=sib-error]'); held_up = pg.locator('[data-testid=sibling-notice]').count()
        go(f"bird/edit/?id={ids['kabir']}"); choose('صغير'); apply_(); down = text(pg, '[data-testid=sib-error]'); held_down = pg.locator('[data-testid=sibling-notice]').count()
        check('[item 11 · ancestor or descendant · M-nolineage fails here] صغير cannot be the sibling of its own father كبير, nor كبير of its son: «لا يمكن تسجيل «…» أخًا أو أختًا لهذا الطير: أحدهما من أسلاف الآخر.» — and no link is held',
              up == 'لا يمكن تسجيل «كبير» أخًا أو أختًا لهذا الطير: أحدهما من أسلاف الآخر.' and down == 'لا يمكن تسجيل «صغير» أخًا أو أختًا لهذا الطير: أحدهما من أسلاف الآخر.' and held_up == 0 and held_down == 0 and not faces(pg), (up, down, held_up, held_down))

        # ══ item 11 — ALL OR NOTHING ══
        go(f"bird/new/?sire={ids['sultan']}"); choose('قديم'); apply_(); n6 = run(pg, COUNT); q0 = run(pg, REC, ids['qadim'])
        seen = save('كاف'); q1 = run(pg, REC, ids['qadim'])
        check('[item 11 · the other bird\'s error] the link would give قديم (hatched 2019) the father سلطان (hatched 2022): the save is refused, the error filed under «قديم»',
              seen[0] == 'dialog' and seen[1].startswith('لا يمكن الحفظ') and 'قديم' in seen[1], seen)
        click(pg, '[data-testid=dialog-cancel]'); pg.wait_for_timeout(200)
        check('[item 11 · the other bird\'s error] …and NOTHING was written: no new bird, no placeholder for the mother neither has, قديم untouched', run(pg, COUNT) == n6 and q1 == q0 and run(pg, BYNAME, 'كاف') is None, (run(pg, COUNT) - n6, q1))
        RAW = """const idb = await new Promise((res, rej) => { const r = indexedDB.open('zajil'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
            const stored = await new Promise((res) => { const q = idb.transaction('birds').objectStore('birds').getAllKeys(); q.onsuccess = () => res(q.result); }); idb.close();"""
        tx = run(pg, """async (db) => { const good = db.newBird({ name: 'يُكتب أولًا', sex: 'cock', placeholder: true }), bad = db.newBird({ name: 'لا يُخزَّن', sex: 'hen' }); bad.cannotBeStored = () => 1;
            const ops = (await db.listOps()).length, n = db.allBirds().length; let threw = null;
            try { await db.saveBirds([{ bird: good }, { bird: bad }]); } catch (e) { threw = e && e.name; }
            """ + RAW + """
            return { threw, mem: !!db.getBird(good.id), stored: stored.includes(good.id), ops: (await db.listOps()).length - ops, n: db.allBirds().length - n }; }""")
        check('[item 11 · ONE TRANSACTION · M-notx fails here] saveBirds() with a second record storage cannot take: it throws, and the FIRST record is not in memory, not in storage, and logged no operation',
              tx == {'threw': 'DataCloneError', 'mem': False, 'stored': False, 'ops': 0, 'n': 0}, tx)
        pre = run(pg, """async (db) => { const good = db.newBird({ name: 'يُكتب أولًا', sex: 'cock', placeholder: true }), bad = db.newBird({ name: 'أب نفسه', sex: 'cock' }); bad.sireId = bad.id;
            const n = db.allBirds().length; let threw = null;
            try { await db.saveBirds([{ bird: good }, { bird: bad }]); } catch (e) { threw = [e && e.name, (e.errors || []).map(x => x.key)]; }
            """ + RAW + """
            return { threw, stored: stored.includes(good.id) || stored.includes(bad.id), n: db.allBirds().length - n }; }""")
        check('[item 11 · judged first · M-partial fails here] saveBirds() with one record that fails validation: ValidationError (val.selfParent), and neither record is written',
              pre == {'threw': ['ValidationError', ['val.selfParent']], 'stored': False, 'n': 0}, pre)

        # ══ item 13 — the profile: full siblings, half siblings, clutch-mates (placement and styling PROPOSED) ══
        LISTS = """() => { const card = document.querySelector('[data-testid=siblings-card]'); if (!card) return null; const out = { title: card.querySelector('h2').innerText.trim() };
            for (const k of ['full', 'half', 'clutch']) { const box = card.querySelector('[data-testid=siblings-' + k + ']'); out[k] = box ? { label: box.querySelector('p').innerText.trim(), names: [...box.querySelectorAll('[data-testid=sibling-link]')].map(a => a.innerText.trim()).sort(), hrefs: [...box.querySelectorAll('[data-testid=sibling-link]')].map(a => a.getAttribute('href')).sort() } : null; }
            return out; }"""
        go(f"bird/?id={ids['alif']}&tab=ped", '[data-testid=mini-node]'); pg.wait_for_timeout(300); la = pg.evaluate(LISTS) or {}; ty = faces(pg)
        check('[item 13 · M-nolists fails here] ألف\'s profile, النسب: «الإخوة» — «أشقاء (نفس الأب والأم)»: باء, ياء · «من نفس البطن»: باء, ياء — and no half-sibling list, it has none',
              la.get('title') == 'الإخوة' and la.get('full') and la['full']['label'] == 'أشقاء (نفس الأب والأم)' and la['full']['names'] == ['باء', 'ياء'] and la.get('clutch') and la['clutch']['label'] == 'من نفس البطن' and la['clutch']['names'] == ['باء', 'ياء'] and la.get('half') is None, la)
        check('[item 13] …each name is a link to that bird\'s profile; no placeholder is listed; in a face that has Arabic',
              bool(la.get('full')) and la['full']['hrefs'] == sorted([f"/bird/?id={ids['ba']}", f"/bird/?id={ids['ya']}"]) and 'غير معروف' not in json.dumps(la, ensure_ascii=False) and not ty, (la.get('full'), ty[:2]))
        want = run(pg, "async (db, id) => { const s = db.siblingsOf(db.getBird(id)); return { full: s.full.map(b => b.name).sort(), half: s.half.map(b => b.name).sort() }; }", ids['waw'])
        go(f"bird/?id={ids['waw']}&tab=ped", '[data-testid=mini-node]'); pg.wait_for_timeout(300); lw = pg.evaluate(LISTS) or {}
        check('[item 13 · half siblings] واو, saved with سلطان as father only: «إخوة من طرف واحد» lists every other bird of سلطان — جيم and هاء among them — and no full sibling: a missing mother is not a shared mother',
              lw.get('half') and lw['half']['label'] == 'إخوة من طرف واحد' and lw['half']['names'] == want['half'] and 'جيم' in want['half'] and 'هاء' in want['half'] and (lw.get('full') or {}).get('names', []) == want['full'], (lw, want))
        go(f"bird/?id={ids['marjan']}&tab=ped", '[data-testid=mini-node]'); pg.wait_for_timeout(300)
        check('[item 13] a bird with no sibling and no clutch-mate has no «الإخوة» card', pg.locator('[data-testid=siblings-card]').count() == 0)

        # ══ records travel whole: an export, then a replace-import of the same file ══
        trip = run(pg, """async (db) => { const mark = () => JSON.stringify(db.allBirds().filter(b => b.placeholder === true || b.clutchId).map(b => [b.id, b.placeholder === true, b.clutchId || null, b.sireId || null, b.damId || null]).sort());
            const before = mark(); const text = JSON.stringify(await db.exportAll()); await db.importAll(JSON.parse(text), 'replace');
            return { same: mark() === before, n: JSON.parse(before).length, inFile: [text.includes('"placeholder":true'), text.includes('"clutchId":"')] }; }""")
        check('[export → replace-import] the file carries placeholder and clutchId, and after replacing the register with it every flagged record and every clutchId is as it was',
              trip['same'] and trip['n'] >= 6 and trip['inFile'] == [True, True], trip)

        # ══ item 15 — the same panel in English ══
        run(pg, "async (db) => { await db.setSetting('lang', 'en'); }")
        go('bird/new/'); en_open = text(pg, '[data-testid=sib-open]'); click(pg, '[data-testid=sib-open]')
        en = [texts(pg, '[data-testid=sib-which-btn]'), text(pg, '[data-testid=sib-panel] label')]
        check('[item 15] in English: "Sibling of a recorded bird…", "Both parents" · "Father only" · "Mother only", "From the same clutch"',
              en_open == 'Sibling of a recorded bird…' and en == [['Both parents', 'Father only', 'Mother only'], 'From the same clutch'], (en_open, en))
        run(pg, "async (db) => { await db.setSetting('lang', 'ar'); }")

        check('zero page errors overall', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
