#!/usr/bin/env python3
"""The three-way delete — RULED 2026-10-03.

WHY. Delete is the only visible control meaning "not mine any more", so a fancier who sells or
loses a bird reaches for it. Measured on the teaching loft before this existed: deleting one
ancestor took a DESCENDANT's pedigree from 30 known nodes to 27 and its COI from 12.5% to
10.5% — a different number, for a bird the fancier was not looking at, with nothing on screen
to say why. The data model already had the non-destructive answer (external / مرجع نسب); the
UI never offered it at the moment of deletion.

WHAT IS ASSERTED. The dialog, and the two things that must remain true either side of it:

  1. the three-way choice appears ONLY for a bird with descendants;
  2. «أصبح مرجع نسب» leaves offspring links, pedigree nodes and the descendant's COI EXACTLY
     as they were — the whole point, so it is measured on a descendant and not on the bird;
  3. «حذف نهائيًا» behaves exactly as delete behaved before;
  4. a bird with pairs/races/health but NO offspring still gets the old two-button dialog.
     Those are its own records and losing them is what was asked for — the third answer exists
     for damage to records that are not this bird's.

(4) is the mutation-provable half: widen the test from "has descendants" to anything else and
this is the assertion that fails.

Binds to data-testid only. Provisions its own server (R6)."""
import os
import sys
import uuid as _uuid

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve

_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
bid = lambda k: str(_uuid.uuid5(_NS, k))
SUBJECT = bid('g5-faris26')          # the descendant whose pedigree and COI must not move

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok)
    print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

PED = """() => {
  const all = [...document.querySelectorAll('[data-testid=node]')];
  const b = document.querySelector('[data-testid=coi-headline] [data-testid=coi-badge]');
  return { known: all.filter(n => n.getAttribute('data-known') === '1').length,
           unknown: all.filter(n => n.getAttribute('data-known') === '0').length,
           coi: b ? b.textContent.trim() : '(absent)' }; }"""

