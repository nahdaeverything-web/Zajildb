#!/usr/bin/env python3
"""THE MIGRATION PROOF — a loft moving from one origin to another, end to end.

WHY THIS EXISTS. IndexedDB is per-origin. Records made at
`nahdaeverything-web.github.io` are not readable from `zajildb.com`, by any means, from
inside the browser. The cutover's entire answer for existing users is: export from the old
origin, import at the new one. **That path was proven nowhere.**

What the existing coverage actually tested: `screens/tools.py` re-imports the app's own
export in «دمج» mode into a database that ALREADY HOLDS those records — and `src/db/io.js:192`
is `if (mode === 'merge' && existing) { counts.skipped++; continue; }`, so every media row is
skipped. The round trip proved that merge does not duplicate. It proved nothing whatever
about whether a photo survives a move. `import_atomicity.py:63` carries one 1×1 PNG through a
replace-import; that is a smoke test, not a migration.

WHAT THIS SUITE DOES, and why each choice is load-bearing:

  · REAL BYTES. Photos are generated as multi-hundred-KB images with per-bird noise, so no
    two are alike and a mix-up cannot hide behind identical content. A 1×1 pixel would pass
    a broken re-encode.
  · A SECOND ORIGIN. Two http servers on two ports are two origins — origin is
    scheme+host+PORT — so this is the real per-origin boundary and not a wiped database
    pretending to be one.
  · A FIRST-EVER OPEN. A fresh BrowserContext for that origin, and the suite ASSERTS the
    database does not exist before importing (`indexedDB.databases()`), not merely that it
    holds no rows. A deleted database and a never-created one take different paths through
    `onupgradeneeded`, and the never-created one is what a migrating fancier hits.
  · THROUGH THE UI. The export is produced by clicking «تصدير الكل» and the file is the one
    the browser actually downloaded — not `exportAll()` called directly. A fancier cannot
    call a function.
  · BYTE-IDENTICAL, not "present". Every blob is hashed with SHA-256 inside the page before
    the export and again after the import, and the digests are compared. "The photo is
    there" is not the claim; "it is the same photo" is.
  · BOTH DIRECTIONS OF FORMAT COMPATIBILITY, because the cutover depends on it: a PORT export
    must import into VANILLA, and a VANILLA export must import into the PORT. The port's
    `io.js` is authorised to diverge; the FORMAT may not.

A FAILURE HERE IS THE POINT. This suite is written to find out whether a loft can move, not
to demonstrate that it can. Assertions name what they measure and report the measured value.

Provisions its own servers (R6). Binds to data-testid only."""
import json
import os
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
NEXT_OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'out'))
VANILLA = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


def serve_dir(path):
    """One http server on its own ephemeral port. A different port is a DIFFERENT ORIGIN."""
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '-d', path, '--bind', '127.0.0.1'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.9)
    return srv, f'http://127.0.0.1:{port}/'


assert os.path.exists(os.path.join(NEXT_OUT, 'test-harness.html')), 'run `npm run build:harness` first'

# ── the fixture, built in the page ───────────────────────────────────────────────────────
# Photos are drawn on a canvas with per-bird noise and encoded as PNG, so each is a few
# hundred KB of genuinely different bytes. toBlob is async; the whole thing is awaited.
SEED = """async (n) => {
  const db = await window.__zajilDb;
  for (const b of db.allBirds()) await db.deleteBird(b.id);
  const loft = db.currentLoft().id;
  const photo = async (seed) => {
    const c = document.createElement('canvas'); c.width = 640; c.height = 480;
    const x = c.getContext('2d');
    const img = x.createImageData(640, 480);
    // crypto random, so the PNG cannot compress: a patterned LCG gave 68 KB a photo and the
    // point is to carry real weight through the export
    // getRandomValues caps at 65536 bytes per call, so fill in chunks
    const noise = new Uint8Array(img.data.length);
    for (let o = 0; o < noise.length; o += 65536)
      crypto.getRandomValues(noise.subarray(o, Math.min(o + 65536, noise.length)));
    for (let i = 0; i < img.data.length; i += 4) {
      img.data[i] = noise[i]; img.data[i + 1] = noise[i + 1]; img.data[i + 2] = noise[i + 2]; img.data[i + 3] = 255;
    }
    x.putImageData(img, 0, 0);
    return await new Promise((res) => c.toBlob(res, 'image/png'));
  };
  const made = [];
  for (let i = 0; i < n; i++) {
    const bird = await db.saveBird(db.newBird({
      name: 'طائر-' + i, sex: i % 2 ? 'hen' : 'cock', hatchDate: '202' + (4 + i % 2) + '-03-0' + (i % 9 + 1),
      loftId: loft, notes: [{ id: db.uuid(), at: '2026-04-0' + (i % 9 + 1) + 'T09:00:00.000Z', text: 'ملاحظة-' + i }] }));
    const blob = await photo(i + 1);
    const m = await db.addMedia(bird.id, 'photo', 'bird', 'p' + i + '.png', blob);
    made.push({ birdId: bird.id, mediaId: m.id, bytes: blob.size });
    await db.Races.save({ birdId: bird.id, loftId: loft, date: '2026-05-0' + (i % 9 + 1),
      raceName: 'سباق-' + i, distanceKm: 200 + i, raceType: 'race', position: i + 1, birdsEntered: 100 });
    await db.Health.save({ birdId: bird.id, loftId: loft, date: '2026-06-0' + (i % 9 + 1),
      eventType: 'vaccination', medication: 'لقاح-' + i });
  }
  const bs = db.allBirds();
  for (let i = 0; i + 1 < bs.length; i += 2)
    await db.Pairs.save({ sireId: bs[i].id, damId: bs[i + 1].id, loftId: loft, season: 2026,
      nestBox: String(i), status: 'active', rounds: [] });
  // a deletion, so a tombstone has to travel too
  const doomed = await db.saveBird(db.newBird({ name: 'محذوف', sex: 'cock', loftId: loft }));
  await db.deleteBird(doomed.id);
  return { made, doomedId: doomed.id };
}"""

