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

    # ── THE INVARIANT THIS PASS EXISTS TO PROTECT ──
    # N sequential writes must produce seq 1..N: no duplicates, no gaps.
    seqs = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const before = (await db.listOps()).length;
        for (let i = 0; i < 25; i++) await db.saveBird(db.newBird({ name: 'seq-' + i, sex: 'cock' }));
        const ops = (await db.listOps()).sort((a, b) => a.seq - b.seq);
        return { seqs: ops.map(o => o.seq), before };
    }""")
    s = seqs['seqs']
    check('seq values are strictly 1..N with no gaps', s == list(range(1, len(s) + 1)), f'{s[:8]}…{s[-4:] if len(s)>8 else ""}')
    check('no duplicate seq values', len(set(s)) == len(s), f'{len(s)} ops, {len(set(s))} distinct')

    # ── the real hazard: writes started in the SAME TICK ──
    conc = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const before = (await db.listOps()).map(o => o.seq);
        // fire 20 writes without awaiting between them
        await Promise.all(Array.from({ length: 20 }, (_, i) =>
            db.saveBird(db.newBird({ name: 'conc-' + i, sex: 'hen' }))));
        const all = (await db.listOps()).map(o => o.seq);
        const added = all.filter(x => !before.includes(x));
        return { total: all.length, distinct: new Set(all).size,
                 addedCount: all.length - before.length, addedDistinct: new Set(added).size };
    }""")
    check('concurrent writes never share a seq', conc['distinct'] == conc['total'],
          f"{conc['total']} ops, {conc['distinct']} distinct")
    check('every concurrent write got its own op', conc['addedCount'] == 20, str(conc['addedCount']))

    # ── and the counter survives a reload without re-issuing numbers ──
    page.reload(wait_until='load'); page.wait_for_timeout(2000)
    after = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const maxBefore = Math.max(...(await db.listOps()).map(o => o.seq));
        await db.saveBird(db.newBird({ name: 'after-reload', sex: 'cock' }));
        const ops = await db.listOps();
        const all = ops.map(o => o.seq);
        return { maxBefore, newMax: Math.max(...all), distinct: new Set(all).size, total: all.length };
    }""")
    check('seq continues after a reload, never repeats',
          after['newMax'] == after['maxBefore'] + 1 and after['distinct'] == after['total'],
          str(after))

    # ── one op per record touched, with the right shape ──
    shape = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'shape', sex: 'cock' }));
        const ops = await db.listOps();
        const op = ops.find(o => o.recordId === b.id && o.op === 'put');
        return { op, hasDevice: !!op.deviceId };
    }""")
    op = shape['op']
    for field in ['opId', 'seq', 'deviceId', 'actorId', 'at', 'origin', 'store', 'op', 'recordId', 'changed', 'record']:
        check(f'op carries {field}', field in op, str(sorted(op.keys())))
    # v1.9 Phase 2 wired actorId to the signed-in user. On a device with no
    # session it is still null, and that is not a placeholder any more — it is
    # the honest record of an op made by an unidentified actor. The signed-in
    # half of this rule is asserted in tests/e2e/auth.py.
    check('actorId is null when no one is signed in', op['actorId'] is None)
    check("origin is 'user' for a normal save", op['origin'] == 'user')
    check('a new record reports every field as changed', 'name' in op['changed'] and 'sex' in op['changed'])

    # ── an edit reports ONLY what changed ──
    edited = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'before', sex: 'cock', colour: 'blue' }));
        await db.saveBird({ ...db.getBird(b.id), name: 'after' });
        const ops = (await db.listOps()).filter(o => o.recordId === b.id).sort((a, c) => a.seq - c.seq);
        return ops[ops.length - 1].changed;
    }""")
    check('an edit reports only the changed fields', sorted(x for x in edited if x != 'updatedAt') == ['name'], str(edited))

    # ── setSetting is out of scope: no op ──
    st = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const before = (await db.listOps()).length;
        await db.setSetting('coiDepth', 9);
        return { before, after: (await db.listOps()).length };
    }""")
    check('setSetting writes NO op (out of sync scope)', st['before'] == st['after'], str(st))

    # ── origin coverage: all three paths, not just 'user' ──
    origins = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const out = {};
        // restore
        const b = await db.saveBird(db.newBird({ name: 'origin-restore', sex: 'cock' }));
        const snap = await db.deleteBird(b.id);
        const maxSeq = () => db.listOps().then(o => Math.max(0, ...o.map(x => x.seq)));
        const since = async (m) => (await db.listOps()).filter(o => o.seq > m);
        const m1 = await maxSeq();
        await db.restoreBird(snap);
        out.restore = (await since(m1)).map(o => o.origin);
        // generic restore too
        const r = await db.Races.save({ id: 'origin-r', birdId: null, date: '2026-06-06', raceType: 'club' });
        const rsnap = await db.Races.remove('origin-r');
        const m2 = await maxSeq();
        await db.Races.restore(rsnap);
        out.genericRestore = (await since(m2)).map(o => o.origin);
        // import
        const m3 = await maxSeq();
        await db.importAll({ format: 'zajil-export', version: 1, exportedAt: new Date().toISOString(),
            lofts: [], birds: [{ id: 'origin-import-bird', rings: [], name: 'imported', sex: 'hen',
                external: false, status: 'stock', sireId: null, damId: null, notes: [],
                updatedAt: new Date().toISOString() }],
            pairs: [], raceResults: [], healthEvents: [], media: [], tombstones: [] }, 'merge');
        out.import = (await since(m3)).map(o => o.origin);
        return out;
    }""")
    check("restoreBird ops carry origin 'restore'",
          len(origins['restore']) > 0 and set(origins['restore']) == {'restore'}, str(origins['restore']))
    check("generic restore ops carry origin 'restore'",
          set(origins['genericRestore']) == {'restore'}, str(origins['genericRestore']))
    check("importAll ops carry origin 'import'",
          len(origins['import']) > 0 and set(origins['import']) == {'import'}, str(origins['import']))

    # ── media: metadata logged, blob never ──
    med = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = await db.saveBird(db.newBird({ name: 'has-photo', sex: 'hen' }));
        const blob = new Blob([new Uint8Array(4096)], { type: 'image/png' });
        const m = await db.addMedia(b.id, 'photo', 'body', 'p.png', blob);
        const op = (await db.listOps()).find(o => o.recordId === m.id);
        return { hasBlob: op.record && 'blob' in op.record, name: op.record.name, store: op.store };
    }""")
    check('a media op keeps metadata', med['name'] == 'p.png' and med['store'] == 'media', str(med))
    check('a media op NEVER carries the blob', not med['hasBlob'])

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
