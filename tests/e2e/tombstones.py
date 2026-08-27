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
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.wait_for_timeout(600)

    # ── a simple delete writes exactly one tombstone ──
    simple = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'doomed', sex: 'cock' }));
        const before = (await db.idbGetAll('tombstones')).length;
        const snap = await db.deleteBird(b.id);
        const ts = await db.idbGetAll('tombstones');
        const mine = ts.find(t => t.recordId === b.id);
        return { added: ts.length - before, mine, id: b.id };
    }""")
    check('a delete writes one tombstone', simple['added'] == 1, str(simple['added']))
    t = simple['mine']
    for f in ['id', 'store', 'recordId', 'at', 'deviceId', 'seq']:
        check(f'tombstone carries {f}', f in t, str(sorted(t.keys())))
    check('tombstone id is store:recordId', t['id'] == f"birds:{simple['id']}", t['id'])

    # ── A1: the CASCADE tombstones races, health, pairs AND MEDIA ──
    casc = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const target = 'g4-wisam';                       // has races + a pair
        await db.Health.save({ id: 'ts-h', eventType: 'check', birdId: target, date: '2026-01-01', wholeLoft: false });
        const blob = new Blob([new Uint8Array(512)], { type: 'image/png' });
        const m = await db.addMedia(target, 'photo', 'body', 'ts.png', blob);
        const races = [...db.state.raceResults.values()].filter(r => r.birdId === target).map(r => r.id);
        const pairs = [...db.state.pairs.values()].filter(p => p.sireId === target || p.damId === target).map(p => p.id);
        const eggPairs = [...db.state.pairs.values()]
            .filter(p => (p.rounds||[]).some(r => (r.eggs||[]).some(e => e.chickId === target))).map(p => p.id);
        const snap = await db.deleteBird(target);
        const ts = await db.idbGetAll('tombstones');
        const has = (s, id) => ts.some(x => x.store === s && x.recordId === id);
        return {
            bird:   has('birds', target),
            races:  races.every(id => has('raceResults', id)),  raceN: races.length,
            health: has('healthEvents', 'ts-h'),
            pairs:  pairs.every(id => has('pairs', id)),        pairN: pairs.length,
            media:  has('media', m.id),
            eggPairsTombstoned: eggPairs.some(id => has('pairs', id)),   // must be FALSE: an unlink is a put
            snap,
        };
    }""")
    check('cascade: the bird itself is tombstoned', casc['bird'])
    check(f"cascade: all {casc['raceN']} race results tombstoned", casc['races'] and casc['raceN'] > 0)
    check('cascade: the health event is tombstoned', casc['health'])
    check(f"cascade: all {casc['pairN']} pairs tombstoned", casc['pairs'] and casc['pairN'] > 0)
    check('cascade: MEDIA rows are tombstoned too (A1)', casc['media'])
    check('an egg UNLINK is a put, so its pair is NOT tombstoned', not casc['eggPairsTombstoned'])

    # ── undo removes every tombstone the cascade wrote ──
    undone = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const before = await db.idbGetAll('tombstones');
        return { before: before.length };
    }""")
    undo = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        // re-delete a fresh bird with dependents, then undo it
        const b = await db.saveBird(db.newBird({ name: 'undo-me', sex: 'hen' }));
        await db.Races.save({ id: 'undo-r', birdId: b.id, date: '2026-02-02', raceType: 'club' });
        await db.Health.save({ id: 'undo-h', eventType: 'check', birdId: b.id, date: '2026-02-02', wholeLoft: false });
        const blob = new Blob([new Uint8Array(256)], { type: 'image/png' });
        await db.addMedia(b.id, 'photo', 'body', 'u.png', blob);
        const snap = await db.deleteBird(b.id);
        const afterDelete = (await db.idbGetAll('tombstones')).filter(t =>
            t.recordId === b.id || t.recordId === 'undo-r' || t.recordId === 'undo-h' || t.store === 'media');
        await db.restoreBird(snap);
        const all = await db.idbGetAll('tombstones');
        const left = all.filter(t => t.recordId === b.id || t.recordId === 'undo-r' || t.recordId === 'undo-h');
        return { wrote: afterDelete.length, left: left.length };
    }""")
    check('undo clears every tombstone the delete wrote', undo['left'] == 0, f"{undo['wrote']} written, {undo['left']} left")

    # ── generic remove + media delete write tombstones, restore clears them ──
    gen = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const r = await db.Races.save({ id: 'gen-r', birdId: null, date: '2026-03-03', raceType: 'club' });
        const snap = await db.Races.remove('gen-r');
        const afterRemove = (await db.idbGetAll('tombstones')).some(t => t.id === 'raceResults:gen-r');
        await db.Races.restore(snap);
        const afterRestore = (await db.idbGetAll('tombstones')).some(t => t.id === 'raceResults:gen-r');
        const b = await db.saveBird(db.newBird({ name: 'med', sex: 'cock' }));
        const blob = new Blob([new Uint8Array(128)], { type: 'image/png' });
        const m = await db.addMedia(b.id, 'photo', 'body', 'g.png', blob);
        const msnap = await db.deleteMedia(m.id);
        const medAfter = (await db.idbGetAll('tombstones')).some(t => t.id === 'media:' + m.id);
        await db.restoreMedia(msnap);
        const medRestored = (await db.idbGetAll('tombstones')).some(t => t.id === 'media:' + m.id);
        return { afterRemove, afterRestore, medAfter, medRestored };
    }""")
    check('generic remove writes a tombstone', gen['afterRemove'])
    check('generic restore clears it', not gen['afterRestore'])
    check('deleteMedia writes a tombstone', gen['medAfter'])
    check('restoreMedia clears it', not gen['medRestored'])

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
