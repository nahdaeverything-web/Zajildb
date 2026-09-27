#!/usr/bin/env python3
"""RF-12 — importing a loft adopts it when ours is PRISTINE, and refuses to guess otherwise.

THE DEFECT. `initDB()` creates an unnamed default loft on first run and points currentLoftId
at it. Import ADDED the loft a file carries and never adopted it, so the first sequence a new
fancier performs — load the teaching loft, then add a bird — left the register holding birds
of two different lofts: 38 under «لوفت إربد التعليمي» and their own under the unnamed one that
currentLoftId still named. The loft settings card edits that empty loft, so naming it put the
name on a loft containing one bird. NOTHING WARNED, because no screen filters by loftId.

THE RULE, ruled 2026-09-27 and not invented here: it is R4's, which sync.js already applies
when a first sync brings a real loft. If ours is pristine, theirs becomes current and ours is
dropped. The same two functions decide — isPristineLoft() and dropPristineLoft() — so there is
one mechanism, not two.

WHAT IS ASSERTED, and the refusals matter as much as the adoption:
  1. the reported sequence now ends with ONE loft and every bird under it;
  2. a NON-pristine current loft is left alone — named, placed, or holding records, it is
     theirs and which loft is current is not ours to decide;
  3. an import carrying SEVERAL lofts adopts nothing — there is no basis for choosing;
  4. the drop writes NO op and NO tombstone, which is R4's third exception in the
     op-enumeration matrix: the record never existed anywhere but this device, so an op
     describes a deletion no other device can receive and a tombstone suppresses a row that
     was never pushed. Mutation-proved: the guard is removed and the assertion must fail.

Provisions its own server (R6)."""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sync'))
from _serve import serve

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok)
    print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


# the raw stores, so nothing is read through the layer that is under test
RAW = """async () => new Promise((res) => {
  const r = indexedDB.open('zajil');
  r.onsuccess = () => {
    const db = r.result;
    const stores = ['lofts', 'settings', 'birds', 'oplog', 'tombstones'];
    const tx = db.transaction(stores, 'readonly');
    const out = {}; let left = stores.length;
    const done = () => { if (--left === 0) res({
      lofts: out.lofts.map(l => ({ id: l.id, name: l.name || '' })),
      currentLoftId: (out.settings.find(s => s.key === 'currentLoftId') || {}).value,
      birds: out.birds.length,
      byLoft: out.birds.reduce((a, b) => { const k = b.loftId || 'NONE'; a[k] = (a[k] || 0) + 1; return a; }, {}),
      loftOps: out.oplog.filter(o => o.store === 'lofts').map(o => `${o.op}:${o.recordId}`),
      loftTombstones: out.tombstones.filter(t => (t.store || '') === 'lofts').map(t => t.id),
    }); };
    for (const s of stores) { const q = tx.objectStore(s).getAll(); q.onsuccess = () => { out[s] = q.result; done(); }; }
  };
})"""

WIPE = """async () => { await window.__zajilReady; const db = await window.__zajilDb;
    for (const b of db.allBirds()) await db.deleteBird(b.id); }"""

LOAD_EXAMPLE = """async () => { const db = await window.__zajilDb;
    await db.importAll(await (await fetch(new URL('example-loft-large.json',
        document.querySelector('link[rel=manifest]').href))).json(), 'merge'); }"""

