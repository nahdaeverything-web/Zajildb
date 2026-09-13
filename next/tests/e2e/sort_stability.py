#!/usr/bin/env python3
"""RF-7 — every list comparator ends on the record's own id.

WHY THIS EXISTS. A comparator that returns 0 on a tie leaves the order to Array.sort's
stability, which preserves SOURCE order — and source order is `db.state.*`, built from
`idbGetAll()`, which IndexedDB returns in PRIMARY KEY order: the uuid. So two records that
tie on the visible key are ordered by an id nobody can see.

It is stable for a given loft (a uuid never changes), so it does not reshuffle between
reloads. What it is, is arbitrary: a fancier's register, race log, health log, breeding list
and progeny table each order their ties by a hidden random string, and two lofts holding the
same birds order them differently.

HOW THIS SUITE PROVES IT — and the first version of it did NOT.

The obvious fixture does not discriminate. Seeding records and reloading gives an in-memory
order of `idbGetAll()`, and IndexedDB returns rows in PRIMARY KEY order, so the fallback is
ALREADY id-ascending and the unfixed comparator renders exactly what the fixed one does. That
version passed with the tie-break reverted, which means it proved nothing. It was found by
running the proof rather than trusting it.

The case that discriminates is the one a fancier actually hits: records created DURING a
session. A record saved while the page is open goes into `db.state` by INSERTION order — the
Map keeps what it was given — and no reload has re-sorted it by key. So this suite boots with
four records already stored, then adds four more LIVE with ids that sort BEFORE them. The
in-memory order is then 4,5,6,7,3,2,1,0 while id order is 0…7; the unfixed comparator renders
the former and the fixed one the latter. Proven both ways by reverting the clause.

Each assertion names the site it covers. Binds to data-testid only. Provisions its own
server (R6)."""
import os, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


srv, HARNESS = serve()
ROOT = HARNESS.replace('test-harness.html', '')

# Eight ids that sort ASCENDING as id-0 … id-7. They are seeded in that same order, so a
# comparator with no tie-break can only reproduce this sequence if IndexedDB happens to hand
# them back in insertion order — which it does, since these ids are already sorted. The
# discriminating case is the SECOND fixture below, where the ids run the other way.
def ids(n, ascending=True):
    order = range(n) if ascending else range(n - 1, -1, -1)
    return [f'{i:08d}-0000-4000-8000-000000000000' for i in order]