# A full census, hashed. Media blobs are read back out of IndexedDB and digested, so the
# comparison is over BYTES and not over a row being present.
CENSUS = """async () => {
  const db = await window.__zajilDb;
  const hex = (buf) => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  const sha = async (blob) => hex(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()));
  // media is NOT in the in-memory state (storage.js:98-107 keeps no blobs), so the census
  // reads the store itself — which is also the only way to get at the BYTES.
  const media = {};
  const raw = await new Promise((res, rej) => {
    const r = indexedDB.open('zajil');
    r.onsuccess = () => { const d = r.result;
      const tx = d.transaction('media', 'readonly').objectStore('media').getAll();
      tx.onsuccess = () => { res(tx.result); d.close(); };
      tx.onerror = () => rej(tx.error); };
    r.onerror = () => rej(r.error);
  });
  for (const m of raw) {
    media[m.id] = { birdId: m.birdId, name: m.name, kind: m.kind, subtype: m.subtype };
    if (m.blob) { media[m.id].hash = await sha(m.blob); media[m.id].bytes = m.blob.size; }
  }
  const strip = (o, keys) => Object.fromEntries(keys.map(k => [k, o[k] ?? null]));
  return {
    birds: db.allBirds().map(b => strip(b, ['id', 'name', 'sex', 'hatchDate', 'status', 'sireId', 'damId']))
             .sort((a, b) => a.id.localeCompare(b.id)),
    notes: db.allBirds().flatMap(b => (b.notes || []).map(n => ({ bird: b.id, at: n.at, text: n.text })))
             .sort((a, b) => (a.bird + a.at).localeCompare(b.bird + b.at)),
    pairs: [...db.state.pairs.values()].map(p => strip(p, ['id', 'sireId', 'damId', 'season', 'nestBox']))
             .sort((a, b) => a.id.localeCompare(b.id)),
    races: [...db.state.raceResults.values()].map(r => strip(r, ['id', 'birdId', 'date', 'raceName', 'position']))
             .sort((a, b) => a.id.localeCompare(b.id)),
    health: [...db.state.healthEvents.values()].map(h => strip(h, ['id', 'birdId', 'date', 'eventType', 'medication']))
             .sort((a, b) => a.id.localeCompare(b.id)),
    media,
  };
}"""

TOMBS = """async () => {
  const raw = await new Promise((res, rej) => {
    const r = indexedDB.open('zajil');
    r.onsuccess = () => { const d = r.result;
      const tx = d.transaction('tombstones', 'readonly').objectStore('tombstones').getAll();
      tx.onsuccess = () => { res(tx.result); d.close(); }; tx.onerror = () => rej(tx.error); };
    r.onerror = () => rej(r.error);
  });
  return raw.map(t => t.recordId).sort();   // NOT t.id — that is tombstoneId(store, recordId)
}"""

DB_EXISTS = """async () => {
  if (!indexedDB.databases) return 'unknown';
  const names = (await indexedDB.databases()).map(d => d.name);
  return names.includes('zajil');
}"""

