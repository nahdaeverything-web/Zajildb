#!/usr/bin/env python3
"""THE PAIR OFFER (ORDERED 2026-11-20). Found on Samir's data: he set a father and a mother on two youngsters, never
made the breeding pair, and believed he had. A bird saved with both parents SET OR CHANGED by that save, when no pair
of that cock and that hen exists in any season, is offered the pair — a question, never a record made for him — and
«إنشاء الزوج» opens the new-pair sheet with both parents filled. Never for an external or reference parent.
Fixture names are invented; local only, nothing leaves the page.

    python3 tests/e2e/screens/pair_offer.py
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
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)[:400]) if not ok and d != '' else ''}")
def run(pg, js, *a): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(a))

SEED = """async (db) => {
    const loftId = db.currentLoft() && db.currentLoft().id;
    const mk = async (name, sex, extra = {}) => (await db.saveBird(db.newBird({ name, sex, loftId, ...extra }))).id;
    const ids = { barq: await mk('برق', 'cock'), ghayma: await mk('غيمة', 'hen'), saqr: await mk('صقر', 'cock'), najma: await mk('نجمة', 'hen'),
                  ref: await mk('جد مرجعي', 'cock', { external: true }), hadeel: await mk('هديل', 'hen') };
    await db.Pairs.save({ sireId: ids.saqr, damId: ids.najma, season: '2025', nestBox: '4', status: 'separated', rounds: [] });   // another season, not active
    ids.old = (await db.saveBird(db.newBird({ name: 'فرخ قديم', sex: 'cock', loftId, sireId: ids.barq, damId: ids.hadeel }), { allowWarnings: true })).id;
    return ids; }"""
PAIRS = "async (db) => [...db.state.pairs.values()].map(p => [p.sireId, p.damId])"

def save_and_see(pg, name=None):
    """Press save on the open form; answer what follows within 6 s: the offer's dialog, or the page it went to."""
    if name is not None: pg.fill('[data-testid=f-name]', name)
    pg.click('[data-testid=save-btn]')
    try:
        pg.wait_for_function("() => document.querySelector('[data-testid=dialog]') || /\\/bird\\/\\?id=/.test(location.href) || /\\/birds\\/?$/.test(location.pathname)", timeout=6000)
    except Exception: return ('nothing', pg.url)
    if pg.locator('[data-testid=dialog]').count():
        d = pg.locator('[data-testid=dialog]')
        return ('dialog', d.locator('h3').inner_text().strip(), (d.locator('p').all_inner_texts() or [''])[0].strip())
    return ('page', pg.url)