srv, HARNESS = serve()
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        def fresh():
            """A brand-new storage partition: first run, one pristine loft, no birds."""
            ctx = b.new_context(viewport={'width': 430, 'height': 900})
            pg = ctx.new_page(); pg.set_default_timeout(60000)
            pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(900)
            pg.evaluate("async () => { await window.__zajilReady; }")
            return ctx, pg

        # ── 1. THE REPORTED SEQUENCE ──────────────────────────────────────────────
        ctx, pg = fresh()
        before = pg.evaluate(RAW)
        check('first run: exactly one loft, unnamed, and it is current',
              len(before['lofts']) == 1 and before['lofts'][0]['name'] == ''
              and before['currentLoftId'] == before['lofts'][0]['id'],
              f"{len(before['lofts'])} loft(s)")
        pristine_id = before['lofts'][0]['id']

        pg.evaluate(LOAD_EXAMPLE); pg.wait_for_timeout(1200)
        after = pg.evaluate(RAW)
        check('after importing the teaching loft: the pristine loft is GONE',
              pristine_id not in [l['id'] for l in after['lofts']],
              f"{len(after['lofts'])} loft(s): {[l['name'] or '(unnamed)' for l in after['lofts']]}")
        check('…exactly one loft remains, and it is the imported, NAMED one',
              len(after['lofts']) == 1 and after['lofts'][0]['name'].strip() != '',
              f"{[l['name'] or '(unnamed)' for l in after['lofts']]}")
        check('…and it is current', after['currentLoftId'] == after['lofts'][0]['id'])
        check('…with all 38 imported birds under it',
              after['byLoft'].get(after['lofts'][0]['id']) == 38, str(after['byLoft']))

        # the step that made the split visible: a bird added AFTER the import
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            await db.saveBird(db.newBird({ name: 'PROBE', sex: 'cock', hatchDate: '2026-01-01' })); }""")
        pg.wait_for_timeout(600)
        end = pg.evaluate(RAW)
        check('a bird added afterwards is filed under THE SAME loft as the other 38',
              len(end['lofts']) == 1 and end['birds'] == 39
              and end['byLoft'].get(end['lofts'][0]['id']) == 39,
              f"{end['birds']} birds across {len(end['byLoft'])} loft(s): {end['byLoft']}")

        # ── 4. THE DROP IS SILENT — no op, no tombstone (R4's third exception) ────
        check('[R4] dropping the pristine loft logged NO op',
              not [o for o in end['loftOps'] if o.startswith('delete:' + pristine_id)],
              str(end['loftOps'][:4]))
        check('[R4] …and wrote NO tombstone',
              pristine_id not in end['loftTombstones'], str(end['loftTombstones'][:4]))
        ctx.close()

        # ── 2. REFUSAL: the current loft is NOT pristine ──────────────────────────
        ctx, pg = fresh()
        mine = pg.evaluate(RAW)['lofts'][0]['id']
        pg.evaluate("""async (id) => { const db = await window.__zajilDb;
            const l = { ...db.state.lofts.get(id), name: 'لوفت سمير' };
            await db.Lofts.save(l); }""", mine)
        pg.wait_for_timeout(500)
        named = pg.evaluate(RAW)
        check('[refusal setup] the current loft is now NAMED, so not pristine',
              named['lofts'][0]['name'] == 'لوفت سمير', named['lofts'][0]['name'])
        pg.evaluate(LOAD_EXAMPLE); pg.wait_for_timeout(1200)
        kept = pg.evaluate(RAW)
        check('[REFUSAL] a NAMED current loft is left alone — both lofts survive',
              len(kept['lofts']) == 2 and mine in [l['id'] for l in kept['lofts']],
              f"{len(kept['lofts'])} loft(s)")
        check('…and it is still current: whose loft this is was never ours to decide',
              kept['currentLoftId'] == mine, kept['currentLoftId'])
        ctx.close()

        # ── 2b. REFUSAL: pristine by name, but HOLDING A RECORD ───────────────────
        ctx, pg = fresh()
        mine2 = pg.evaluate(RAW)['lofts'][0]['id']
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            await db.saveBird(db.newBird({ name: 'MINE', sex: 'hen', hatchDate: '2025-01-01' })); }""")
        pg.wait_for_timeout(500)
        pg.evaluate(LOAD_EXAMPLE); pg.wait_for_timeout(1200)
        held = pg.evaluate(RAW)
        check('[REFUSAL] an unnamed loft that HOLDS A BIRD is not pristine — both survive',
              len(held['lofts']) == 2 and held['currentLoftId'] == mine2,
              f"{len(held['lofts'])} loft(s), current={held['currentLoftId'] == mine2}")
        check('…and that bird kept its loftId, which dropping the loft would have orphaned',
              held['byLoft'].get(mine2) == 1, str(held['byLoft']))
        ctx.close()

        # ── 3. REFUSAL: the import carries SEVERAL lofts ──────────────────────────
        ctx, pg = fresh()
        mine3 = pg.evaluate(RAW)['lofts'][0]['id']
        pg.evaluate("""async () => { const db = await window.__zajilDb;
            const payload = await (await fetch(new URL('example-loft-large.json',
                document.querySelector('link[rel=manifest]').href))).json();
            // the same file, carrying a SECOND loft: no basis for choosing between them
            const extra = { ...payload.lofts[0], id: '00000000-0000-4000-8000-00000000beef',
                            name: 'لوفت آخر' };
            payload.lofts = [...payload.lofts, extra];
            await db.importAll(payload, 'merge'); }""")
        pg.wait_for_timeout(1200)
        many = pg.evaluate(RAW)
        check('[REFUSAL] an import carrying SEVERAL lofts adopts nothing',
              many['currentLoftId'] == mine3 and mine3 in [l['id'] for l in many['lofts']],
              f"{len(many['lofts'])} loft(s), current is still ours: {many['currentLoftId'] == mine3}")
        ctx.close()
        b.close()
finally:
    srv.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
