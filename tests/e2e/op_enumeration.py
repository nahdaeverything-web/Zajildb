import os
from playwright.sync_api import sync_playwright
BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

with sync_playwright() as p:
    br = p.chromium.launch(); page = br.new_page(); page.set_default_timeout(25000)
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2000)

    # ══ THE MATRIX: one op per record touched, with the right op and origin ══
    # Every mutation type is exercised and its ops read back through the SORTED
    # reader (idbGetAll returns key order — a random uuid — so raw reads shuffle).
    m = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const mark = async () => Math.max(0, ...(await db.listOps()).map(o => o.seq));
        const since = (s) => db.getOpsSinceSeq(s);
        const sig = (ops) => ops.map(o => `${o.origin}:${o.store}:${o.op}`).sort();
        const out = {};

        // --- bird save (create) ---
        let s = await mark();
        const b = await db.saveBird(db.newBird({ name: 'matrix', sex: 'cock' }));
        out.birdCreate = sig(await since(s));

        // --- bird save (edit) ---
        s = await mark();
        await db.saveBird({ ...db.getBird(b.id), name: 'matrix-2' });
        out.birdEdit = sig(await since(s));

        // --- generic save / remove / restore, one per store ---
        for (const [label, api, store, rec] of [
            ['race',   db.Races,  'raceResults',  { id: 'mx-r', birdId: b.id, date: '2026-01-01', raceType: 'club' }],
            ['health', db.Health, 'healthEvents', { id: 'mx-h', birdId: b.id, date: '2026-01-01', wholeLoft: false }],
            ['pair',   db.Pairs,  'pairs',        { id: 'mx-p', sireId: b.id, damId: null, season: '2026', rounds: [] }],
        ]) {
            s = await mark(); await api.save({ ...rec });          out[label + 'Save']    = sig(await since(s));
            s = await mark(); const snap = await api.remove(rec.id); out[label + 'Remove'] = sig(await since(s));
            s = await mark(); await api.restore(snap);             out[label + 'Restore'] = sig(await since(s));
            await api.remove(rec.id);                              // tidy up
        }

        // --- media add / delete / restore ---
        const blob = new Blob([new Uint8Array(64)], { type: 'image/png' });
        s = await mark(); const md = await db.addMedia(b.id, 'photo', 'body', 'm.png', blob);
        out.mediaAdd = sig(await since(s));
        s = await mark(); const msnap = await db.deleteMedia(md.id);
        out.mediaDelete = sig(await since(s));
        s = await mark(); await db.restoreMedia(msnap);
        out.mediaRestore = sig(await since(s));

        // --- bird delete WITH a full cascade, then undo ---
        const b2 = await db.saveBird(db.newBird({ name: 'cascade-target', sex: 'hen' }));
        await db.Races.save({ id: 'cx-r', birdId: b2.id, date: '2026-01-01', raceType: 'club' });
        await db.Health.save({ id: 'cx-h', eventType: 'check', birdId: b2.id, date: '2026-01-01', wholeLoft: false });
        await db.Pairs.save({ id: 'cx-p', sireId: null, damId: b2.id, season: '2026', rounds: [] });
        await db.addMedia(b2.id, 'photo', 'body', 'c.png', blob);
        const child = await db.saveBird(db.newBird({ name: 'child', sex: 'cock', damId: b2.id }));

        s = await mark();
        const snap2 = await db.deleteBird(b2.id);
        const delOps = await since(s);
        out.cascadeDelete = sig(delOps);
        const tsAfterDelete = (await db.listTombstones()).filter(t =>
            ['cx-r','cx-h','cx-p', b2.id].includes(t.recordId) || (t.store === 'media' && t.recordId === undefined ? false : false));
        out.tombstoneStores = [...new Set((await db.listTombstones())
            .filter(t => ['cx-r','cx-h','cx-p'].includes(t.recordId) || t.recordId === b2.id)
            .map(t => t.store))].sort();
        out.mediaTombstoned = (await db.listTombstones()).some(t => t.store === 'media');

        s = await mark();
        await db.restoreBird(snap2);
        out.cascadeUndo = sig(await since(s));
        out.tombstonesLeft = (await db.listTombstones())
            .filter(t => ['cx-r','cx-h','cx-p'].includes(t.recordId) || t.recordId === b2.id).length;

        // --- import ---
        s = await mark();
        await db.importAll({ format: 'zajil-export', version: 1, exportedAt: new Date().toISOString(),
            lofts: [], birds: [{ id: 'mx-import', rings: [], name: 'imported', sex: 'hen', external: false,
                status: 'stock', sireId: null, damId: null, notes: [], updatedAt: new Date().toISOString() }],
            pairs: [], raceResults: [], healthEvents: [], media: [], tombstones: [] }, 'merge');
        out.import = sig(await since(s));

        // --- an import that SKIPS must log nothing ---
        s = await mark();
        await db.importAll({ format: 'zajil-export', version: 1, exportedAt: new Date().toISOString(),
            lofts: [], birds: [{ id: 'mx-import', rings: [], name: 'stale', sex: 'hen', external: false,
                status: 'stock', sireId: null, damId: null, notes: [],
                updatedAt: '2000-01-01T00:00:00.000Z' }],
            pairs: [], raceResults: [], healthEvents: [], media: [], tombstones: [] }, 'merge');
        out.importSkipped = (await since(s)).length;

        return out;
    }""")

    check('bird create → one user put', m['birdCreate'] == ['user:birds:put'], str(m['birdCreate']))
    check('bird edit → one user put', m['birdEdit'] == ['user:birds:put'], str(m['birdEdit']))
    for label, store in [('race', 'raceResults'), ('health', 'healthEvents'), ('pair', 'pairs')]:
        check(f'{label} save → one user put', m[label+'Save'] == [f'user:{store}:put'], str(m[label+'Save']))
        check(f'{label} remove → one user delete', m[label+'Remove'] == [f'user:{store}:delete'], str(m[label+'Remove']))
        check(f'{label} restore → one RESTORE put', m[label+'Restore'] == [f'restore:{store}:put'], str(m[label+'Restore']))
    check('media add → one user put', m['mediaAdd'] == ['user:media:put'], str(m['mediaAdd']))
    check('media delete → one user delete', m['mediaDelete'] == ['user:media:delete'], str(m['mediaDelete']))
    check('media restore → one RESTORE put', m['mediaRestore'] == ['restore:media:put'], str(m['mediaRestore']))

    # cascade: every removed record logged as a user delete, the child rewrite as a put
    casc = m['cascadeDelete']
    check('cascade logs the bird delete', 'user:birds:delete' in casc, str(casc))
    check('cascade logs the child rewrite as a PUT not a delete',
          'user:birds:put' in casc and casc.count('user:birds:delete') == 1, str(casc))
    check('cascade logs the race delete', 'user:raceResults:delete' in casc)
    check('cascade logs the health delete', 'user:healthEvents:delete' in casc)
    check('cascade logs the pair delete', 'user:pairs:delete' in casc)
    check('cascade logs the media delete (A1)', 'user:media:delete' in casc)
    check('every cascade op carries origin user', all(x.startswith('user:') for x in casc), str(casc))

    check('cascade tombstoned every store it removed from',
          set(m['tombstoneStores']) == {'birds', 'raceResults', 'healthEvents', 'pairs'}, str(m['tombstoneStores']))
    check('cascade tombstoned media too (A1)', m['mediaTombstoned'])

    undo = m['cascadeUndo']
    check('undo logs only RESTORE ops', all(x.startswith('restore:') for x in undo) and len(undo) > 0, str(undo))
    check('undo removed every tombstone the cascade wrote', m['tombstonesLeft'] == 0, str(m['tombstonesLeft']))

    check('import → one IMPORT put per record written', m['import'] == ['import:birds:put'], str(m['import']))
    check('a skipped import record logs NOTHING', m['importSkipped'] == 0, str(m['importSkipped']))

    # ══ REFINEMENT 3: manufacture a live record + tombstone, assert it is caught ══
    clash = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const { checkIntegrity } = await import('./js/engine/integrity.js');
        const snap = async () => ({
            birds: db.state.birds, pairs: db.state.pairs,
            raceResults: db.state.raceResults, healthEvents: db.state.healthEvents,
            tombstones: await db.listTombstones(),
        });
        const before = checkIntegrity(await snap()).length;
        // manufacture the inconsistency DIRECTLY: a live bird plus a tombstone
        const b = await db.saveBird(db.newBird({ name: 'ghost-and-alive', sex: 'cock' }));
        await db.idbPut('tombstones', { id: 'birds:' + b.id, store: 'birds', recordId: b.id,
            at: new Date().toISOString(), deviceId: db.state.settings.deviceId, seq: 999999 });
        const found = checkIntegrity(await snap());
        const mine = found.filter(x => x.key === 'integrity.liveWithTombstone' && x.params.recordId === b.id);
        // clean up and confirm it goes away
        await db.idbDelete('tombstones', 'birds:' + b.id);
        const after = checkIntegrity(await snap()).length;
        return { before, hit: mine.length, after };
    }""")
    check('database starts consistent', clash['before'] == 0, str(clash['before']))
    check('a live record WITH a tombstone is reported', clash['hit'] == 1, str(clash['hit']))
    check('and the report clears once the state is fixed', clash['after'] == 0, str(clash['after']))

    # ══ normal operation never produces that state ══
    normal = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const { checkIntegrity } = await import('./js/engine/integrity.js');
        const b = await db.saveBird(db.newBird({ name: 'normal-cycle', sex: 'hen' }));
        const snap = await db.deleteBird(b.id);
        const afterDelete = checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs,
            raceResults: db.state.raceResults, healthEvents: db.state.healthEvents,
            tombstones: await db.listTombstones() }).length;
        await db.restoreBird(snap);
        const afterUndo = checkIntegrity({ birds: db.state.birds, pairs: db.state.pairs,
            raceResults: db.state.raceResults, healthEvents: db.state.healthEvents,
            tombstones: await db.listTombstones() }).length;
        return { afterDelete, afterUndo };
    }""")
    check('delete leaves the database consistent', normal['afterDelete'] == 0, str(normal['afterDelete']))
    check('undo leaves the database consistent', normal['afterUndo'] == 0, str(normal['afterUndo']))

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
