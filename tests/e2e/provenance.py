import os, json
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

    # ══ WATCH ITEM 1: a pre-v1.8 bird has NO provenance, and that stays legal ══
    legacy = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        // a v1.7-era record: no provenance, no deviceId
        const old = { id: 'legacy-bird', rings: [{ raw: 'JO-2019-00001', type: 'national' }],
            name: 'قديم', sex: 'cock', hatchDate: '2019-04-01', colour: '', strain: '',
            eyeSign: '', status: 'stock', sireId: null, damId: null, external: false,
            breeder: '', owner: '', acquiredFrom: '', acquiredDate: '', notes: [],
            createdAt: '2019-04-01T00:00:00.000Z', updatedAt: '2019-04-01T00:00:00.000Z',
            loftId: db.state.currentLoftId };
        await db.idbPut('birds', old);
        db.state.birds.set(old.id, old);
        const out = {};
        out.loadedNoProvenance = !('provenance' in db.getBird('legacy-bird'));

        // EDIT and SAVE it — stamp() must not invent provenance
        const edited = { ...db.getBird('legacy-bird'), name: 'قديم معدَّل' };
        await db.saveBird(edited);
        const after = db.getBird('legacy-bird');
        out.stillNoProvenance = !('provenance' in after);
        out.gotDeviceId = !!after.deviceId;
        out.nameChanged = after.name === 'قديم معدَّل';

        // EXPORT and RE-IMPORT it
        const payload = await db.exportAll();
        const inExport = payload.birds.find(b => b.id === 'legacy-bird');
        out.exportNoProvenance = !('provenance' in inExport);
        await db.importAll(payload, 'merge');
        const reimported = db.getBird('legacy-bird');
        out.reimportNoProvenance = reimported && !('provenance' in reimported);
        out.survived = !!reimported;
        return out;
    }""")
    check('a pre-v1.8 bird loads with no provenance field', legacy['loadedNoProvenance'])
    check('editing and saving it does NOT invent provenance', legacy['stillNoProvenance'])
    check('…but it does get a deviceId (last writer)', legacy['gotDeviceId'])
    check('the edit actually applied', legacy['nameChanged'])
    check('it exports without a provenance field', legacy['exportNoProvenance'])
    check('it re-imports intact, still without provenance', legacy['survived'] and legacy['reimportNoProvenance'])

    # ══ WATCH ITEM 2: provenance round-trips byte-identical, merge AND replace ══
    rt = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const history = [
            { event: 'created',     at: '2020-01-01T00:00:00.000Z', deviceId: 'device-A' },
            { event: 'transferred', at: '2021-06-01T00:00:00.000Z', deviceId: 'device-B' },
            { event: 'promoted',    at: '2022-09-15T00:00:00.000Z', deviceId: 'device-C' },
        ];
        const b = await db.saveBird(db.newBird({ id: 'prov-bird', name: 'له تاريخ', sex: 'hen',
            provenance: JSON.parse(JSON.stringify(history)) }));
        const original = JSON.stringify(db.getBird('prov-bird').provenance);

        const payload = await db.exportAll();
        const inExport = JSON.stringify(payload.birds.find(x => x.id === 'prov-bird').provenance);

        await db.importAll(payload, 'merge');
        const afterMerge = JSON.stringify(db.getBird('prov-bird').provenance);

        await db.importAll(payload, 'replace');
        const afterReplace = JSON.stringify(db.getBird('prov-bird').provenance);

        return { expected: JSON.stringify(history), original, inExport, afterMerge, afterReplace };
    }""")
    check('provenance is stored exactly as supplied', rt['original'] == rt['expected'], rt['original'][:90])
    check('export carries it byte-identical', rt['inExport'] == rt['expected'])
    check('MERGE re-import leaves it byte-identical', rt['afterMerge'] == rt['expected'], rt['afterMerge'][:90])
    check('REPLACE re-import leaves it byte-identical', rt['afterReplace'] == rt['expected'], rt['afterReplace'][:90])
    check('no created event was appended on import', rt['afterMerge'].count('"created"') == 1)
    check('the order was not rearranged',
          rt['afterMerge'].index('device-A') < rt['afterMerge'].index('device-B') < rt['afterMerge'].index('device-C'))

    # ══ a new bird gets a created event naming THIS device ══
    fresh = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'جديد', sex: 'cock' }));
        return { prov: b.provenance, deviceId: b.deviceId, settingsDevice: db.state.settings.deviceId };
    }""")
    check('a new bird has one created event', len(fresh['prov']) == 1 and fresh['prov'][0]['event'] == 'created')
    check('the created event names this device', fresh['prov'][0]['deviceId'] == fresh['settingsDevice'])
    check('deviceId (last writer) is also set', fresh['deviceId'] == fresh['settingsDevice'])

    # ══ WATCH ITEM 3 corollary: deviceId tracks the LAST writer, provenance[0] the creator ══
    moved = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        // a bird created on another device, now edited here
        const b = await db.saveBird(db.newBird({ id: 'moved-bird', name: 'منتقل', sex: 'hen',
            provenance: [{ event: 'created', at: '2020-01-01T00:00:00.000Z', deviceId: 'far-away-device' }] }));
        return { creator: b.provenance[0].deviceId, lastWriter: b.deviceId,
                 thisDevice: db.state.settings.deviceId };
    }""")
    check('provenance[0] keeps the ORIGINAL creating device', moved['creator'] == 'far-away-device')
    check('deviceId records THIS device as last writer', moved['lastWriter'] == moved['thisDevice'])
    check('the two are genuinely different', moved['creator'] != moved['lastWriter'])

    # ══ WATCH ITEM 4: the sorted reader ══
    reader = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        for (let i = 0; i < 12; i++) await db.saveBird(db.newBird({ name: 'ord-' + i, sex: 'cock' }));
        const sorted = await db.listOps();
        // deliberate raw read: proves the trap the sorted reader exists to hide
        const raw = await db.idbGetAll('oplog');
        const seqs = sorted.map(o => o.seq);
        const rawSeqs = raw.map(o => o.seq);
        const isSorted = a => a.every((v, i) => i === 0 || a[i-1] <= v);
        const max = Math.max(...seqs);
        const since = await db.getOpsSinceSeq(max - 5);
        return { sortedOk: isSorted(seqs), rawWasSorted: isSorted(rawSeqs),
                 sinceCount: since.length, sinceSorted: isSorted(since.map(o => o.seq)),
                 sinceAllGreater: since.every(o => o.seq > max - 5) };
    }""")
    check('listOps() returns ops in seq order', reader['sortedOk'])
    check('getOpsSinceSeq filters and sorts', reader['sinceCount'] == 5 and reader['sinceSorted'] and reader['sinceAllGreater'], str(reader))
    if not reader['rawWasSorted']:
        print('     (raw idbGetAll was indeed unsorted — the trap the reader exists to hide)')

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