def boot(ctx):
    pg = ctx.new_page(); pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600)
    pg.evaluate("async () => { await window.__zajilReady; }")
    return pg


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 900})
        errs = []
        h = boot(ctx)

        # ── the fixture ──
        # Four records STORED (ids 4..7), then four added LIVE (ids 3,2,1,0 — sorting BEFORE
        # the stored ones). After the reload below, db.state holds the stored four in key
        # order; the live four are appended in the order they are saved. So in-memory order is
        # 4,5,6,7,3,2,1,0 and id order is 0..7 — two different sequences, which is what makes
        # the assertion discriminating. Everything ties on its visible key.
        stored = [f'{i:08d}-0000-4000-8000-000000000000' for i in (4, 5, 6, 7)]
        live = [f'{i:08d}-0000-4000-8000-000000000000' for i in (3, 2, 1, 0)]

        # SEED takes the store to write, because WHICH PAGE FIRST SEES a record decides
        # whether this suite can discriminate at all. A page that boots AFTER the records are
        # stored loads them from IndexedDB in KEY order — already ascending — and re-saving an
        # existing id does not move it in the Map. So each page must be the first to see its
        # OWN live half; seeding all three stores from one page made the races and health
        # assertions pass with the clause reverted, which is to say prove nothing. Found by
        # reverting, not by reading.
        SEED = """async ([kind, idList, loftId]) => {
            const db = await window.__zajilDb;
            const loft = loftId || db.currentLoft().id;
            for (const id of idList) {
                if (kind === 'birds') await db.saveBird(db.newBird({
                    id, name: 'ط-' + id.slice(0, 8), sex: 'cock', hatchDate: '2025-03-01',
                    createdAt: '2026-03-01T08:00:00.000Z', loftId: loft }));
                if (kind === 'races') await db.Races.save({ id, birdId: id, loftId: loft,
                    date: '2026-05-01', raceName: 'س-' + id.slice(0, 8), distanceKm: 300, raceType: 'race' });
                if (kind === 'health') await db.Health.save({ id, birdId: id, loftId: loft,
                    date: '2026-05-01', eventType: 'check', medication: 'ف-' + id.slice(0, 8) });
            }
            return db.currentLoft().id;
        }"""

        loft = h.evaluate("""async () => { const db = await window.__zajilDb;
            for (const x of [...db.state.birds.values()]) await db.deleteBird(x.id);
            for (const r of [...db.state.raceResults.values()]) await db.Races.remove(r.id);
            for (const e of [...db.state.healthEvents.values()]) await db.Health.remove(e.id);
            return db.currentLoft().id; }""")
        for kind in ('birds', 'races', 'health'):
            h.evaluate(SEED, [kind, stored, loft])

        want = [f'{i:08d}' for i in range(8)]          # ids ascending — what the tie-break must give
        inmem = ['00000004', '00000005', '00000006', '00000007', '00000003', '00000002', '00000001', '00000000']

        def order_of(pg, sel, pattern):
            return pg.evaluate(
                "([sel, pat]) => [...document.querySelectorAll(sel)]"
                ".map(e => (e.textContent.match(new RegExp(pat)) || [])[1]).filter(Boolean)",
                [sel, pattern])

        # ── the register, at 1400: the desktop table on its default `year` sort ──
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'{ROOT}birds.html', wait_until='load')
        pg.wait_for_function("document.querySelectorAll('[data-testid=table-row]').length === 4", timeout=8000)
        pg.evaluate(SEED, ['birds', live, loft])   # added LIVE — db.state keeps insertion order
        pg.wait_for_function("document.querySelectorAll('[data-testid=table-row]').length === 8", timeout=8000)
        mem = pg.evaluate("async () => { const db = await window.__zajilDb; return [...db.state.birds.values()].map(b => b.id.slice(0, 8)); }")
        check('the in-memory order is NOT id order — otherwise this suite proves nothing',
              mem != sorted(mem), str(mem))
        got = order_of(pg, '[data-testid=table-row] [data-testid=cell-name]', 'ط-(\\d{8})')
        check('[RF-7 birds/view.tsx:93] the register table breaks a year tie on the id, ascending',
              got == want, f'{got} (in-memory order would be {inmem})')
        check('…and that is NOT the order db.state holds them in', got != inmem)

        # reversing the direction must reverse the KEY, not shuffle the rows that tie on it
        pg.click('[data-testid=th-sort][data-key=year]'); pg.wait_for_timeout(250)
        got_desc = order_of(pg, '[data-testid=table-row] [data-testid=cell-name]', 'ط-(\\d{8})')
        check('[RF-7] flipping the sort direction keeps the tie order stable, it does not reshuffle',
              got_desc == want, str(got_desc))

        # ── the register, at 430: the phone grouping, which sorts on createdAt ──
        pg.set_viewport_size({'width': 430, 'height': 900}); pg.wait_for_timeout(300)
        got_phone = order_of(pg, '[data-testid=bird-row]', 'ط-(\\d{8})')
        check('[RF-7 birds/view.tsx:95] the phone grouping breaks a createdAt tie on the id',
              got_phone == want, f'{got_phone} (in-memory order would be {inmem})')

        # ── the race log: eight races on one date ──
        rp = ctx.new_page(); rp.on('pageerror', lambda e: errs.append(str(e)))
        rp.goto(f'{ROOT}races.html?season=all', wait_until='load')
        rp.wait_for_function("document.querySelectorAll('[data-testid=race-row]').length >= 4", timeout=8000)
        rp.evaluate(SEED, ['races', live, loft])
        rp.wait_for_function("document.querySelectorAll('[data-testid=race-row]').length >= 8", timeout=8000)
        mem_r = rp.evaluate("async () => { const db = await window.__zajilDb; return [...db.state.raceResults.values()].map(r => r.id.slice(0, 8)); }")
        check('races: the in-memory order is NOT id order — otherwise the next check proves nothing',
              mem_r != sorted(mem_r), str(mem_r))
        got_r = order_of(rp, '[data-testid=race-row]', 'س-(\\d{8})')
        check('[RF-7 races/view.tsx:77] the race log breaks a same-date tie on the id',
              got_r[:8] == want, f'{got_r[:8]} (in-memory order would be {inmem})')

        # ── the health log: eight events on one date ──
        hp = ctx.new_page(); hp.on('pageerror', lambda e: errs.append(str(e)))
        hp.goto(f'{ROOT}health.html', wait_until='load')
        hp.wait_for_function("document.querySelectorAll('[data-testid=ev-row]').length >= 4", timeout=8000)
        hp.evaluate(SEED, ['health', live, loft])
        hp.wait_for_function("document.querySelectorAll('[data-testid=ev-row]').length >= 8", timeout=8000)
        mem_h = hp.evaluate("async () => { const db = await window.__zajilDb; return [...db.state.healthEvents.values()].map(e => e.id.slice(0, 8)); }")
        check('health: the in-memory order is NOT id order — otherwise the next check proves nothing',
              mem_h != sorted(mem_h), str(mem_h))
        got_h = order_of(hp, '[data-testid=ev-row]', 'ف-(\\d{8})')
        check('[RF-7 health/view.tsx:66] the health log breaks a same-date tie on the id',
              got_h[:8] == want, f'{got_h[:8]} (in-memory order would be {inmem})')

        check('zero page errors', not errs, '; '.join(errs[:2]))
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