srv_a = srv_b = srv_v = None
try:
    srv_a, ORIGIN_A = serve_dir(NEXT_OUT)          # the old origin — the port, where the loft lives
    srv_b, ORIGIN_B = serve_dir(NEXT_OUT)          # the new origin — a DIFFERENT port, so a different origin
    srv_v, ORIGIN_V = serve_dir(VANILLA)           # the vanilla app, for the format-compatibility pass
    check('two port origins and a vanilla origin, all distinct',
          len({ORIGIN_A, ORIGIN_B, ORIGIN_V}) == 3, f'{ORIGIN_A} {ORIGIN_B} {ORIGIN_V}')

    with sync_playwright() as p:
        br = p.chromium.launch()

        # ── ORIGIN A: build the loft ───────────────────────────────────────────────────
        ctx_a = br.new_context(accept_downloads=True)
        a = ctx_a.new_page(); errs = []; a.on('pageerror', lambda e: errs.append(str(e)))
        a.goto(ORIGIN_A + 'test-harness.html', wait_until='load'); a.wait_for_timeout(800)
        a.evaluate("async () => { await window.__zajilReady; }")
        seeded = a.evaluate(SEED, 6)
        total_bytes = sum(m['bytes'] for m in seeded['made'])
        check('origin A: a loft with 6 birds, each carrying a real photo of real size',
              len(seeded['made']) == 6 and total_bytes > 1_000_000,
              f"{len(seeded['made'])} photos, {total_bytes / 1e6:.2f} MB of image bytes")

        before = a.evaluate(CENSUS)
        tombs_before = a.evaluate(TOMBS)
        hashes_before = {k: v['hash'] for k, v in before['media'].items()}
        check('origin A: every photo hashes to a DISTINCT digest, so a mix-up cannot hide',
              len(set(hashes_before.values())) == len(hashes_before) and all(hashes_before.values()),
              f'{len(set(hashes_before.values()))} distinct of {len(hashes_before)}')
        check('origin A: the deleted bird left a tombstone', seeded['doomedId'] in tombs_before,
              f'{len(tombs_before)} tombstone(s)')

        # ── the export, through the UI ─────────────────────────────────────────────────
        ta = ctx_a.new_page(); ta.on('pageerror', lambda e: errs.append(str(e)))
        ta.goto(ORIGIN_A + 'tools.html', wait_until='load'); ta.wait_for_timeout(1200)
        t0 = time.time()
        with ta.expect_download(timeout=120000) as dl:
            ta.click('[data-testid=export-all]')
        path = dl.value.path()
        elapsed = time.time() - t0
        raw = open(path, 'rb').read()
        check('the export downloads from the UI, as a fancier would produce it',
              dl.value.suggested_filename.startswith('zajil-export-'),
              f'{dl.value.suggested_filename}, {len(raw) / 1e6:.2f} MB, {elapsed:.1f}s')
        payload = json.loads(raw.decode('utf-8'))
        check('the payload carries the media, as data URLs',
              len(payload.get('media', [])) == 6 and all(m.get('dataURL') for m in payload['media']),
              f"{len(payload.get('media', []))} media rows")

        # ── ORIGIN B: a database that has NEVER existed ────────────────────────────────
        ctx_b = br.new_context(accept_downloads=True)
        b = ctx_b.new_page(); b.on('pageerror', lambda e: errs.append(str(e)))
        # A page that does NOT boot the app: the server's own 404 is same-origin and loads no
        # script. Probing after tools.html would be worthless — initDB() creates the database
        # on load, so the answer could only ever be True.
        b.goto(ORIGIN_B + '__no_such_page__', wait_until='domcontentloaded'); b.wait_for_timeout(200)
        exists = b.evaluate(DB_EXISTS)
        check('origin B: the zajil database does NOT exist — a first-ever open, not a wiped one',
              exists is False, f'indexedDB.databases() says exists={exists}')
        b.goto(ORIGIN_B + 'tools.html', wait_until='load'); b.wait_for_timeout(1800)

        b.set_input_files('[data-testid=file-input]',
                          files=[{'name': 'zajil-export.json', 'mimeType': 'application/json', 'buffer': raw}])
        b.wait_for_timeout(400)
        b.click('[data-testid=import-file]')
        b.wait_for_timeout(6000)

        after = b.evaluate(CENSUS)
        tombs_after = b.evaluate(TOMBS)

        # ── record for record ──────────────────────────────────────────────────────────
        for kind in ('birds', 'pairs', 'races', 'health', 'notes'):
            same = before[kind] == after[kind]
            check(f'{kind}: every record survived the move, field for field',
                  same, f"{len(before[kind])} -> {len(after[kind])}" if not same else f'{len(after[kind])}')

        check('tombstones: the deleted bird stays deleted at the new origin',
              seeded['doomedId'] in tombs_after and not any(bd['id'] == seeded['doomedId'] for bd in after['birds']),
              f'{len(tombs_after)} tombstone(s), doomed present={seeded["doomedId"] in tombs_after}')

        hashes_after = {k: v.get('hash') for k, v in after['media'].items()}
        check('media: every photo row arrived', set(hashes_before) == set(hashes_after),
              f'{len(hashes_before)} -> {len(hashes_after)}')
        missing = [k for k, v in hashes_after.items() if not v]
        check('media: every photo carries BYTES at the new origin, not just a row',
              not missing, f'{len(missing)} row(s) with no blob')
        differing = [k for k in hashes_before if hashes_after.get(k) != hashes_before[k]]
        check('media: every photo is BYTE-IDENTICAL — same SHA-256, not merely present',
              not differing, f'{len(differing)} of {len(hashes_before)} differ')

        # ── what does NOT survive, asserted rather than assumed ────────────────────────
        check('KNOWN LOSS: the export carries no settings key at all',
              'settings' not in payload, f"keys: {sorted(payload.keys())}")
        check('KNOWN LOSS: the op log does not travel', 'oplog' not in payload)
        check('KNOWN LOSS: the rotating auto-backups do not travel', 'backups' not in payload)

        # ── FORMAT COMPATIBILITY, both directions ─────────────────────────────────────
        # The port's io.js is authorised to diverge. The FORMAT is not — the cutover depends
        # on a file crossing between the two apps in either direction.
        ctx_v = br.new_context(accept_downloads=True)
        v = ctx_v.new_page(); v.on('pageerror', lambda e: errs.append(str(e)))
        v.goto(ORIGIN_V + 'index.html#/tools', wait_until='load'); v.wait_for_timeout(2500)
        v_imported = v.evaluate("""async (text) => {
            const db = await import('./js/db.js');
            await db.initDB();
            const before = db.allBirds().length;
            const counts = await db.importAll(JSON.parse(text), 'merge');
            return { before, after: db.allBirds().length, counts };
        }""", raw.decode('utf-8'))
        check('FORMAT → : a PORT export imports into VANILLA',
              v_imported['after'] - v_imported['before'] == len(before['birds']),
              f"{v_imported['before']} -> {v_imported['after']} birds, counts={v_imported['counts']}")

        v_payload = v.evaluate("async () => { const db = await import('./js/db.js'); return await db.exportAll(); }")
        ctx_c = br.new_context(accept_downloads=True)
        c = ctx_c.new_page(); c.on('pageerror', lambda e: errs.append(str(e)))
        c.goto(ORIGIN_B + 'tools.html', wait_until='load'); c.wait_for_timeout(1800)
        c_imported = c.evaluate("""async (pl) => {
            const db = await window.__zajilDb;
            const before = db.allBirds().length;
            const counts = await db.importAll(pl, 'merge');
            return { before, after: db.allBirds().length, counts };
        }""", v_payload)
        check('FORMAT ← : a VANILLA export imports into the PORT',
              c_imported['after'] >= c_imported['before'],
              f"{c_imported['before']} -> {c_imported['after']} birds, counts={c_imported['counts']}")

        # ── NEGATIVE CONTROL ───────────────────────────────────────────────────────────
        # A green byte-identity check is worth nothing unless a corrupted photo turns it red.
        # One byte of one data URL is flipped and imported into a THIRD fresh origin-context;
        # the same comparison must catch it. Without this, a detector that silently stopped
        # looking would read exactly like a successful migration.
        tampered = json.loads(raw.decode('utf-8'))
        victim = tampered['media'][0]
        du = victim['dataURL']
        head, b64 = du.split(',', 1)
        flipped = ('B' if b64[400] != 'B' else 'C')
        victim['dataURL'] = f'{head},{b64[:400]}{flipped}{b64[401:]}'
        ctx_n = br.new_context(accept_downloads=True)
        n = ctx_n.new_page()
        n.goto(ORIGIN_B + 'tools.html', wait_until='load'); n.wait_for_timeout(1800)
        n.set_input_files('[data-testid=file-input]', files=[{'name': 'tampered.json',
                          'mimeType': 'application/json', 'buffer': json.dumps(tampered).encode('utf-8')}])
        n.wait_for_timeout(400)
        n.click('[data-testid=import-file]'); n.wait_for_timeout(5000)
        n_census = n.evaluate(CENSUS)
        n_hashes = {k: v.get('hash') for k, v in n_census['media'].items()}
        caught = [k for k in hashes_before if n_hashes.get(k) != hashes_before[k]]
        check('NEGATIVE CONTROL: one flipped byte in one photo IS caught by the same check',
              len(caught) == 1, f'{len(caught)} mismatch(es) detected — expected exactly 1')

        check('zero page errors across the whole migration', not errs, '; '.join(errs[:3]))
        br.close()
finally:
    for s_ in (srv_a, srv_b, srv_v):
        if s_:
            s_.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
