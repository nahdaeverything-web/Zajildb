"""LOADING THE TEACHING DATA AGAIN AFTER REMOVING IT (RF-16, RULED 2026-11-18).

The removal tombstones every example record, and a merge refuses a record whose deletion is newer — so a second load
imported nothing, without a word. The three dataset loaders now forget the tombstones of the shipped ids in the file
they are about to load (src/example-data.js loadExampleDataset); importAll is untouched and goes on honouring every
deletion; an example bird kept as a reference stays a reference. This suite also REPEATS the 16 October sync
measurement under membership by shipped id, against a stub that models the trigger's last-write-wins
(docs/SYNC-DESIGN.md §1: an older write keeps the winner's body, and server_seq still advances).
Harness build, stub project, the net armed.

    python3 tests/e2e/screens/example_reload.py
"""
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net, no_bucket                          # noqa: E402
NET = Net()
PAGES = []

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

STUB = 'https://stub.example.test'

class Server:
    """Owner rows, one global server_seq, deletes as deleted=true — AND the trigger's last-write-wins."""
    def __init__(self): self.rows = {}; self.seq = 0; self.rejected = 0; self.posts = []
    def upsert(self, o, r):
        k = (o, r['store'], r['record_id']); old = self.rows.get(k); self.seq += 1
        if old and (r['updated_at'] < old['updated_at'] or (r['updated_at'] == old['updated_at'] and r['device_id'] <= old['device_id'])):
            self.rejected += 1; row = dict(old, server_seq=self.seq)          # new := old — the winner's body, a fresh seq
        else: row = dict(r, server_seq=self.seq, owner=o)
        self.rows[k] = row; return row
    def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
    def summary(self, o):
        out = {}
        for (w, s, _), r in self.rows.items():
            if w == o: k = s + ('†' if r['deleted'] else ''); out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))
srv = Server()
def handler(route, request):
    if no_bucket(route, request): return          # this suite's project has no photo bucket (tests/e2e/_net.py)
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
STATE = """async (db) => { const IDS = await db.exampleIds(); const tombs = await db.idbGetAll('tombstones');
  const lofts = Object.fromEntries([...db.state.lofts.values()].map(l => [l.id, l.name || '(unnamed)']));
  const standing = tombs.filter(t => db.state[t.store] && db.state[t.store].has(t.recordId)).length;
  return { lofts, birds: db.state.birds.size, pairs: db.state.pairs.size, races: db.state.raceResults.size, health: db.state.healthEvents.size,
    example: [...db.state.birds.values()].filter(b => IDS.birds.has(b.id)).length,
    current: (db.currentLoft() || {}).id || null, currentName: db.currentLoft() ? (db.currentLoft().name || '(unnamed)') : null,
    tombstones: tombs.length, exampleTombs: tombs.filter(t => IDS[t.store] && IDS[t.store].has(t.recordId)).length, standing,
    pending: (await db.listOps()).filter(o => !o.pushed && !o.superseded).length }; }"""
SYNC = "async (db) => { const r = await db.syncNow(); return r && r.ok !== false; }"

def device(b, H, email):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
    ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email); return ctx, pg
def home(pg, H): pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady')
def open_row(pg, row):
    r = pg.locator(f'[data-row={row}]')
    if r.get_attribute('open') is None: r.locator('summary').click(); pg.wait_for_timeout(300)
def tools(pg, ROOT):
    pg.goto(ROOT + 'tools/', wait_until='load'); pg.wait_for_selector('[data-testid=tools-list]', timeout=15000); pg.wait_for_timeout(800)
def last_toast(pg): return pg.locator('[data-testid=toast]').last.inner_text().replace('\n', ' ') if pg.locator('[data-testid=toast]').count() else ''
def load_tools(pg, ROOT, which='load-large'):
    """The loader in الأدوات. Returns the toast."""
    tools(pg, ROOT); open_row(pg, 'teaching'); pg.click(f'[data-testid={which}]'); pg.wait_for_timeout(4000); return last_toast(pg)
def load_empty_state(pg, ROOT):
    """The loader on the empty register. Returns the toast, or None when the empty state is not shown."""
    pg.goto(ROOT + 'birds/', wait_until='load'); pg.wait_for_timeout(1500)
    if not pg.locator('[data-testid=empty-example]').count(): return None
    pg.click('[data-testid=empty-example]'); pg.wait_for_timeout(4000); return last_toast(pg)
