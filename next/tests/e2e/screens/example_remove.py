"""REMOVING THE EXAMPLE DATA, and RF-14 (RULED 2026-10-14).

A fancier loads «تحميل سرب تعليمي», then wants his own birds instead. The removal row in الأدوات → البيانات appears only
while a dataset loft is on the device, confirms with the real counts, goes through deleteBird()/remove()/Lofts.remove()
(so it tombstones and syncs), keeps example ancestors of his own birds as pedigree references, re-files his own records,
and — RF-14 — never leaves currentLoftId pointing at nothing. Harness build, stub project, the net armed.

    python3 tests/e2e/screens/example_remove.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12: a page error is recorded with its stack, address, device and step
import hashlib
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET (RULED 2026-10-08): armed beneath the stub, asserted at the end
from _typography import SCAN                  # noqa: E402
NET = Net()
PAGES = []                                    # every device page; the final check reads THEIR error lists (TF-9)

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

STUB = 'https://stub.example.test'
IRBID_KEY, IRBID_UUID = 'loft-irbid-demo', '8f268d1b-3dbe-57be-8d77-ede52297a2cd'
OLD = json.load(open(os.path.join(HERE, '..', 'fixtures', 'example-loft-large.PRE-v1.9.1.json'), encoding='utf-8'))

# ── the stub project: owner rows, one global server_seq, deletes as deleted=true (docs/SYNC-DESIGN.md §1) ──
class Server:
    def __init__(self): self.rows = {}; self.seq = 0; self.posts = []
    def upsert(self, o, r): self.seq += 1; row = dict(r, server_seq=self.seq, owner=o); self.rows[(o, r['store'], r['record_id'])] = row; return row
    def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
    def summary(self, o):
        out = {}
        for (w, s, _), r in self.rows.items():
            if w == o: k = s + ('†' if r['deleted'] else ''); out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))
    def live_names(self, o, store): return sorted((r['data'].get('name') or '') for (w, s, _), r in self.rows.items() if w == o and s == store and not r['deleted'])
srv = Server()
def handler(route, request):
    if '/auth/v1/token' in request.url:
        body = json.loads(request.post_data or '{}'); who = (body.get('email') or 'a@').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}})); return
    who = 'user-' + (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]'); srv.posts.append((who, len(rows), sum(1 for r in rows if r['deleted'])))
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in rows])); return
    c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); rows = srv.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
STATE = """async (db) => { const st = {}; for (const r of await db.idbGetAll('settings')) st[r.key] = r.value;
  const lofts = Object.fromEntries([...db.state.lofts.values()].map(l => [l.id, l.name || '(unnamed)']));
  const by = {}; for (const b of db.state.birds.values()) by[b.loftId] = (by[b.loftId] || 0) + 1;
  return { lofts, birdsByLoft: by, birds: db.state.birds.size, pairs: db.state.pairs.size, races: db.state.raceResults.size, health: db.state.healthEvents.size,
    current: (db.currentLoft() || {}).id || null, currentName: db.currentLoft() ? (db.currentLoft().name || '(unnamed)') : null, storedCurrent: st.currentLoftId || null,
    tombstones: (await db.idbGetAll('tombstones')).length, external: [...db.state.birds.values()].filter(b => b.external).map(b => b.name).sort() }; }"""

def device(b, H, email='x@zajil.test', downloads=False):
    """A configured device, signed in through the stub (the sign-in gate stands on every route otherwise)."""
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}, accept_downloads=downloads))
    ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email); return ctx, pg
def open_row(pg, row):
    r = pg.locator(f'[data-row={row}]')
    if r.get_attribute('open') is None: r.locator('summary').click(); pg.wait_for_timeout(300)
def tools(pg, ROOT):
    pg.goto(ROOT + 'tools/', wait_until='load'); pg.wait_for_selector('[data-testid=tools-list]', timeout=15000); pg.wait_for_timeout(800)
def load_large(pg, ROOT):
    tools(pg, ROOT); open_row(pg, 'teaching'); pg.click('[data-testid=load-large]'); pg.wait_for_timeout(4000)
def row_present(pg, ROOT):
    tools(pg, ROOT); return pg.locator('[data-row=example-remove]').count()
def ui_remove(pg, ROOT, confirm=True):
    """Open the row, press, read the dialog, confirm (or cancel). Returns the dialog's text, the toast, and whether the row is gone."""
    tools(pg, ROOT); open_row(pg, 'example-remove'); pg.click('[data-testid=example-remove]'); pg.wait_for_selector('[data-testid=dialog]', timeout=8000)
    text = pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')
    pg.click('[data-testid=dialog-confirm]' if confirm else '[data-testid=dialog-cancel]')
    if confirm:
        # bounded and NON-RAISING (TF-9, 2026-10-30): a removal that never completes must fail a named check with the toast
        # as evidence — the R1 mutant died here on the 120 s timeout, red for the wrong reason, never reaching an assertion
        try: pg.wait_for_function("() => !document.querySelector('[data-row=example-remove]') || [...document.querySelectorAll('[data-testid=toast]')].some(t => (t.textContent || '').includes('لم تُزل'))", timeout=120000)
        except PWTimeout: pass
        pg.wait_for_timeout(1500)
    else: pg.wait_for_timeout(500)
    toast = pg.locator('[data-testid=toast]').last.inner_text().replace('\n', ' ') if pg.locator('[data-testid=toast]').count() else ''
    return text, toast, pg.locator('[data-row=example-remove]').count() == 0
