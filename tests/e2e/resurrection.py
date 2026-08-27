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

    # ── THE BUG: create → export → delete → merge-import the old export ──
    r = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'يجب ألا يعود', sex: 'cock' }));
        const payload = await db.exportAll();                 // export WITH the bird
        await new Promise(r => setTimeout(r, 15));            // ensure the tombstone is newer
        await db.deleteBird(b.id);
        const goneBefore = !db.getBird(b.id);
        const counts = await db.importAll(payload, 'merge');  // the old export comes back
        return { goneBefore, stillGone: !db.getBird(b.id), skipped: counts.skipped, id: b.id };
    }""")
    check('the bird was deleted', r['goneBefore'])
    check('a merge-import of an OLD export does NOT resurrect it', r['stillGone'])
    check('and it is counted as skipped', r['skipped'] >= 1, str(r['skipped']))

    # ── a genuinely NEWER incoming record must still win ──
    newer = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'legit-update', sex: 'hen' }));
        await db.deleteBird(b.id);
        // an edit made on another device AFTER the delete
        const future = new Date(Date.now() + 60000).toISOString();
        const payload = { format: 'zajil-export', version: 1, exportedAt: future,
            lofts: [], birds: [{ id: b.id, rings: [], name: 'edited elsewhere', sex: 'hen',
                external: false, status: 'stock', sireId: null, damId: null, notes: [],
                updatedAt: future }],
            pairs: [], raceResults: [], healthEvents: [], media: [], tombstones: [] };
        await db.importAll(payload, 'merge');
        const back = db.getBird(b.id);
        return { restored: !!back, name: back && back.name };
    }""")
    check('a genuinely newer record still wins over the tombstone',
          newer['restored'] and newer['name'] == 'edited elsewhere', str(newer))

    # ── A3: the export carries tombstones but NEVER the op log ──
    exp = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const payload = await db.exportAll();
        return { keys: Object.keys(payload).sort(),
                 hasTombstones: Array.isArray(payload.tombstones),
                 tombstoneCount: (payload.tombstones || []).length,
                 oplogKeyPresent: 'oplog' in payload };
    }""")
    check('export includes a tombstones array', exp['hasTombstones'] and exp['tombstoneCount'] > 0, str(exp['tombstoneCount']))
    check('export has NO oplog key at all (not even empty)', not exp['oplogKeyPresent'], str(exp['keys']))

    # ── payload tombstones are imported, so protection survives a round trip ──
    rt = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'round-trip', sex: 'cock' }));
        const withBird = await db.exportAll();
        await new Promise(r => setTimeout(r, 15));
        await db.deleteBird(b.id);
        const withTombstone = await db.exportAll();          // carries the tombstone
        // simulate a second device: wipe local tombstones, then import the tombstone-bearing export
        for (const t of await db.idbGetAll('tombstones')) await db.idbDelete('tombstones', t.id);
        await db.importAll(withTombstone, 'merge');
        const gotTombstone = (await db.idbGetAll('tombstones')).some(t => t.recordId === b.id);
        // now the OLD export arrives — the imported tombstone must still block it
        await db.importAll(withBird, 'merge');
        return { gotTombstone, resurrected: !!db.getBird(b.id) };
    }""")
    check('payload tombstones are imported (union by id)', rt['gotTombstone'])
    check('an imported tombstone blocks resurrection on another device', not rt['resurrected'])

    # ── replace mode ignores tombstones: it is a restore of a point in time ──
    rep = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'replace-me', sex: 'hen' }));
        const payload = await db.exportAll();
        await new Promise(r => setTimeout(r, 15));
        await db.deleteBird(b.id);
        await db.importAll(payload, 'replace');
        return { back: !!db.getBird(b.id) };
    }""")
    check('replace mode restores the point in time, tombstone or not', rep['back'])

    # ── ADDITION 2: replace clears ONLY data stores ──
    scope = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        await db.saveBird(db.newBird({ name: 'scope-probe', sex: 'cock' }));
        const before = {
            oplog: (await db.listOps()).length,
            tombstones: (await db.idbGetAll('tombstones')).length,
            settings: (await db.idbGetAll('settings')).length,
            backups: (await db.idbGetAll('backups')).length,
            deviceId: db.state.settings.deviceId,
        };
        const payload = { format: 'zajil-export', version: 1, exportedAt: new Date().toISOString(),
            lofts: [{ id: 'rep-loft', name: 'x', statuses: ['stock'], updatedAt: new Date().toISOString() }],
            birds: [], pairs: [], raceResults: [], healthEvents: [], media: [], tombstones: [] };
        await db.importAll(payload, 'replace');
        const after = {
            oplog: (await db.listOps()).length,
            tombstones: (await db.idbGetAll('tombstones')).length,
            settings: (await db.idbGetAll('settings')).length,
            backups: (await db.idbGetAll('backups')).length,
            deviceId: db.state.settings.deviceId,
            birds: db.state.birds.size,
        };
        return { before, after };
    }""")
    b_, a_ = scope['before'], scope['after']
    check('replace does NOT clear the op log (device history)', a_['oplog'] >= b_['oplog'], f"{b_['oplog']} -> {a_['oplog']}")
    check('replace does NOT clear tombstones', a_['tombstones'] >= b_['tombstones'], f"{b_['tombstones']} -> {a_['tombstones']}")
    check('replace does NOT clear settings', a_['settings'] >= b_['settings'], f"{b_['settings']} -> {a_['settings']}")
    check('replace does NOT clear backups', a_['backups'] >= b_['backups'], f"{b_['backups']} -> {a_['backups']}")
    check('device identity survives a replace', a_['deviceId'] == b_['deviceId'])
    check('replace DID clear the data stores', a_['birds'] == 0, str(a_['birds']))

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