def remove(pg): return run(pg, "async (db) => { const r = await db.removeExampleData(); return r && r.birds; }")
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s or '')
FULL = {'birds': 38, 'healthEvents': 7, 'lofts': 1, 'pairs': 5, 'raceResults': 17}
GONE = {'birds†': 38, 'healthEvents†': 7, 'lofts†': 1, 'pairs†': 5, 'raceResults†': 17}

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ ONE DEVICE: load, remove, load again — from the empty register ═══
        c1, d1 = device(b, H, 'a@zajil.test'); run(d1, SYNC); load_tools(d1, ROOT); home(d1, H); run(d1, SYNC)
        n = remove(d1); s = run(d1, STATE)
        check('[setup] the teaching loft was loaded and removed: 38 birds gone, 68 tombstones, every one for a shipped id', n == 38 and s['birds'] == 0 and s['tombstones'] == 68 and s['exampleTombs'] == 68, s)
        run(d1, SYNC); check('[setup] the removal is on the server: 68 deleted rows', srv.summary('user-A') == GONE, srv.summary('user-A'))
        plain = run(d1, "async (db) => { const big = await (await fetch('/example-loft-large.json')).json(); const c = await db.importAll(big, 'merge'); return { birds: c.birds, skipped: c.skipped }; }")
        s = run(d1, STATE)
        check('[importAll] importing the same file as a BACKUP still brings nothing back — importAll honours the deletions (M-inimport fails here)', plain['birds'] == 0 and plain['skipped'] >= 68 and s['birds'] == 0 and s['tombstones'] == 68, (plain, s['birds'], s['tombstones']))
        rej0 = srv.rejected
        toast = load_empty_state(d1, ROOT); home(d1, H); s = run(d1, STATE)
        check('[reload · empty state] «تحميل سرب تعليمي» on the empty register loads it again: 38 birds, 5 pairs, 17 results, 7 health (M-nostamp fails here)', toast is not None and s['birds'] == 38 and s['pairs'] == 5 and s['races'] == 17 and s['health'] == 7, (toast, s))
        check('[reload · empty state] the toast says 38', '38' in digits(toast), toast)
        check('[reload] the 68 tombstones are forgotten and none stands against a record that is here (M-noforget fails here)', s['tombstones'] == 0 and s['standing'] == 0, (s['tombstones'], s['standing']))
        check('[reload] the removal row is back in الأدوات — the data is recognised as example data again', (tools(d1, ROOT), d1.locator('[data-row=example-remove]').count())[1] == 1)
        home(d1, H); ok = run(d1, SYNC)
        check('[sync] the reload is pushed and passes the server’s last-write-wins: 68 live rows, 0 rejected', ok and srv.summary('user-A') == FULL and srv.rejected == rej0, (srv.summary('user-A'), srv.rejected - rej0))

        # ═══ THE 16 OCTOBER MEASUREMENT, REPEATED under membership by shipped id ═══
        c2, d2 = device(b, H, 'a@zajil.test'); run(d2, SYNC); s2 = run(d2, STATE)
        check('[sync · new device] a device that signs in after the reload holds the data: 38 birds, no tombstones', s2['birds'] == 38 and s2['tombstones'] == 0, s2)
        # d2 removes locally and stays offline; d1 removes, syncs, loads again, syncs; then d2 syncs
        n2 = remove(d2); p2 = run(d2, STATE)
        check('[sync · setup] the second device removed locally and has not synced: its deletions are pending', n2 == 38 and p2['birds'] == 0 and p2['pending'] >= 68, p2)
        remove(d1); run(d1, SYNC); t = load_tools(d1, ROOT); home(d1, H); run(d1, SYNC)
        check('[reload · الأدوات] the loader in الأدوات loads it again after a second removal', run(d1, STATE)['birds'] == 38 and '38' in digits(t), t)
        rej1 = srv.rejected; posts1 = len(srv.posts); ok = run(d2, SYNC); s2 = run(d2, STATE)
        check('[sync · removed BEFORE the reload] that device pulls first and holds the data again; its older deletions do not win', ok and s2['birds'] == 38 and s2['standing'] == 0 and srv.summary('user-A') == FULL, (s2, srv.summary('user-A')))
        print(f'    measured: pending before {p2["pending"]} · after {s2["pending"]} · POSTs by that sync {[x[1:] for x in srv.posts[posts1:]]} · rejected by LWW {srv.rejected - rej1}')
        # a removal AFTER the reload wins, everywhere
        remove(d2); run(d2, SYNC); run(d1, SYNC); s1 = run(d1, STATE)
        check('[sync · removed AFTER the reload] the later removal wins: the other device follows, the server holds 68 deleted rows', s1['birds'] == 0 and srv.summary('user-A') == GONE, (s1['birds'], srv.summary('user-A')))
        c3, d3 = device(b, H, 'a@zajil.test'); run(d3, SYNC)
        check('[sync · new device] a brand-new device ends with the latest intent — nothing', run(d3, STATE)['birds'] == 0, run(d3, STATE)['birds'])
        c1.close(); c2.close(); c3.close()

        # ═══ THE DEVICE'S OWN PUSHED DELETIONS COME BACK ON ITS NEXT PULL (measured 2026-11-18: 11 of 68 records lost again) ═══
        c7, d7 = device(b, H, 'g@zajil.test'); load_tools(d7, ROOT); home(d7, H); run(d7, SYNC); t0 = run(d7, "async (db) => db.nowISO()")
        remove(d7); run(d7, "async (db) => { await db.pushAll(); }")           # pushed, NOT pulled: the 68 deletions now sit above this device's cursor
        check('[own deletions · setup] the removal is pushed and not yet pulled back', srv.summary('user-G') == GONE, srv.summary('user-G'))
        tools(d7, ROOT); open_row(d7, 'teaching')
        d7.evaluate("""() => { const put = IDBObjectStore.prototype.put; window.__fired = 0;
            IDBObjectStore.prototype.put = function (...a) { if (this.name === 'lofts' && !window.__fired) { window.__fired = 1; Promise.resolve(window.__zajilDb).then(db => db.pullAll()).then(() => { window.__fired = 2; }); } return put.apply(this, a); }; }""")
        d7.click('[data-testid=load-large]'); d7.wait_for_timeout(4000); fired = d7.evaluate("() => window.__fired"); home(d7, H)
        check('[own deletions · setup] a pull of those deletions STARTED in the middle of the load, and finished', fired == 2, fired)
        stamps = run(d7, "async (db, t0) => { const IDS = await db.exampleIds(); const bs = [...db.state.birds.values()].filter(b => IDS.birds.has(b.id)); return { n: bs.length, newer: bs.filter(b => (b.updatedAt || '') > t0).length }; }", t0)
        check('[own deletions] every record loaded again is stamped as made now — newer than its removal', stamps == {'n': 38, 'newer': 38}, stamps)
        run(d7, SYNC); run(d7, SYNC); s7 = run(d7, STATE)
        check('[own deletions] the pull that brings the device’s own deletions back does not remove the reloaded data', s7['birds'] == 38 and s7['pairs'] == 5 and s7['races'] == 17 and s7['health'] == 7 and s7['tombstones'] == 0, s7)
        check('[own deletions] …and the server holds it live', srv.summary('user-G') == FULL, srv.summary('user-G'))
        c8, d8 = device(b, H, 'g@zajil.test'); run(d8, SYNC)
        check('[own deletions] …and a second device receives all of it', run(d8, STATE)['example'] == 38, run(d8, STATE)['example'])
        first = run(d8, "async (db) => { const big = await (await fetch('/example-loft-large.json')).json(); const IDS = await db.exampleIds(); return big.birds.filter(x => IDS.birds.has(x.id)).length; }")
        c7.close(); c8.close()
        # a FIRST load is untouched: the records keep the file's own updatedAt
        c9, d9 = device(b, H, 'h@zajil.test'); load_tools(d9, ROOT); home(d9, H)
        same = run(d9, "async (db) => { const big = await (await fetch('/example-loft-large.json')).json(); return big.birds.filter(x => (db.state.birds.get(x.id) || {}).updatedAt === x.updatedAt).length; }")
        check('[first load] a first load stamps nothing: all 38 birds keep the file’s own updatedAt', same == 38 and first == 38, (same, first))
        c9.close()

        # ═══ KEPT REFERENCES STAY REFERENCES (the same ruling) ═══
        c4, d4 = device(b, H, 'd@zajil.test'); load_tools(d4, ROOT); home(d4, H)
        own = run(d4, """async (db) => { const sire = [...db.state.birds.values()].find(b => b.sex === 'cock' && b.sireId && b.damId);
            const mine = await db.saveBird(db.newBird({ name: 'طيري-1', sex: 'hen', loftId: db.currentLoft().id, sireId: sire.id }));
            const closure = new Set(); const stack = [sire.id]; while (stack.length) { const id = stack.pop(); if (!id || closure.has(id)) continue; const a = db.state.birds.get(id); if (!a) continue; closure.add(id); stack.push(a.sireId, a.damId); }
            return { mine: mine.id, sire: sire.id, closure: [...closure] }; }""")
        run(d4, SYNC); run(d4, SYNC)   # settled first: a removal overlapping an automatic pull is RF-26, measured on its own
        remove(d4); home(d4, H)
        KEPT = """async (db, ids) => ids.map(id => { const x = db.state.birds.get(id); return x ? { external: !!x.external, status: x.status, loft: x.loftId, at: x.updatedAt } : null; })"""
        before = run(d4, KEPT, own['closure']); sb = run(d4, STATE)
        check('[kept · setup] the removal kept the sire’s whole ancestor closure as reference birds in the fancier’s loft', all(k and k['external'] and k['status'] == 'reference' and k['loft'] == sb['current'] for k in before) and sb['birds'] == 1 + len(own['closure']), (len(own['closure']), sb['birds']))
        t = load_tools(d4, ROOT); home(d4, H); after = run(d4, KEPT, own['closure']); sa = run(d4, STATE)
        check('[kept] a reload leaves every kept reference EXACTLY as it was — still a reference, same loft, not rewritten (M-touchkept fails here)', after == before, [(a, b_) for a, b_ in zip(after, before) if a != b_][:2])
        check('[kept] the rest of the teaching loft came back around them: 38 example birds in all, and the fancier’s own bird', sa['example'] == 38 and sa['birds'] == 39 and sa['standing'] == 0, sa)
        check('[kept] the toast counts only what was loaded', str(38 - len(own['closure'])) in digits(t), t)
        link = run(d4, "async (db, o) => { const m = db.state.birds.get(o.mine); return m.sireId === o.sire && db.state.birds.has(o.sire); }", own)
        check('[kept] the fancier’s bird still points at its sire', link)
        c4.close()

        # ═══ MEMBERSHIP: only shipped ids, whatever the file carries ═══
        c5, d5 = device(b, H, 'e@zajil.test')
        m = run(d5, """async (db) => { const mine = await db.saveBird(db.newBird({ name: 'طيري-المحذوف', sex: 'cock', loftId: db.currentLoft().id })); await db.deleteBird(mine.id);
            const big = await (await fetch('/example-loft-large.json')).json(); big.birds = [...big.birds, { ...mine }];
            const c = await db.loadExampleDataset(big);
            return { forgotten: c.forgotten, back: db.state.birds.has(mine.id), tomb: !!(await db.getTombstone('birds', mine.id)), birds: db.state.birds.size }; }""")
        check('[membership] a fancier’s own deleted bird smuggled into the file is NOT brought back, and its tombstone stands (M-anyid fails here)', m['back'] is False and m['tomb'] is True and m['forgotten'] == 0 and m['birds'] == 38, m)
        # the small dataset, through its own button
        remove(d5); home(d5, H); load_tools(d5, ROOT, 'load-sample'); home(d5, H); a1 = run(d5, STATE); remove(d5); home(d5, H)
        gone = run(d5, STATE); load_tools(d5, ROOT, 'load-sample'); home(d5, H); a2 = run(d5, STATE)
        check('[reload · small] the small teaching loft loads again after its removal, to the same counts', a1['example'] > 0 and gone['example'] == 0 and (a2['example'], a2['pairs'], a2['races'], a2['health']) == (a1['example'], a1['pairs'], a1['races'], a1['health']), (a1['example'], gone['example'], a2['example']))
        c5.close()

        # ═══ A LOAD THAT FAILS forgets nothing it did not replace ═══
        c6, d6 = device(b, H, 'f@zajil.test'); load_tools(d6, ROOT); home(d6, H); run(d6, SYNC); remove(d6); run(d6, SYNC); run(d6, SYNC)
        tools(d6, ROOT); open_row(d6, 'teaching')
        d6.evaluate("""() => { const put = IDBObjectStore.prototype.put; window.__unbreak = () => { IDBObjectStore.prototype.put = put; };
            IDBObjectStore.prototype.put = function (...a) { if (this.name === 'birds') throw new DOMException('injected-write-failure', 'QuotaExceededError'); return put.apply(this, a); }; }""")
        d6.click('[data-testid=load-large]'); d6.wait_for_timeout(4000); toast = last_toast(d6); d6.evaluate("() => window.__unbreak()")
        f = run(d6, STATE)
        check('[failure] a load that storage refuses says so', 'لم يكتمل' in toast and 'injected-write-failure' in toast, toast[:200])
        check('[failure] …and the deletions of everything that did NOT come in still stand: 67 tombstones, none against a record that is here (M-clearabsent fails here)', f['birds'] == 0 and f['tombstones'] == 67 and f['standing'] == 0, f)
        t = load_tools(d6, ROOT); home(d6, H); f = run(d6, STATE)
        check('[failure] the next load, with storage working, completes', f['birds'] == 38 and f['tombstones'] == 0, f)
        c6.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