def sync_ui(pg, ROOT):
    pg.goto(ROOT + 'tools/sync/', wait_until='load'); pg.wait_for_selector('[data-testid=card-sync]', timeout=15000); pg.click('[data-testid=sync-now]'); pg.wait_for_timeout(5000)
    return pg.locator('[data-testid=sync-status]').get_attribute('data-state')
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s)

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ the derivation: the four ids, computed in the browser, equal the shipped ids and the keys ═══
        c0, pg = device(b, H)
        ids = run(pg, "async (db) => db.exampleLoftIds()")
        shipped = json.load(open(os.path.join(HERE, '..', '..', '..', 'public', 'example-loft-large.json'), encoding='utf-8'))['lofts'][0]['id']
        small = json.load(open(os.path.join(HERE, '..', '..', '..', 'public', 'sample-data.json'), encoding='utf-8'))['lofts'][0]['id']
        check('[derived] the four example loft ids are the two keys and their uuid5 forms — and the uuid5 forms are the ids the datasets ship',
              ids == ['loft-irbid-demo', 'loft-zarqa', shipped, small], ids)
        check('[derived] uuid5 in the browser equals Python uuid5 over the same namespace and key',
              ids[2] == IRBID_UUID and ids[3] == 'b5ab67a5-483f-5a6c-997c-a5de423cb53f', ids[2:])
        check('[absent] a device with no example data shows no removal row', row_present(pg, ROOT) == 0)
        c0.close()

        # ═══ THE PHONE + PC CASE (CONSTRUCTED from a description, not from any export — TF-10): a real loft on the phone; the PC holds BOTH teaching generations and removes them in one action ═══
        cph, ph = device(b, H, 'a@zajil.test')
        run(ph, """async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت أبو خالد', breederName: 'خالد العمري' });
            for (const n of ['حقيقي-1', 'حقيقي-2']) await db.saveBird(db.newBird({ name: n, sex: 'cock', loftId: db.currentLoft().id })); await db.syncNow(); }""")
        cpc, pc = device(b, H, 'a@zajil.test'); run(pc, "async (db) => { await db.syncNow(); }")
        load_large(pc, ROOT); pc.goto(H, wait_until='load'); pc.wait_for_function('window.__zajilReady')
        run(pc, "async (db, old) => db.importAll(old, 'merge')", OLD); run(pc, "async (db) => { await db.syncNow(); }")
        s0 = run(pc, STATE)
        check('[both] the PC holds both generations beside the real loft', set(s0['lofts'].values()) == {'لوفت أبو خالد', 'لوفت إربد التعليمي'} and len(s0['lofts']) == 3 and s0['birds'] == 78, s0['lofts'])
        check('[both] …and the server holds all of it', srv.summary('user-A') == {'birds': 78, 'healthEvents': 14, 'lofts': 3, 'pairs': 10, 'raceResults': 34}, srv.summary('user-A'))
        cc, c3 = device(b, H, 'a@zajil.test'); run(c3, "async (db) => { await db.syncNow(); }")   # a third device that pulled the teaching data
        check('[both] the row appears, counting the example birds of both lofts', row_present(pc, ROOT) == 1 and digits(pc.locator('[data-row=example-remove] [data-testid=row-value]').inner_text()).strip() == '76',
              pc.locator('[data-row=example-remove] [data-testid=row-value]').inner_text() if row_present(pc, ROOT) else 'no row')
        text, _, _ = ui_remove(pc, ROOT, confirm=False)
        check('[both] the dialog names the real counts and both lofts, before anything is touched', all(x in digits(text) for x in ['76', '10', '34', '14']) and text.count('لوفت إربد التعليمي') == 2 and 'لا يُمسّ أي طير من طيورك' in text, text[:200])
        s1 = run(pc, STATE); check('[both] cancelling changes nothing', s1 == s0)
        posts = len(srv.posts); text, toast, gone = ui_remove(pc, ROOT, confirm=True); s2 = run(pc, STATE)
        check('[both] ONE action removes both generations: the example records and both loft records are gone, the real loft untouched',
              s2['lofts'] == {k: v for k, v in s0['lofts'].items() if v == 'لوفت أبو خالد'} and s2['birds'] == 2 and s2['pairs'] == s2['races'] == s2['health'] == 0, {k: s2[k] for k in ('lofts', 'birds', 'pairs', 'races', 'health')})
        check('[both] every deletion was tombstoned — 136 tombstones, nothing pushed yet', s2['tombstones'] == 136 and len(srv.posts) == posts, (s2['tombstones'], len(srv.posts) - posts))
        check('[both] the toast reports the counts', all(x in digits(toast) for x in ['76', '10', '34', '14']), toast)
        check('[both] the row is gone', row_present(pc, ROOT) == 0)
        check('[both] «مزامنة الآن» pushes the tombstones', sync_ui(pc, ROOT) == 'synced' and sum(d for _, _, d in srv.posts[posts:]) == 136 and srv.summary('user-A') == {'birds': 2, 'birds†': 76, 'healthEvents†': 14, 'lofts': 1, 'lofts†': 2, 'pairs†': 10, 'raceResults†': 34}, (srv.posts[posts:], srv.summary('user-A')))
        run(c3, "async (db) => { await db.syncNow(); }"); s3 = run(c3, STATE)
        # (that device joined while three lofts stood, so RF-12's adoption refused and it keeps its own pristine loft beside the real one — seen, out of scope)
        check('[both] a second device that had pulled the teaching data loses it on its next sync', s3['birds'] == 2 and 'لوفت إربد التعليمي' not in s3['lofts'].values() and 'لوفت أبو خالد' in s3['lofts'].values() and s3['tombstones'] == 136, {k: s3[k] for k in ('lofts', 'birds', 'tombstones')})
        check('[both] the phone, which never held example data, is unaffected', run(ph, "async (db) => { await db.syncNow(); }") is None and run(ph, STATE)['birds'] == 2)
        check('[both] the net: nothing left for the real project', not NET.escaped)
        cph.close(); cpc.close(); cc.close()

        # ═══ ONE generation only ═══
        c1, d1 = device(b, H, 'b@zajil.test'); run(d1, "async (db) => { await db.syncNow(); }"); load_large(d1, ROOT)
        d1.goto(H, wait_until='load'); d1.wait_for_function('window.__zajilReady'); run(d1, "async (db) => { await db.syncNow(); }")
        s = run(d1, STATE); check('[one] after loading the teaching loft on a fresh device it IS the current loft (RF-12)', s['currentName'] == 'لوفت إربد التعليمي' and s['birds'] == 38, s['currentName'])
        text, toast, gone = ui_remove(d1, ROOT); s = run(d1, STATE)
        check('[one] the removal ran to completion — the row detached', gone and 'لم تُزل' not in toast, toast[:200])
        check('[one] removes that generation cleanly: 38 birds, 5 pairs, 17 races, 7 health, the loft', '38' in digits(text) and s['birds'] == 0 and s['pairs'] == 0 and s['tombstones'] == 68, (digits(text)[:120], s['birds'], s['tombstones']))
        check('[one · RF-14] the current loft was the one removed: the device recovered onto a real loft', s['current'] is not None and s['current'] == s['storedCurrent'] and s['current'] in s['lofts'] and s['currentName'] == '(unnamed)', {k: s[k] for k in ('current', 'storedCurrent', 'lofts')})
        check('[one] its sync pushes 68 tombstones', sync_ui(d1, ROOT) == 'synced' and srv.summary('user-B') == {'birds†': 38, 'healthEvents†': 7, 'lofts†': 1, 'pairs†': 5, 'raceResults†': 17}, srv.summary('user-B'))
        c1.close()

        # ═══ THE PILOT FLOW: load the teaching loft, add your own birds (they land in it), one descends from an example bird ═══
        c2, d2 = device(b, H, 'd@zajil.test'); load_large(d2, ROOT); d2.goto(H, wait_until='load'); d2.wait_for_function('window.__zajilReady')
        own = run(d2, """async (db) => { const sire = [...db.state.birds.values()].find(b => b.sex === 'cock' && b.sireId && b.damId);   // an example cock WITH parents, so the kept chain has depth
            const mine = await db.saveBird(db.newBird({ name: 'طيري-1', sex: 'hen', loftId: db.currentLoft().id, sireId: sire.id }));
            const other = await db.saveBird(db.newBird({ name: 'طيري-2', sex: 'cock', loftId: db.currentLoft().id }));
            const chain = []; let cur = sire; while (cur) { chain.push(cur.name); cur = db.state.birds.get(cur.sireId); }
            const closure = new Set(); const stack = [sire.id]; while (stack.length) { const id = stack.pop(); if (!id || closure.has(id)) continue; const a = db.state.birds.get(id); if (!a) continue; closure.add(id); stack.push(a.sireId, a.damId); }
            return { sire: sire.name, sireLoft: sire.loftId.slice(0, 8), mineLoft: mine.loftId.slice(0, 8), chainDepth: chain.length, chain, closure: closure.size }; }""")
        check('[own] the fancier’s birds were filed IN the teaching loft (it is current), one of them with an example sire whose own line has depth', own['mineLoft'] == own['sireLoft'] and own['chainDepth'] >= 2 and own['closure'] > own['chainDepth'], own)
        text, toast, gone = ui_remove(d2, ROOT); s = run(d2, STATE)
        kept_expected = own['chainDepth']   # the sire and his whole paternal chain at least
        check('[own] the dialog says how many example birds are kept as references and why, and that own records are moved', 'كمراجع في النسب' in text and 'تُنقل إلى لوفتك' in text, text[:220])
        bird = run(d2, """async (db) => { const m = [...db.state.birds.values()].find(b => b.name === 'طيري-1'); const sire = db.state.birds.get(m.sireId);
            const up = []; let cur = sire; while (cur) { up.push({ name: cur.name, external: !!cur.external, status: cur.status, loft: cur.loftId }); cur = db.state.birds.get(cur.sireId); }
            return { mine: { loft: m.loftId, sireLinked: !!sire }, up, own2: db.state.birds.has([...db.state.birds.values()].find(b => b.name === 'طيري-2')?.id) }; }""")
        check('[own] the ruled outcome: the example sire and his ancestors stay, as reference birds, and the pedigree link is intact', bird['mine']['sireLinked'] and len(bird['up']) == own['chainDepth'] and all(u['external'] and u['status'] == 'reference' for u in bird['up']), bird)
        check('[own] nothing else of the example data remains: the fancier’s own two birds and the whole ancestor closure of the sire (both sides), nothing more', s['birds'] == 2 + own['closure'] and bird['own2'] and s['pairs'] == s['races'] == s['health'] == 0, {k: s[k] for k in ('birds', 'pairs', 'races', 'health')} | {'closure': own['closure']})
        check('[own · RF-14] his birds and the kept references were re-filed under the loft that is current now — a loft that exists', s['current'] in s['lofts'] and bird['mine']['loft'] == s['current'] and all(u['loft'] == s['current'] for u in bird['up']), (s['current'], bird['mine']['loft'], [u['loft'][:8] for u in bird['up']]))
        check('[own] the kept birds carry the external tag in the register', set(s['external']) >= set(u['name'] for u in bird['up']), s['external'])
        # a bird added afterwards, and a reload
        after = run(d2, "async (db) => { const b = await db.saveBird(db.newBird({ name: 'طيري-3', sex: 'cock' })); return { loft: b.loftId, exists: db.state.lofts.has(b.loftId) }; }")
        check('[own · RF-14] a bird added afterwards is filed under a loft that exists', after['exists'] and after['loft'] == s['current'], after)
        d2.goto(H, wait_until='load'); d2.wait_for_function('window.__zajilReady'); r = run(d2, STATE)
        check('[own · RF-14] a reload keeps the recovery — the stored id still names a loft that exists', r['current'] == s['current'] and r['storedCurrent'] == s['current'] and r['currentName'] is not None, {k: r[k] for k in ('current', 'storedCurrent', 'currentName')})
        gone = row_present(d2, ROOT); d2.goto(H, wait_until='load'); d2.wait_for_function('window.__zajilReady')
        again = run(d2, "async (db) => { const big = await (await fetch('/example-loft-large.json')).json(); return db.importAll(big, 'merge'); }")
        check('[own] the row is gone', gone == 0, gone)
        # MEASURED, recorded as a follow-up (not ruled): the 68 tombstones the removal wrote are newer than the dataset's records,
        # so a merge-import of the same dataset on this device brings nothing back — the loader says «0» and the row stays absent
        check('[own · seen] loading the same teaching loft again on this device imports nothing — the tombstones win (follow-up, not ruled)', again['birds'] == 0 and again['skipped'] >= 68 and row_present(d2, ROOT) == 0, again)
        c2.close()

        # ═══ RF-14 by a PULLED tombstone: another device removes the loft this one is standing in ═══
        ca, da = device(b, H, 'c@zajil.test'); load_large(da, ROOT); da.goto(H, wait_until='load'); da.wait_for_function('window.__zajilReady'); run(da, "async (db) => { await db.syncNow(); }")
        cb, dbb = device(b, H, 'c@zajil.test'); run(dbb, "async (db) => { await db.syncNow(); }")
        sb = run(dbb, STATE); check('[pulled] the second device adopted the teaching loft as its current loft', sb['currentName'] == 'لوفت إربد التعليمي', sb['currentName'])
        ui_remove(da, ROOT); sync_ui(da, ROOT); run(dbb, "async (db) => { await db.syncNow(); }"); sb = run(dbb, STATE)
        check('[pulled · RF-14] when the pulled tombstone removes its current loft, the device recovers at once', sb['current'] is not None and sb['current'] in sb['lofts'] and sb['current'] == sb['storedCurrent'] and sb['birds'] == 0, {k: sb[k] for k in ('current', 'storedCurrent', 'lofts', 'birds')})
        ca.close(); cb.close()

        # ═══ THE INTERSECTION SHAPE (RF-18, 2026-10-30 — CONSTRUCTED, TF-10: this step GIVES the own bird the teaching dam نجمة ٢٦; no export ever held that link): both generations AND an own bird linked to a teaching parent AND an own record inside a teaching loft ═══
        cs_, ds = device(b, H, 'f@zajil.test')
        shape = run(ds, """async (db, old) => { await db.Lofts.save({ ...db.currentLoft(), name: 'Hummar' }); const mine = db.currentLoft();
            const big = await (await fetch('/example-loft-large.json')).json(); await db.importAll(big, 'merge'); await db.importAll(old, 'merge');
            const deep = [...db.state.birds.values()].find(x => x.name === 'نجمة ٢٦' && x.loftId === '8f268d1b-3dbe-57be-8d77-ede52297a2cd');
            await db.saveBird(db.newBird({ name: 'حمّار-1', sex: 'hen', loftId: mine.id, damId: deep.id }));
            await db.saveBird(db.newBird({ name: 'حمّار-2', sex: 'cock', loftId: '8f268d1b-3dbe-57be-8d77-ede52297a2cd' }));
            const p = await db.examplePresence(); const rings = {}; for (const id of p.keep) rings[id] = JSON.stringify(db.state.birds.get(id).rings || []);
            return { mine: mine.id, kept: p.kept, birds: p.birds, own: p.own, keptRings: rings, dup: db.state.birds.size }; }""", OLD)
        s0 = run(ds, STATE)
        check('[shape] the constructed intersection: 78 example birds (both generations) + 2 own birds, 29 to keep, 47 to delete, 1 own record inside a teaching loft', s0['birds'] == 78 and shape['kept'] == 29 and shape['birds'] == 47 and shape['own'] == 1, (s0['birds'], shape['kept'], shape['birds'], shape['own']))
        # the default save path still refuses a warning — the bypass is the removal's alone
        chk = run(ds, "async (db) => { const k = db.state.birds.get([...(await db.examplePresence()).keep][0]); try { await db.saveBird({ ...k, external: true, status: db.REFERENCE_STATUS }); return 'saved'; } catch (e) { return (e.warnings || []).map(w => w.key).join(','); } }")
        check('[shape] saveBird without the flag still refuses the duplicate-ring warning (the user-facing path is unchanged)', chk == 'val.dupRing' or chk.startswith('val.dupRing'), chk)
        # THE INVARIANT first: a failure that blocks (an ERROR, not a warning) must reach the fancier as a toast, and change nothing
        run(ds, """async (db) => { const p = await db.examplePresence(); for (const id of p.keep) { const k = db.state.birds.get(id); const sire = k.sireId && db.state.birds.get(k.sireId); if (sire) { await db.idbPut('birds', { ...sire, sex: 'hen' }); sire.sex = 'hen'; return; } } }""")   # a kept ancestor's sire recorded as a hen → val.sireIsHen, an error
        tools(ds, ROOT); open_row(ds, 'example-remove'); ds.click('[data-testid=example-remove]'); ds.wait_for_selector('[data-testid=dialog]', timeout=8000); ds.click('[data-testid=dialog-confirm]'); ds.wait_for_timeout(4000)
        ftoast = ds.locator('[data-testid=toast]').last.inner_text().replace('\n', ' ') if ds.locator('[data-testid=toast]').count() else ''
        s1 = run(ds, STATE)
        check('[shape · invariant] a removal that cannot proceed SAYS SO — a toast naming the reason, nothing changed', 'لم تُزل البيانات التجريبية' in ftoast and 'لم يتغيّر شيء' in ftoast and 'الأب' in ftoast and s1['birds'] == 78 and s1['tombstones'] == 0 and not ds.errs, (ftoast[:160], s1['birds'], s1['tombstones'], ds.errs[:1]))
        check('[shape · invariant] …and the row is still there with its count', row_present(ds, ROOT) == 1 and digits(ds.locator('[data-row=example-remove] [data-testid=row-value]').inner_text()).strip() == '76')
        run(ds, """async (db) => { for (const b of db.state.birds.values()) { if (b.sex === 'hen' && [...db.state.birds.values()].some(c => c.sireId === b.id)) { await db.idbPut('birds', { ...b, sex: 'cock' }); b.sex = 'cock'; } } }""")   # undo the forced error
        # now the removal itself
        text, toast, gone = ui_remove(ds, ROOT); s2 = run(ds, STATE)
        check('[shape] the removal RAN TO COMPLETION — the row detached, no failure toast (R1 fails here: the flag not passed)', gone and 'لم تُزل' not in toast, toast[:200])
        after = run(ds, """async (db) => { const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i; const birds = [...db.state.birds.values()];
            const kept = birds.filter(b => !V4.test(b.id)); const rings = {}; for (const b of kept) rings[b.id] = JSON.stringify(b.rings || []);
            const own = birds.filter(b => V4.test(b.id)); return { exampleLeft: kept.length, keptAllRefs: kept.every(b => b.external && b.status === 'reference'), keptRings: rings, ownLofts: own.map(b => [b.name, b.loftId]), current: db.state.currentLoftId }; }""")
        check('[shape] the dialog said 47 deleted, 29 kept, 1 own record inside', all(x in digits(text) for x in ['47', '29']) and 'لديك 1' in digits(text), digits(text)[:200])
        check('[shape] 47 deleted — 29 example birds remain, every one a reference bird', after['exampleLeft'] == 29 and after['keptAllRefs'] and s2['birds'] == 31, (after['exampleLeft'], after['keptAllRefs'], s2['birds']))
        check('[shape] the 29 kept WITH THEIR RINGS INTACT', all(after['keptRings'].get(k) == v for k, v in shape['keptRings'].items()), sum(1 for k, v in shape['keptRings'].items() if after['keptRings'].get(k) != v))
        check('[shape] the own record inside the teaching loft was re-filed to the own loft, which is current', all(l == shape['mine'] for _, l in after['ownLofts']) and after['current'] == shape['mine'] and s2['lofts'] == {shape['mine']: 'Hummar'}, (after['ownLofts'], s2['lofts']))
        check('[shape] both teaching lofts gone, tombstoned, the toast reports 47 and 29', s2['tombstones'] >= 47 + 10 + 34 + 14 + 2 and '47' in digits(toast) and '29' in digits(toast), (s2['tombstones'], digits(toast)[:120]))
        cs_.close()

        # ═══ RF-22 / H3 (RULED 2026-11-01, built 2026-11-16): membership is THE SHIPPED DATASETS' OWN IDS — not the loft, not the id's shape ═══
        ch, h0 = device(b, H, 'h@zajil.test')
        sets = run(h0, "async (db) => { const s = await db.exampleIds(); return Object.fromEntries(Object.entries(s).map(([k, v]) => [k, [...v]])); }")
        import uuid as _uuid
        NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f'); UU = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        PUB = os.path.join(HERE, '..', '..', '..', 'public'); files = [json.load(open(os.path.join(PUB, f), encoding='utf-8')) for f in ('example-loft-large.json', 'sample-data.json')]
        STORES = ['lofts', 'birds', 'pairs', 'raceResults', 'healthEvents']
        shipped_now = {st: sorted(r['id'] for f in files for r in f.get(st, [])) for st in STORES}
        check('[H3 · the set] the uuid half of the membership set is EXACTLY the ids the two shipped files carry, store by store — none missing, none extra',
              all(sorted(i for i in sets[st] if UU.match(i)) == shipped_now[st] for st in STORES), {st: (len([i for i in sets[st] if UU.match(i)]), len(shipped_now[st])) for st in STORES})
        check('[H3 · the set] …and the other half is the pre-1.9.1 keys those ids are derived from (Python uuid5 over the same namespace): 2 lofts, 58 birds, 9 pairs, 29 results, 13 health — twice each',
              all(sorted(str(_uuid.uuid5(NS, k)) for k in sets[st] if not UU.match(k)) == shipped_now[st] for st in STORES) and {st: len(sets[st]) for st in STORES} == {'lofts': 4, 'birds': 116, 'pairs': 18, 'raceResults': 58, 'healthEvents': 26}, {st: len(sets[st]) for st in STORES})

        # ── direction ONE: a teaching bird filed in ANOTHER loft is still example data (the old rule kept it, and its ancestors, as the fancier's) ──
        one = run(h0, """async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفتي' }); const mine = db.currentLoft();
            await db.importAll(await (await fetch('/example-loft-large.json')).json(), 'merge');
            const kids = new Set(); for (const x of db.state.birds.values()) { kids.add(x.sireId); kids.add(x.damId); }
            const x = [...db.state.birds.values()].find(y => y.sireId && y.damId && !kids.has(y.id));        // a teaching bird with both parents and no offspring
            await db.idbPut('birds', { ...x, loftId: mine.id }); db.state.birds.set(x.id, { ...x, loftId: mine.id });   // as a pull from another device leaves it
            const p = await db.examplePresence(); return { mine: mine.id, moved: x.name, movedId: x.id, birds: p.birds, kept: p.kept, elsewhere: p.elsewhere, because: p.because.length, own: p.own }; }""")
        check('[H3 · M-loft fails here] a teaching bird filed in the fancier\'s own loft IS example data: 38 to delete, none kept, 1 counted outside the teaching loft, and it causes no keep',
              one['birds'] == 38 and one['kept'] == 0 and one['elsewhere'] == 1 and one['because'] == 0 and one['own'] == 0, one)
        text, toast, gone = ui_remove(h0, ROOT); s = run(h0, STATE)
        check('[H3 · M-loft fails here] …the removal deletes it with the rest: no bird left, no reference bird made, the own loft untouched', gone and s['birds'] == 0 and s['external'] == [] and s['lofts'] == {one['mine']: 'لوفتي'} and 'كمراجع' not in text, (s['birds'], s['external'], text[:160]))
        ch.close()

        # ── direction TWO: a fancier's record whose id is NOT a v4 uuid, filed IN the teaching loft, is NOT example data (the old rule deleted it) ──
        ci, h1 = device(b, H, 'i@zajil.test')
        two = run(h1, """async (db) => { await db.importAll(await (await fetch('/example-loft-large.json')).json(), 'merge');
            const loft = '8f268d1b-3dbe-57be-8d77-ede52297a2cd'; const sire = [...db.state.birds.values()].find(x => x.sex === 'cock' && x.sireId && x.damId);
            const at = '2025-01-05T08:00:00.000Z';
            await db.importAll({ format: 'zajil-export', version: 1, birds: [{ ...db.newBird({ name: 'قديم-العهد', sex: 'hen' }), id: 'bird-0007', loftId: loft, sireId: sire.id, createdAt: at, updatedAt: at }] }, 'merge');
            for (let i = 1; i <= 6; i++) await db.saveBird(db.newBird({ name: 'سليل-' + i, sex: 'cock', loftId: loft, sireId: sire.id }));
            const closure = new Set(); const stack = [sire.id]; while (stack.length) { const id = stack.pop(); if (!id || closure.has(id)) continue; const a = db.state.birds.get(id); if (!a) continue; closure.add(id); stack.push(a.sireId, a.damId); }
            const p = await db.examplePresence(); const before = {}; for (const x of db.state.birds.values()) before[x.id] = JSON.parse(JSON.stringify(x));
            return { sire: sire.id, closure: closure.size, birds: p.birds, kept: p.kept, own: p.own, because: p.because.map(x => x.name), keep: [...p.keep], before, shown: db.BECAUSE_SHOWN }; }""")
        check('[H3 · M-nonv4 fails here] a record with a non-uuid id that the datasets never shipped is the fancier\'s OWN, though it sits in the teaching loft: 7 own records, and it is among the causes of the keep, which are listed by name',
              two['own'] == 7 and two['kept'] == two['closure'] and two['birds'] == 38 - two['closure'] and two['because'] == [f'سليل-{i}' for i in range(1, 7)] + ['قديم-العهد'], {k: two[k] for k in ('own', 'kept', 'closure', 'birds', 'because')})
        tools(h1, ROOT); open_row(h1, 'example-remove'); h1.click('[data-testid=example-remove]'); h1.wait_for_selector('[data-testid=dialog]', timeout=8000)
        IN_DIALOG = SCAN.replace("document.body.querySelectorAll('*')", "document.querySelector('[data-testid=dialog]').querySelectorAll('*')"); assert IN_DIALOG != SCAN   # the question itself: الأدوات behind it draws «غير معروف» for the version in the mono face on a build with no service worker — seen 2026-11-16, reported, not this check's subject
        q = digits(h1.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')); typo = h1.evaluate(IN_DIALOG); h1.click('[data-testid=dialog-cancel]'); h1.wait_for_timeout(400)
        check('[H3 · M-names fails here] the question NAMES the birds that cause the keep: «بسبب:» and the first five, by name', two['shown'] == 5 and 'بسبب: سليل-1، سليل-2، سليل-3، سليل-4، سليل-5' in q, q)
        check('[H3 · M-names fails here] …and says «و2 غيرها» for the other two, without naming them', 'سليل-5 و2 غيرها.' in q and 'سليل-6' not in q and 'قديم-العهد' not in q, q)
        check('[typography] the question with the names is drawn in a face that has Arabic', not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        text, toast, gone = ui_remove(h1, ROOT); s = run(h1, STATE)
        after = run(h1, "async (db) => { const o = {}; for (const x of db.state.birds.values()) o[x.id] = JSON.parse(JSON.stringify(x)); return o; }")
        check('[H3 · A-set · M-patch fails here] the removal ran to completion', gone and 'لم تُزل' not in toast, toast[:200])
        mine = after.get('bird-0007')
        check('[H3 · M-nonv4 fails here] the fancier\'s old-id bird SURVIVES the removal, re-filed to the loft that is current, its teaching sire still linked and now a reference',
              bool(mine) and mine['loftId'] == s['current'] and mine['sireId'] == two['sire'] and after.get(two['sire'], {}).get('external') is True and after[two['sire']]['status'] == 'reference', mine)
        check('[H3] the seven own birds and the kept closure remain, nothing else', s['birds'] == 7 + two['closure'] and sorted(k for k in after if k not in two['keep']) == sorted(['bird-0007'] + [k for k, v in two['before'].items() if v['name'].startswith('سليل-')]), s['birds'])
        # THE A-SET: a removal re-save may alter only the reference flag (external, and the status that goes with it) and loftId
        diffs = {}
        for k, v in after.items():
            ch_ = sorted(f for f in set(v) | set(two['before'][k]) if v.get(f) != two['before'][k].get(f) and f not in ('updatedAt', 'deviceId'))   # the two stamps every save writes: when, and from which device
            if ch_: diffs[k] = ch_
        check('[A-set · M-alter fails here] across the kept references and the re-filed birds, the removal altered ONLY external, status and loftId (and the two stamps every save writes, updatedAt and deviceId)',
              len(after) == 7 + two['closure'] and all(set(d) <= {'external', 'status', 'loftId'} for d in diffs.values()) and len(diffs) == len(after), sorted({f for d in diffs.values() for f in d}))
        check('[A-set] …the kept references are references in the current loft; the own birds changed their loft and nothing else', all(diffs.get(k) == ['loftId'] for k in after if k not in two['keep']) and all(after[k]['external'] is True and after[k]['status'] == 'reference' and after[k]['loftId'] == s['current'] for k in two['keep']), {k: diffs.get(k) for k in list(after)[:3]})
        check('[H3] the row is gone though the kept references carry dataset ids: nothing of the example data is left to remove', row_present(h1, ROOT) == 0)
        ci.close()

        # ═══ RF-14 AT BOOT: a device that dangled BEFORE this build (a loft removed by an older version, or by the console route) ═══
        cl, dl = device(b, H, 'e@zajil.test'); run(dl, "async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفتي' }); await db.setSetting('currentLoftId', 'ghost-loft-id'); }")
        dl.goto(H, wait_until='load'); dl.wait_for_function('window.__zajilReady'); sl = run(dl, STATE)
        check('[boot · RF-14] a stored id that names no loft, with exactly one loft on the device: boot adopts that loft', sl['current'] is not None and sl['currentName'] == 'لوفتي' and sl['storedCurrent'] == sl['current'] and len(sl['lofts']) == 1, {k: sl[k] for k in ('current', 'storedCurrent', 'currentName', 'lofts')})
        run(dl, "async (db) => { await db.Lofts.save({ name: 'لوفت ثانٍ', location: '', statuses: [] }); await db.setSetting('currentLoftId', 'ghost-loft-id'); }")
        dl.goto(H, wait_until='load'); dl.wait_for_function('window.__zajilReady'); sl = run(dl, STATE)
        check('[boot · RF-14] …with several lofts and no way to choose: boot makes a fresh pristine loft current — a clear state, never a dangle', sl['current'] is not None and sl['currentName'] == '(unnamed)' and sl['storedCurrent'] == sl['current'] and len(sl['lofts']) == 3, {k: sl[k] for k in ('current', 'storedCurrent', 'currentName', 'lofts')})
        nb = run(dl, "async (db) => { const b = await db.saveBird(db.newBird({ name: 'بعد', sex: 'cock' })); return db.state.lofts.has(b.loftId); }")
        check('[boot · RF-14] a bird added afterwards is filed under a loft that exists', nb)
        cl.close()

        # TF-9 (2026-10-30): until this date the check iterated over an EMPTY list and could not fail
        # ═══ TF-12 (RULED 2026-11-15): the removal row's recompute, held at examplePresence()'s media read ═══
        # The hold: IDBObjectStore.getAll on `media` hands back a stand-in request whose success is delivered only on
        # release. deleteBird()'s own media read goes through an INDEX and is not held.
        HOLD = """() => { if (window.__hold) return; const H = window.__hold = { n: 0, held: [], release() { const h = this.held; this.held = []; h.forEach(f => f()); } };
          const orig = IDBObjectStore.prototype.getAll;
          IDBObjectStore.prototype.getAll = function (...a) { const real = orig.apply(this, a); if (this.name !== 'media' || H.n <= 0) return real;
            H.n--; const fake = { result: undefined, error: null, onsuccess: null, onerror: null };
            real.onsuccess = () => { fake.result = real.result; H.held.push(() => fake.onsuccess && fake.onsuccess({ target: fake })); };
            real.onerror = () => { fake.error = real.error; fake.onerror && fake.onerror({ target: fake }); }; return fake; }; }"""
        ROWV = "() => { const r = document.querySelector('[data-row=example-remove] [data-testid=row-value]'); return r ? r.textContent : null; }"
        def held_device(email):
            c_, d_ = device(b, H, email); run(d_, "async (db) => { const big = await (await fetch('/example-loft-large.json')).json(); await db.importAll(big, 'merge'); }")
            tools(d_, ROOT); d_.wait_for_selector('[data-row=example-remove]', timeout=15000); d_.wait_for_timeout(6000)     # past the boot cycle and the after-change cycle
            d_.evaluate(HOLD); d_.evaluate("() => { window.__hold.n = 1; }"); run(d_, "async (db) => { db.emitChange({ type: 'probe' }); }")
            try: d_.wait_for_function("() => window.__hold.held.length === 1", timeout=5000)
            except PWTimeout: pass
            return c_, d_, d_.evaluate("() => window.__hold.held.length")
        ch, dh, held = held_device('h@zajil.test')
        check('[TF-12 · setup] the row shows the 38 and ONE recompute of it is held at the media read, the loft still there', digits(dh.evaluate(ROWV) or '') == '38' and held == 1, (dh.evaluate(ROWV), held))
        rem = run(dh, "async (db) => { const r = await db.removeExampleData(); return r && r.birds; }"); dh.wait_for_timeout(1200)
        check('[TF-12] the removal ran with that recompute still held, and the row is gone', rem == 38 and dh.evaluate(ROWV) is None, (rem, dh.evaluate(ROWV)))
        dh.evaluate("() => window.__hold.release()"); dh.wait_for_timeout(1200)
        check('[TF-12 · M-recheck fails here] released AFTER its loft was removed, the held recompute raises no page error', not dh.errs, [e[:200] for e in dh.errs][:1])
        check('[TF-12] …and the row stays gone', dh.evaluate(ROWV) is None, dh.evaluate(ROWV))
        ch.close()
        co, do, held = held_device('o@zajil.test')
        do.evaluate("""() => { const W = window.__seen = []; const read = () => { const r = document.querySelector('[data-row=example-remove] [data-testid=row-value]'); const x = r ? r.textContent : '(no row)';
            if (!W.length || W[W.length - 1] !== x) W.push(x); }; read(); new MutationObserver(read).observe(document.body, { subtree: true, childList: true, characterData: true }); }""")
        run(do, """async (db) => { const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i; const all = [...db.state.birds.values()];
            const leaf = all.find(b => !V4.test(b.id) && !all.some(c => c.sireId === b.id || c.damId === b.id)); await db.deleteBird(leaf.id); }"""); do.wait_for_timeout(800)
        mid = digits(do.evaluate(ROWV) or '')
        do.evaluate("() => window.__hold.release()"); do.wait_for_timeout(500); late = digits(do.evaluate(ROWV) or ''); do.wait_for_timeout(4500)
        seen = [digits(x) for x in do.evaluate("() => window.__seen")]
        check('[TF-12 · setup] one recompute held, one example bird deleted: the row went from 38 to 37', held == 1 and mid == '37', (held, mid))
        check('[TF-12 · M-order fails here] the held recompute, released late with the OLD count, is dropped — the row never shows 38 again', late == '37' and seen == ['38', '37'], (late, seen))
        co.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
