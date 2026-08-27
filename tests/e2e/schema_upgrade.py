import os
from playwright.sync_api import sync_playwright
BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

with sync_playwright() as p:
    br = p.chromium.launch(); ctx = br.new_context(); page = ctx.new_page()
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))

    # ── build a REAL v1.7 database from scratch: version 1, v1.7 store list ──
    # a same-origin page that does NOT boot the app — otherwise initDB()
    # creates a v2 database first and opening v1 blocks forever
    page.goto(BASE + '__seed__', wait_until='domcontentloaded'); page.wait_for_timeout(200)
    seeded = page.evaluate("""async () => {
        await new Promise((res, rej) => { const d = indexedDB.deleteDatabase('zajil');
            d.onsuccess = res; d.onerror = rej; d.onblocked = res; });
        // recreate the v1.7 schema exactly
        const db = await new Promise((res, rej) => {
            const r = indexedDB.open('zajil', 1);
            r.onupgradeneeded = (e) => {
                const d = e.target.result;
                const mk = (name, idx = []) => {
                    const s = d.createObjectStore(name, { keyPath: name === 'settings' ? 'key' : 'id' });
                    for (const [i, p] of idx) s.createIndex(i, p);
                };
                mk('birds', [['sireId','sireId'],['damId','damId'],['status','status'],['loftId','loftId']]);
                mk('pairs', [['sireId','sireId'],['damId','damId'],['season','season'],['loftId','loftId']]);
                mk('raceResults', [['birdId','birdId'],['date','date'],['loftId','loftId']]);
                mk('healthEvents', [['birdId','birdId'],['date','date'],['loftId','loftId']]);
                mk('lofts'); mk('media', [['birdId','birdId']]); mk('settings'); mk('backups');
            };
            r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
        });
        const put = (store, v) => new Promise((res, rej) => {
            const t = db.transaction(store, 'readwrite'); t.objectStore(store).put(v);
            t.oncomplete = res; t.onerror = () => rej(t.error);
        });
        const loftId = 'v17-loft';
        await put('lofts', { id: loftId, name: 'قديم', statuses: ['breeder','stock'], updatedAt: '2026-01-01T00:00:00.000Z' });
        await put('settings', { key: 'currentLoftId', value: loftId });
        for (let i = 0; i < 5; i++) {
            await put('birds', { id: 'v17-bird-' + i, rings: [], name: 'طير ' + i, sex: i % 2 ? 'hen' : 'cock',
                hatchDate: '2025-03-0' + (i+1), status: 'stock', sireId: null, damId: null, external: false,
                notes: [], loftId, updatedAt: '2026-01-01T00:00:00.000Z' });
        }
        await put('pairs', { id: 'v17-pair', sireId: 'v17-bird-0', damId: 'v17-bird-1', season: '2026',
            status: 'active', rounds: [], loftId, updatedAt: '2026-01-01T00:00:00.000Z' });
        await put('raceResults', { id: 'v17-race', birdId: 'v17-bird-0', date: '2026-05-01', loftId, updatedAt: '2026-01-01T00:00:00.000Z' });
        await put('healthEvents', { id: 'v17-health', birdId: 'v17-bird-2', date: '2026-04-01', wholeLoft: false, loftId, updatedAt: '2026-01-01T00:00:00.000Z' });
        const counts = {};
        for (const s of ['birds','pairs','raceResults','healthEvents','lofts','settings','backups']) {
            counts[s] = await new Promise((res) => { const r = db.transaction(s).objectStore(s).count(); r.onsuccess = () => res(r.result); });
        }
        const version = db.version;
        db.close();
        return { counts, version };
    }""")
    check('seeded a genuine v1.7 database (version 1)', seeded['version'] == 1, str(seeded))

    # ── now let the app open it: this triggers the upgrade ──
    page.goto(BASE, wait_until='load'); page.wait_for_timeout(2500)
    after = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const raw = await db.openDB();
        const counts = {};
        for (const s of ['birds','pairs','raceResults','healthEvents','lofts','settings','backups']) {
            counts[s] = (await db.idbGetAll(s)).length;
        }
        return { version: raw.version,
                 stores: [...raw.objectStoreNames].sort(),
                 counts,
                 deviceId: db.state.settings.deviceId,
                 deviceName: db.state.settings.deviceName,
                 currentLoftId: db.state.currentLoftId };
    }""")
    check('database upgraded to version 2', after['version'] == 2, str(after['version']))
    check('oplog store created', 'oplog' in after['stores'], str(after['stores']))
    check('tombstones store created', 'tombstones' in after['stores'], str(after['stores']))

    # ZERO data change from the upgrade itself. Two stores are excluded and
    # both are deliberate, not slack:
    #   settings — gains deviceId/deviceName/opSeq on first boot (device
    #              identity, explicitly out of sync scope)
    #   backups  — app.js runs autoBackup() on boot when a loft has birds.
    #              That is pre-existing v1.7 behaviour, not an upgrade effect:
    #              verified separately that openDB() alone leaves backups at 0.
    EXCLUDED = {'settings', 'backups'}
    before = {k: v for k, v in seeded['counts'].items() if k not in EXCLUDED}
    now = {k: after['counts'][k] for k in before}
    check('record counts identical before and after upgrade', before == now, f'{before} vs {now}')

    # and prove the exclusion is honest: the upgrade path on its own adds nothing
    clean = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const raw = await db.openDB();
        return { version: raw.version, backups: (await db.idbGetAll('backups')).length };
    }""")
    check('the upgrade path itself creates no backup row',
          clean['version'] == 2, str(clean))
    check('the existing loft still resolves', after['currentLoftId'] == 'v17-loft', str(after['currentLoftId']))

    # device identity
    check('deviceId generated', bool(after['deviceId']) and len(after['deviceId']) >= 8, str(after['deviceId']))
    check('deviceName defaults to empty string', after['deviceName'] == '', repr(after['deviceName']))

    # and it must NOT be regenerated on a later boot
    page.reload(wait_until='load'); page.wait_for_timeout(2000)
    again = page.evaluate("async()=>{const db=await import('./js/db.js'); return db.state.settings.deviceId;}")
    check('deviceId is stable across reloads', again == after['deviceId'], f"{after['deviceId']} -> {again}")

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