LINKS = """async (id) => { const db = await window.__zajilDb;
  const kids = db.allBirds().filter(b => b.sireId === id || b.damId === id);
  const v = db.getBird(id);
  return { exists: !!v, external: v ? !!v.external : null, kids: kids.length,
           birds: db.allBirds().length }; }"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        def seeded():
            ctx = b.new_context(viewport={'width': 430, 'height': 900})
            pg = ctx.new_page(); pg.set_default_timeout(60000)
            pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(900)
            pg.evaluate("async () => { await window.__zajilReady; }")
            pg.evaluate("""async () => { const db = await window.__zajilDb;
                await db.importAll(await (await fetch(new URL('example-loft-large.json',
                  document.querySelector('link[rel=manifest]').href))).json(), 'merge'); }""")
            return ctx, pg

        def open_delete(pg, bird_id):
            pg.goto(f'{ROOT}bird/?id={bird_id}', wait_until='load'); pg.wait_for_timeout(2000)
            pg.click('[aria-haspopup=menu]'); pg.wait_for_timeout(500)
            pg.click('[data-testid=menu-delete]'); pg.wait_for_timeout(1000)
            return pg.evaluate("""() => ({
                alt: !!document.querySelector('[data-testid=dialog-alt]'),
                altText: (document.querySelector('[data-testid=dialog-alt]') || {}).textContent,
                confirmText: (document.querySelector('[data-testid=dialog-confirm]') || {}).textContent,
                body: (document.querySelector('[data-testid=dialog]') || {}).innerText })""")

        # ── a bird WITH descendants: the ancestor whose removal moved the COI ──────
        ctx, pg = seeded()
        VICT = pg.evaluate("""async () => { const db = await window.__zajilDb; const bs = db.allBirds();
            const v = bs.find(x => x.name === 'دانة'); return v.id; }""")
        pg.goto(f'{ROOT}pedigree/?id={SUBJECT}', wait_until='load'); pg.wait_for_timeout(2200)
        base_ped = pg.evaluate(PED)
        base_links = pg.evaluate(LINKS, VICT)
        check('[baseline] the descendant has a full pedigree and a COI',
              base_ped['known'] == 30 and base_ped['coi'] == '12.5%', str(base_ped))

        d = open_delete(pg, VICT)
        check('a bird WITH descendants gets the three-way dialog', d['alt'], str(d['altText']))
        check('…the alt action offers the reference path', d['altText'] == 'أصبح مرجع نسب', repr(d['altText']))
        check('…the destructive action is named «حذف نهائيًا»', d['confirmText'] == 'حذف نهائيًا', repr(d['confirmText']))
        check('…and the body states the CONSEQUENCE, not a count of records',
              'معامل التآلف' in (d['body'] or '') and 'النسل' in (d['body'] or ''),
              repr((d['body'] or '').replace('\n', ' | ')[:150]))

        # ── choosing the reference path ──────────────────────────────────────────
        pg.click('[data-testid=dialog-alt]'); pg.wait_for_timeout(2500)
        after = pg.evaluate(LINKS, VICT)
        check('«أصبح مرجع نسب» keeps the bird, and marks it external',
              after['exists'] and after['external'] and after['birds'] == base_links['birds'], str(after))
        check('…offspring links are untouched', after['kids'] == base_links['kids'],
              f"{after['kids']} vs {base_links['kids']}")
        pg.goto(f'{ROOT}pedigree/?id={SUBJECT}', wait_until='load'); pg.wait_for_timeout(2200)
        ped2 = pg.evaluate(PED)
        check('…the DESCENDANT\'s pedigree is unchanged', ped2['known'] == base_ped['known']
              and ped2['unknown'] == base_ped['unknown'], f"{ped2} vs {base_ped}")
        check('…and its COI is unchanged — the whole point',
              ped2['coi'] == base_ped['coi'], f"{ped2['coi']} vs {base_ped['coi']}")
        ctx.close()

        # ── choosing delete anyway: exactly the old behaviour ────────────────────
        ctx, pg = seeded()
        open_delete(pg, VICT)
        pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(2500)
        gone = pg.evaluate(LINKS, VICT)
        check('«حذف نهائيًا» deletes as before — bird gone, links cleared',
              not gone['exists'] and gone['kids'] == 0 and gone['birds'] == base_links['birds'] - 1, str(gone))
        pg.goto(f'{ROOT}pedigree/?id={SUBJECT}', wait_until='load'); pg.wait_for_timeout(2200)
        ped3 = pg.evaluate(PED)
        check('…and the descendant\'s pedigree and COI change, as they always did',
              ped3['known'] < base_ped['known'] and ped3['coi'] != base_ped['coi'],
              f"{ped3} vs {base_ped}")
        ctx.close()

        # ── THE REFUSAL: records of its own are not someone else's pedigree ──────
        ctx, pg = seeded()
        NOKIDS = pg.evaluate("""async () => { const db = await window.__zajilDb; const s = db.state;
            const bs = db.allBirds();
            const v = bs.find(x => !bs.some(y => y.sireId === x.id || y.damId === x.id)
              && ([...s.pairs.values()].some(q => q.sireId === x.id || q.damId === x.id)
                  || [...s.raceResults.values()].some(r => r.birdId === x.id)));
            if (!v) return null;
            return { id: v.id, name: v.name,
                     pairs: [...s.pairs.values()].filter(q => q.sireId === v.id || q.damId === v.id).length,
                     races: [...s.raceResults.values()].filter(r => r.birdId === v.id).length }; }""")
        check('[setup] found a bird with its OWN records but no offspring',
              NOKIDS is not None, str(NOKIDS))
        if NOKIDS:
            d2 = open_delete(pg, NOKIDS['id'])
            check('a bird with pairs/races but NO offspring gets the OLD two-button dialog',
                  not d2['alt'],
                  f"{NOKIDS['name']}: pairs={NOKIDS['pairs']} races={NOKIDS['races']}; "
                  f"alt button present = {d2['alt']}")
            check('…and its destructive button is still the plain «حذف»',
                  d2['confirmText'] == 'حذف', repr(d2['confirmText']))
        ctx.close()

        # ── AN EXTERNAL BIRD CAN SAY IT DIED (RULED 2026-10-03) ──────────────────
        # The status field used to be hidden entirely when a bird was external, AND collect()
        # forced the status back to `reference` on every save — so even reaching the control
        # would not have helped. A fancier who records a pedigree ancestor and later learns it
        # died had nothing true to write down.
        #
        # The vocabulary is narrowed rather than the field hidden: «تربية», «فريق السباق»,
        # «فرخ», «احتياط» are jobs a bird does in THIS loft, and «مباع» / «مفقود» happen to a
        # bird you owned — none can be true of an ancestor that was never yours. «نافق» is a
        # fact about the bird, not about ownership, so it stays.
        ctx, pg = seeded()
        EXT = pg.evaluate("""async () => { const db = await window.__zajilDb;
            const v = db.allBirds().find(b => b.external);
            return { id: v.id, name: v.name, status: v.status }; }""")
        check('[setup] an external bird, carrying the reference status',
              EXT['status'] == 'reference', str(EXT))
        pg.goto(f"{ROOT}bird/edit/?id={EXT['id']}", wait_until='load'); pg.wait_for_timeout(2200)
        chips = pg.evaluate("""() => { const f = document.querySelector('[data-testid=f-status]');
            return f ? [...f.querySelectorAll('button')].map(x => x.getAttribute('data-status')) : null; }""")
        check('the status field is SHOWN for an external bird', chips is not None, str(chips))
        check('…offering reference and dead, and nothing that contradicts being external',
              chips is not None and set(chips) == {'reference', 'dead'}, str(chips))
        check('…specifically: no «مباع», «مفقود», «تربية» or «فريق السباق» on a reference bird',
              chips is not None and not ({'sold', 'lost', 'breeder', 'race team'} & set(chips)), str(chips))

        pg.click('[data-testid=status-chip][data-status=dead]'); pg.wait_for_timeout(400)
        pg.click('[data-testid=save-btn]'); pg.wait_for_timeout(3000)
        stored = pg.evaluate("""async (id) => { const db = await window.__zajilDb;
            const v = db.getBird(id); return { status: v.status, external: !!v.external }; }""", EXT['id'])
        check('choosing «نافق» PERSISTS — collect() no longer forces it back to reference',
              stored['status'] == 'dead', str(stored))
        check('…and the bird is still external', stored['external'] is True, str(stored))
        ctx.close()
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
