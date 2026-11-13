"""RF-15 — A REPLACE TRAVELS (RULED 2026-11-13).

A replace-import, and a restore (which is a replace of a snapshot), used to clear the stores and leave no trace of what
they removed. Measured on the deployed build: the next pull brought the whole pre-import set back, and any record another
device touched afterwards returned for good. Now every dropped record is tombstoned and pushed as a deletion, so nothing
dropped comes back and the person's other device converges on the file; the confirmation states the count removed (and,
for a restore, what comes back) and that it applies on every device.

Two devices on one stub project that models the real table (owner rows, one server_seq, the §4 last-write-wins trigger).
Every pull that matters is fired DURING the operation and again AFTER it. Harness build, the net armed. All shapes are
CONSTRUCTED.

    python3 tests/e2e/screens/replace_sync.py
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET: armed beneath the stub, asserted at the end
NET = Net()
PAGES = []

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

STUB = 'https://stub.example.test'

class Server:
    """sync_records as docs/SYNC-DESIGN.md §1 describes it: upsert on (owner, store, record_id), a server_seq per write, §4 LWW in the trigger."""
    def __init__(self): self.rows = {}; self.seq = 0
    def upsert(self, o, r):
        key = (o, r['store'], r['record_id']); old = self.rows.get(key); row = dict(r)
        if old is not None and (row['updated_at'], str(row.get('device_id') or '')) <= (old['updated_at'], str(old.get('device_id') or '')): row = dict(old)
        self.seq += 1; row['server_seq'] = self.seq; row['owner'] = o; self.rows[key] = row; return row
    def page(self, o, c, n): return sorted((r for (w, _, _), r in self.rows.items() if w == o and r['server_seq'] > c), key=lambda r: r['server_seq'])[:n]
    def live(self, o, store): return sorted((r['data'].get('name') or r['record_id']) for (w, s, _), r in self.rows.items() if w == o and s == store and not r['deleted'])
srv = Server()
def handler(route, request):
    if '/auth/v1/token' in request.url:
        body = json.loads(request.post_data or '{}'); who = (body.get('email') or 'a@').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer', 'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}})); return
    who = 'user-' + (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
    if request.method == 'POST':
        rows = json.loads(request.post_data or '[]')
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in rows])); return
    c = int(re.search(r'server_seq=gt\.(\d+)', request.url).group(1)); rows = srv.page(who, c, int(re.search(r'limit=(\d+)', request.url).group(1)))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s)
SYNC = "async (db) => { await db.syncNow(); }"
CENSUS = """async (db) => { const t = await db.idbGetAll('tombstones'); const ops = await db.idbGetAll('oplog');
  return { names: [...db.state.birds.values()].map(b => b.name).sort(), birdsInStore: (await db.idbGetAll('birds')).length, pairs: db.state.pairs.size, races: db.state.raceResults.size,
    health: db.state.healthEvents.size, lofts: [...db.state.lofts.values()].map(l => l.name || '(unnamed)').sort(), tombstones: t.length, birdTombstones: t.filter(x => x.store === 'birds').map(x => x.recordId).sort(),
    deleteOps: ops.filter(o => o.op === 'delete').length, ids: [...db.state.birds.keys()].sort() }; }"""
def census(pg): return run(pg, CENSUS)

def device(b, H, email='r@zajil.test', configured=True):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
    if configured:
        ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};"); ctx.route(f'{STUB}/**', handler)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady')
    if configured: run(pg, "async (db, e) => { await db.signIn(e, 'pw'); }", email)
    return ctx, pg
def open_row(pg, row):
    r = pg.locator(f'[data-row={row}]')
    if r.get_attribute('open') is None: r.locator('summary').click(); pg.wait_for_timeout(300)
def load_large(pg, ROOT):
    pg.goto(ROOT + 'tools/', wait_until='load'); pg.wait_for_selector('[data-testid=tools-list]', timeout=15000); pg.wait_for_timeout(800)
    open_row(pg, 'teaching'); pg.click('[data-testid=load-large]'); pg.wait_for_timeout(4000)
def settle(pg):
    """bounded and NON-RAISING: an operation that never finishes must fail a named check, not die on a wait"""
    try: pg.wait_for_function("() => document.querySelectorAll('[data-testid=toast]').length > 0", timeout=30000)
    except PWTimeout: pass
    pg.wait_for_timeout(2500)
def replace_ui(pg, ROOT, payload, pull_during=True, confirm=True):
    """the import screen, mode «استبدال كامل», through the file picker; returns the confirmation's text ('' if none appeared)"""
    pg.goto(ROOT + 'tools/import/', wait_until='load'); pg.wait_for_selector('[data-testid=import-mode]', timeout=15000); pg.click('[data-testid=import-mode] [data-value=replace]')
    pg.set_input_files('[data-testid=file-input]', files=[{'name': 'file.json', 'mimeType': 'application/json', 'buffer': json.dumps(payload).encode()}]); pg.click('[data-testid=import-file]')
    try: pg.wait_for_selector('[data-testid=dialog]', timeout=8000)
    except PWTimeout: return ''
    text = digits(pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' '))
    pg.click('[data-testid=dialog-confirm]' if confirm else '[data-testid=dialog-cancel]')
    if confirm:
        if pull_during: pg.evaluate("async () => { const db = await window.__zajilDb; db.syncNow(); }")   # launched while the import runs, deliberately not awaited
        settle(pg)
    return text