srv, HARNESS = serve(); ROOT = HARNESS.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e, _p=pg: errs.append(perr(e, _p)))
        pg.goto(HARNESS, wait_until='load'); pg.wait_for_function('window.__zajilReady')
        ids = run(pg, SEED); pairs0 = run(pg, PAIRS)
        def new_form(sire=None, dam=None):
            q = '&'.join(x for x in ((f'sire={sire}' if sire else ''), (f'dam={dam}' if dam else '')) if x)
            pg.goto(ROOT + 'bird/new/' + (('?' + q) if q else ''), wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]')

        # ── a youngster given a father and a mother that are not a pair: the offer ──
        new_form(ids['barq'], ids['ghayma']); seen = save_and_see(pg, 'فرخ أول')
        check('[offer · M-nooffer fails here] saving a youngster with both parents, and no pair of the two in any season, ASKS: «لا يوجد زوج تربية لهذين الأبوين»',
              seen[0] == 'dialog' and seen[1] == 'لا يوجد زوج تربية لهذين الأبوين', seen)
        check('[offer] the question names both parents: «اخترت برق أبًا وغيمة أمًّا، ولا يوجد في السجل زوج تربية يجمعهما. هل تريد إنشاء هذا الزوج الآن؟»',
              seen[0] == 'dialog' and seen[2] == 'اخترت برق أبًا وغيمة أمًّا، ولا يوجد في السجل زوج تربية يجمعهما. هل تريد إنشاء هذا الزوج الآن؟', seen)
        btns = [x.strip() for x in pg.locator('[data-testid=dialog] button').all_inner_texts()] if seen[0] == 'dialog' else []
        ty = [(x['why'], x['face'], x['text']) for x in pg.evaluate(SCAN)]
        check('[offer] its two answers are «ليس الآن» and «إنشاء الزوج»; all of it in a face that has Arabic', btns == ['ليس الآن', 'إنشاء الزوج'] and not ty, (btns, ty[:3]))
        if seen[0] == 'dialog': pg.click('[data-testid=dialog-cancel]')
        try: pg.wait_for_url(re.compile(r'/bird/\?id='), timeout=6000)
        except Exception: pass
        check('[offer · never automatic] «ليس الآن»: the bird is saved and shown, and NO pair was made', '/bird/?id=' in pg.url and run(pg, PAIRS) == pairs0, (pg.url, run(pg, PAIRS)))

        # ── the second youngster: this time «إنشاء الزوج» opens the new-pair sheet with both parents filled ──
        new_form(ids['barq'], ids['ghayma']); seen = save_and_see(pg, 'فرخ ثان')
        check('[offer] the second youngster of the same two is offered again — there is still no pair', seen[0] == 'dialog', seen)
        if seen[0] == 'dialog': pg.click('[data-testid=dialog-confirm]')
        got = False
        try: pg.wait_for_selector('[data-testid=sheet-new]', timeout=6000); got = True
        except Exception: pass
        picks = [pg.locator(f'[data-testid={k}-btn]').inner_text().strip() if got else '' for k in ('f-sire', 'f-dam')]
        check('[offer · M-noprefill fails here] «إنشاء الزوج» opens the new-pair sheet with برق as father and غيمة as mother',
              got and '/breeding' in pg.url and 'برق' in picks[0] and 'غيمة' in picks[1], (pg.url, picks))
        check('[offer] the youngster was saved before anything else happened', any(x['name'] == 'فرخ ثان' for x in run(pg, "async (db) => db.allBirds().map(b => ({ name: b.name }))")))
        if got:
            pg.fill('[data-testid=f-nest]', '12'); pg.click('[data-testid=sheet-save]')
            try: pg.wait_for_url(re.compile(r'/pair/\?id='), timeout=6000)
            except Exception: pass
        check('[offer] saving the sheet makes the pair, and opens it', '/pair/?id=' in pg.url and [ids['barq'], ids['ghayma']] in run(pg, PAIRS), pg.url)

        # ── no offer when it has nothing to offer ──
        new_form(ids['barq'], ids['ghayma']); seen = save_and_see(pg, 'فرخ ثالث')
        check('[no offer] once the pair exists, a third youngster of the two is saved without a question', seen[0] == 'page', seen)
        new_form(ids['saqr'], ids['najma']); seen = save_and_see(pg, 'فرخ صقر')
        check('[no offer] a pair of the two in ANOTHER season, separated, counts: no question', seen[0] == 'page', seen)
        new_form(ids['ref'], ids['ghayma']); seen = save_and_see(pg, 'فرخ مرجعي')
        check('[no offer · M-offerref fails here] a reference (external) parent is never offered a pair', seen[0] == 'page', seen)
        new_form(ids['barq'], None); seen = save_and_see(pg, 'فرخ بأب')
        check('[no offer] one parent only: no question', seen[0] == 'page', seen)
        pg.goto(ROOT + 'bird/edit/?id=' + ids['old'], wait_until='load'); pg.wait_for_selector('[data-testid=bird-form]'); seen = save_and_see(pg, 'فرخ قديم مُعدّل')
        check('[no offer · M-offerevery fails here] editing a bird whose parents this save did NOT change asks nothing — even with no pair of its parents', seen[0] == 'page', seen)
        check('[no offer] …nothing was made by any of these saves', sorted(map(tuple, run(pg, PAIRS))) == sorted(map(tuple, pairs0 + [[ids['barq'], ids['ghayma']]])), run(pg, PAIRS))

        check('zero page errors overall', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()
print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