def restore_ui(pg, ROOT):
    pg.goto(ROOT + 'tools/restore/', wait_until='load'); pg.wait_for_selector('[data-testid=snap-list]', timeout=15000)
    pg.click('[data-testid=snap-row][data-id^=pre-import] [data-testid=snap-restore]'); pg.wait_for_selector('[data-testid=dialog]', timeout=8000)
    text = digits(pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')); listed = pg.locator('[data-testid=dialog] li').count()
    pg.click('[data-testid=dialog-confirm]'); pg.evaluate("async () => { const db = await window.__zajilDb; db.syncNow(); }"); settle(pg)
    return text, listed

FILE = {'format': 'zajil-export', 'version': 1, 'exportedAt': '2026-11-01T00:00:00.000Z', 'tombstones': [], 'pairs': [], 'raceResults': [], 'healthEvents': [], 'media': [],
        'lofts': [{'id': 'loft-file', 'name': 'لوفت الملف', 'location': '', 'statuses': ['breeder', 'race team', 'young bird', 'stock', 'sold', 'lost', 'dead'], 'createdAt': '2026-11-01T00:00:00.000Z', 'updatedAt': '2026-11-01T00:00:00.000Z'}],
        'birds': [{'id': 'bird-file-1', 'name': 'من-الملف', 'sex': 'cock', 'rings': [], 'status': 'stock', 'loftId': 'loft-file', 'notes': [], 'updatedAt': '2026-11-01T00:00:00.000Z', 'createdAt': '2026-11-01T00:00:00.000Z'}]}

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ two devices of one account, both holding the teaching loft (38) and one bird made on D; the server holds all of it ═══
        cd, D = device(b, H); run(D, "async (db) => { await db.Lofts.save({ ...db.currentLoft(), name: 'لوفت القياس' }); await db.saveBird(db.newBird({ name: 'طير-الجهاز', sex: 'cock' })); }")
        load_large(D, ROOT); D.goto(H, wait_until='load'); D.wait_for_function('window.__zajilReady'); run(D, SYNC)
        ce, E = device(b, H); run(E, SYNC)
        d0, e0 = census(D), census(E)
        check('[setup] both devices hold the same 39 birds', len(d0['names']) == 39 and d0['names'] == e0['names'], (len(d0['names']), len(e0['names'])))
        # E edits three teaching birds and pushes: rows that now sit ABOVE D's cursor — the rows that used to bring the set back
        run(E, "async (db) => { for (const n of ['شهاب', 'بشرى', 'الملك']) { const x = [...db.state.birds.values()].find(v => v.name === n); await db.saveBird({ ...x, colour: 'عُدّل على الجهاز الآخر' }, { allowWarnings: true }); } await db.syncNow(); }")
        others = d0['pairs'] + d0['races'] + d0['health'] + len(d0['lofts'])

        # ═══ b1 — THE REPLACE-IMPORT, a pull fired DURING it ═══
        text = replace_ui(D, ROOT, FILE); d1 = census(D)
        check('[replace · confirm] the question states the count removed — the birds and the other records', f'{len(d0["names"])} طيرًا' in text and f'{others} سجلًا' in text, text[:260])
        check('[replace · confirm] …and that it applies on all the person\'s devices', 'كل أجهزتك' in text, text[:260])
        check('[replace] the device holds the file and nothing else, with a pull fired DURING the import', d1['names'] == ['من-الملف'] and d1['birdsInStore'] == 1 and d1['lofts'] == ['لوفت الملف'] and d1['pairs'] == 0 and d1['races'] == 0 and d1['health'] == 0, {k: d1[k] for k in ('names', 'birdsInStore', 'lofts', 'pairs', 'races', 'health')})
        check('[replace] every dropped bird is tombstoned — 39 of them', sorted(d0['ids']) == d1['birdTombstones'], (len(d0['ids']), len(d1['birdTombstones'])))
        run(D, SYNC); d2 = census(D)
        check('[replace · M1 fails here] after ANOTHER pull NOTHING dropped comes back — the three the other device had edited included', d2['names'] == ['من-الملف'] and d2['birdsInStore'] == 1, d2['names'][:6])
        check('[replace] the server holds one live bird, the file\'s', srv.live('user-R', 'birds') == ['من-الملف'], srv.live('user-R', 'birds')[:6])
        run(E, SYNC); e2 = census(E)
        check('[replace · M2 fails here] THE SECOND DEVICE CONVERGES TO THE IMPORT: the file\'s bird, the file\'s loft, nothing else', e2['names'] == ['من-الملف'] and [l for l in e2['lofts'] if l != '(unnamed)'] == ['لوفت الملف'] and e2['pairs'] == 0 and e2['races'] == 0 and e2['health'] == 0, {k: e2[k] for k in ('names', 'lofts', 'pairs', 'races', 'health')})
        # (the second device also keeps its own untouched default loft, «(unnamed)»: a first sync that brings TWO lofts adopts neither — R4, sync.js adoptRemoteLoftIfPristine — and it never travels)
        # a touch from the other device AFTER the replace used to bring a dropped record back for good; now there is nothing left there to touch
        check('[replace] …and no dropped bird is left on the second device for a later edit to send back', not any(n in e2['names'] for n in ('شهاب', 'بشرى', 'الملك', 'سديم')), e2['names'][:6])

        # ═══ b3 — THE RESTORE of the snapshot the replace took (39 birds), a pull fired DURING it ═══
        run(D, "async (db) => { await db.saveBird(db.newBird({ name: 'بعد-النسخة', sex: 'hen' })); await db.syncNow(); }"); run(E, SYNC)
        check('[restore · setup] both devices hold the file\'s bird and one made since', census(D)['names'] == ['بعد-النسخة', 'من-الملف'] and census(E)['names'] == ['بعد-النسخة', 'من-الملف'], (census(D)['names'], census(E)['names']))
        text, listed = restore_ui(D, ROOT); d3 = census(D)
        check('[restore · confirm] the question NAMES what comes back — 39 birds, five by name and the rest counted', 'يعود 39 طيرًا' in text and listed == 6 and 'و34 غيرها' in text and sum(1 for n in d0['names'] if n and n in text) >= 5, (text[:300], listed))
        check('[restore · confirm] …states what it removes (the two birds and the loft added since)', 'يُحذف 3 سجلًا' in text, text[:300])
        check('[restore · confirm] …and that both happen on the other devices', 'أجهزتك الأخرى' in text, text[:300])
        check('[restore] the device holds the snapshot — 39 birds — and neither bird added since, with a pull fired DURING', d3['names'] == d0['names'] and d3['birdsInStore'] == 39, (len(d3['names']), [n for n in ('بعد-النسخة', 'من-الملف') if n in d3['names']]))
        check('[restore] the returned birds are no longer tombstoned here; the two dropped are', len(d3['birdTombstones']) == 2 and not set(d3['birdTombstones']) & set(d0['ids']), d3['birdTombstones'][:4])
        run(D, SYNC); d4 = census(D)
        check('[restore · M1 fails here] after another pull the two dropped birds stay gone and the 39 stay', d4['names'] == d0['names'], [n for n in d4['names'] if n not in d0['names']])
        run(E, SYNC); e4 = census(E)
        check('[restore · M2 fails here] the second device converges to the snapshot: the same 39, the two dropped gone', e4['names'] == d0['names'] and [l for l in e4['lofts'] if l != '(unnamed)'] == [l for l in d4['lofts'] if l != '(unnamed)'] and e4['pairs'] == d0['pairs'], ([n for n in e4['names'] if n not in d0['names']], len(e4['names']), e4['lofts']))
        check('[restore] the server agrees: 39 live birds', srv.live('user-R', 'birds') == d0['names'], len(srv.live('user-R', 'birds')))
        cd.close(); ce.close()

        # ═══ a replace that FAILS half way leaves no deletion standing or queued ═══
        cf, F = device(b, H, 'f@zajil.test'); run(F, "async (db) => { for (const n of ['ف1', 'ف2', 'ف3']) await db.saveBird(db.newBird({ name: n, sex: 'cock' })); await db.syncNow(); }")
        f0 = census(F)
        threw = run(F, """async (db, file) => { const bad = { ...file, birds: [{ ...file.birds[0], notCloneable: () => 1 }] };   // IndexedDB cannot store a function: the put throws AFTER the stores are cleared
            try { await db.importAll(bad, 'replace'); return 'did not throw'; } catch (e) { return String((e && e.name) || e); } }""", FILE)
        f1 = census(F)
        check('[failure · M3 fails here] a replace that throws mid-way leaves NO tombstone and NO delete op for records it did not finish replacing', threw != 'did not throw' and f1['tombstones'] == f0['tombstones'] and f1['deleteOps'] == f0['deleteOps'], (threw, f0['tombstones'], f1['tombstones'], f0['deleteOps'], f1['deleteOps']))
        cf.close()

        # ═══ a device with no sync configured is not told about other devices ═══
        cu, U = device(b, H, configured=False); run(U, "async (db) => { await db.saveBird(db.newBird({ name: 'محلي', sex: 'cock' })); }")
        text = replace_ui(U, ROOT, FILE, pull_during=False)
        check('[unconfigured] the question still states the count, and says nothing of other devices', '1 طيرًا' in text and 'أجهزتك' not in text, text[:200])
        check('[unconfigured] the replace ran', census(U)['names'] == ['من-الملف'], census(U)['names'])
        cu.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
