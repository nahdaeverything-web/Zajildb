#!/usr/bin/env python3
"""Two accounts, one device — the account collision (ROOT-FINDINGS RF-13, RULED 2026-10-05).

THE DEFECT, measured on the deployed build before anything changed: signIn() never compared the
incoming user with the owner of the data already on the device. A second account signing in
inherited the loft on screen, had the first account's unpushed edits pushed into ITS account,
and either skipped its own older rows (the pull resumed from the first account's cursor) or
merged the two lofts on the device — and nothing was shown to either person.

THE RULING. The owning user id is recorded on the device and survives sign-out. On sign-in it
is compared: the same account proceeds exactly as before; a different one STOPS before any
sync — no merge, no push, nothing silently cleared — and is put a decision: export what is
here, or clear it and come in as the new account. A device with no recorded owner adopts the
first account that signs in.

RULED 2026-10-07, closing the limit: a device with no record and no session still names its
owner through its op log — the most recent op made while signed in carries that account's id
— and that owner is compared exactly as the recorded one. Adoption is now ONLY for a device
that was never signed in, the one case with nothing to protect. A gate that forces sign-in
would have turned the old "adopt" from an incidental risk into a compulsory one.

THE SERVER HERE models the real table (docs/SYNC-DESIGN.md:84-152): rows are owner-only, and
ONE global sequence numbers every account's rows. Both matter — the first is what makes a push
under the wrong session land in the wrong loft, the second is why one account's cursor is
meaningless for another's rows. "Unchanged" below is a digest of an account's rows, not a count.

Binds to data-testid only. Provisions its own server (R6)."""
import hashlib
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402

passed = failed = 0


def check(n, ok, d=''):
    global passed, failed
    passed += bool(ok); failed += (not ok); print(f"  {'✓' if ok else '✗'} {n}{('  ' + str(d)) if d else ''}")


STUB = 'https://stub.example.test'


class Server:
    """sync_records, with its two properties that matter here: owner-only rows, one sequence."""
    def __init__(self):
        self.rows = {}; self.seq = 0; self.log = []

    def upsert(self, owner, incoming):
        self.seq += 1
        row = dict(incoming, server_seq=self.seq, owner='user-' + owner)
        self.rows[(owner, incoming['store'], incoming['record_id'])] = row
        return row

    def page(self, owner, cursor, limit):
        return sorted((r for (o, _, _), r in self.rows.items() if o == owner and r['server_seq'] > cursor),
                      key=lambda r: r['server_seq'])[:limit]

    def names(self, owner, store='birds'):
        return sorted(r['data'].get('name') for (o, s, _), r in self.rows.items() if o == owner and s == store)

    def digest(self, owner):
        rows = sorted((s, rid, r['server_seq'], json.dumps(r['data'], sort_keys=True, ensure_ascii=False))
                      for (o, s, rid), r in self.rows.items() if o == owner)
        return f"{len(rows)} rows {hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()[:12]}"

    def calls(self, who, since=0):
        return [(m, d) for w, m, d in self.log[since:] if w == who]


srv = Server()


def handler(route, request):
    url = request.url
    if '/auth/v1/token' in url:
        body = json.loads(request.post_data or '{}')
        who = (body.get('email') or '').split('@')[0].upper() or (body.get('refresh_token') or '').replace('REFRESH-', '')
        srv.log.append((who, 'TOKEN', ''))
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'access_token': 'ACCESS-' + who, 'refresh_token': 'REFRESH-' + who, 'token_type': 'bearer',
            'expires_in': 3600, 'user': {'id': 'user-' + who, 'email': who.lower() + '@zajil.test'}}))
        return
    who = (request.headers.get('authorization') or '').replace('Bearer ACCESS-', '')
    if request.method == 'POST':
        body = json.loads(request.post_data or '[]')
        srv.log.append((who, 'POST', sorted((r.get('data') or {}).get('name') or r['store'] for r in body)))
        route.fulfill(status=200, content_type='application/json', body=json.dumps([srv.upsert(who, r) for r in body]))
        return
    cursor = int(re.search(r'server_seq=gt\.(\d+)', url).group(1)); limit = int(re.search(r'limit=(\d+)', url).group(1))
    rows = srv.page(who, cursor, limit)
    srv.log.append((who, 'GET', f'cursor>{cursor}: {len(rows)}'))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))


RUN = "async (a) => { const db = await window.__zajilDb; return (%s)(db, a); }"


def run(pg, fn, arg=None):
    return pg.evaluate(RUN % fn, arg)


# raw IndexedDB — what is on the device, not what a mirror in memory believes
CENSUS = """async () => {
  const idb = await new Promise((res, rej) => { const r = indexedDB.open('zajil'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
  const out = {}; for (const n of [...idb.objectStoreNames]) out[n] = await new Promise((res) => { const q = idb.transaction(n).objectStore(n).getAll(); q.onsuccess = () => res(q.result); });
  idb.close(); const st = {}; for (const r of out.settings) st[r.key] = r.value;
  const acked = st.lastAckedSeq || 0;
  return { counts: Object.fromEntries(Object.entries(out).filter(([k]) => k !== 'settings').map(([k, v]) => [k, v.length])),
           birds: out.birds.map(b => b.name).sort(), lofts: out.lofts.map(l => l.name || '(unnamed)').sort(),
           unpushed: out.oplog.filter(o => o.seq > acked).map(o => (o.record && o.record.name) || o.store).sort(),
           signedIn: !!st.authRefreshToken, account: st.authEmail || null, tokens: ['authAccessToken', 'authRefreshToken'].filter(k => st[k]).length,
           owner: st.dataOwnerId || null, hint: st.dataOwnerHint || null, cursor: st.syncCursor || 0, everSynced: !!st.lastSyncAt,
           deviceId: st.deviceId, coiDepth: st.coiDepth || null, lang: st.lang || null }; }"""


def census(pg):
    return pg.evaluate(CENSUS)


def device(b, downloads=False):
    ctx = b.new_context(viewport={'width': 430, 'height': 900}, accept_downloads=downloads)
    ctx.add_init_script(f"globalThis.ZAJIL_SYNC_CONFIG = {{ url: '{STUB}', publishableKey: 'sb_publishable_test' }};")
    ctx.route(f'{STUB}/**', handler)
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e)))
    # the harness page, not a screen: with no session, every screen is the sign-in gate now
    pg.goto(HARNESS, wait_until='load'); pg.wait_for_timeout(600); pg.evaluate("async () => { await window.__zajilReady; }")
    return ctx, pg


def birds(pg, names):
    return run(pg, """async (db, names) => { for (const n of names) await db.saveBird(db.newBird({ name: n, sex: 'cock', loftId: db.currentLoft().id })); }""", names)


def name_loft(pg, name):
    return run(pg, "async (db, n) => { await db.Lofts.save({ ...db.currentLoft(), name: n }); }", name)


def submit(pg, email):
    """The sign-in screen itself: the only caller of signIn() the app has."""
    pg.goto(ROOT + 'sign-in/', wait_until='load'); pg.wait_for_selector('[data-testid=signin-form]', timeout=10000)
    pg.fill('[data-testid=f-email]', email); pg.fill('[data-testid=f-password]', 'pw'); pg.click('[data-testid=signin-submit]')


def settled(pg, ms=2500):
    """Either the decision is up or the screen has left for /tools — whichever this build does."""
    try:
        pg.wait_for_function("() => document.querySelector('[data-testid=dialog]') || location.pathname.endsWith('/tools/')", timeout=15000)
    except Exception:
        pass
    pg.wait_for_timeout(ms)


def dialog(pg):
    d = pg.locator('[data-testid=dialog]')
    return ' / '.join(x.strip() for x in d.inner_text().split('\n') if x.strip()) if d.count() else ''


srvp, HARNESS = serve()
ROOT = HARNESS.replace('test-harness/', '')

try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ── account B has a loft of its own on the server, from a device of its own ──
        cb, pb = device(b)
        name_loft(pb, 'لوفت ب'); birds(pb, ['ب-1', 'ب-2'])
        run(pb, "async (db) => { await db.signIn('b@zajil.test', 'pw'); await db.syncNow(); }")
        cb.close()
        check('the stage is set: account B holds a loft and two birds on the server',
              srv.names('B') == ['ب-1', 'ب-2'] and srv.names('B', 'lofts') == ['لوفت ب'], srv.digest('B'))

        # ══ 1. A DEVICE WITH NO RECORDED OWNER ADOPTS THE FIRST ACCOUNT THAT SIGNS IN ═════
        ctx, pg = device(b, downloads=True)
        name_loft(pg, 'لوفت أ'); birds(pg, ['أ-1', 'أ-2', 'أ-3'])
        run(pg, "async (db) => { await db.setSetting('coiDepth', 7); }")
        c = census(pg)
        check('[adoption] a device nobody has signed in on records no owner', c['owner'] is None and not c['signedIn'])
        mark = len(srv.log); submit(pg, 'a@zajil.test'); settled(pg)
        c = census(pg)
        check('[adoption] the first account signs in with NO question asked — grandfathering, not a collision',
              pg.locator('[data-testid=dialog]').count() == 0 and pg.url.endswith('/tools/') and c['account'] == 'a@zajil.test', pg.url)
        check('[adoption] …and its first sync runs exactly as before: the local loft goes up, then the pull',
              srv.calls('A', mark) == [('TOKEN', ''), ('POST', ['أ-1', 'أ-2', 'أ-3', 'لوفت أ']), ('GET', 'cursor>0: 4')], str(srv.calls('A', mark)))
        check('[adoption] …and the device now records whose data it holds — the id, and a MASKED hint, never the address',
              c['owner'] == 'user-A' and c['hint'] == 'a•••@zajil.test', f"{c['owner']} / {c['hint']}")

        # two more birds that never reach the server, then A signs out
        birds(pg, ['أ-4 غير مرفوع', 'أ-5 غير مرفوع'])
        pg.goto(ROOT + 'tools/', wait_until='load'); pg.wait_for_selector('[data-testid=sign-out]', timeout=10000)
        pg.click('[data-testid=sign-out]'); pg.wait_for_selector('[data-testid=dialog]'); pg.click('[data-testid=dialog-confirm]')
        pg.wait_for_selector('[data-testid=gate]', state='attached', timeout=10000); pg.wait_for_timeout(400)   # the gate: there is data and no session
        before = census(pg); a0, b0 = srv.digest('A'), srv.digest('B')
        check('[ownership survives sign-out] the session is gone and the owner record is not',
              not before['signedIn'] and before['tokens'] == 0 and before['owner'] == 'user-A' and before['hint'] == 'a•••@zajil.test',
              f"signedIn={before['signedIn']} owner={before['owner']}")
        check('…with the loft and its two unpushed edits still on the device, as sign-out promises',
              len(before['birds']) == 5 and before['unpushed'] == ['أ-4 غير مرفوع', 'أ-5 غير مرفوع'], str(before['unpushed']))

        # ══ 2. THE COLLISION: A DIFFERENT ACCOUNT SIGNS IN ════════════════════════════════
        mark = len(srv.log); submit(pg, 'b@zajil.test'); settled(pg)
        now = census(pg)
        check('[THE COLLISION] the second account is STOPPED: a decision is on screen and the app has not moved on',
              pg.locator('[data-testid=dialog]').count() == 1 and pg.url.endswith('/sign-in/'), f"{pg.url} · dialog: {dialog(pg)[:60] or 'NONE'}")
        check('[THE COLLISION] …BEFORE ANY SYNC: the only thing asked of the server was the token — no pull, no push',
              srv.calls('B', mark) == [('TOKEN', '')], str(srv.calls('B', mark)))
        check("[THE COLLISION] …sync_records for account B is UNCHANGED",
              srv.digest('B') == b0, f"{b0}  ->  {srv.digest('B')}")
        check("[THE COLLISION] …and so is account A's", srv.digest('A') == a0, f"{a0}  ->  {srv.digest('A')}")
        check('[THE COLLISION] …no session was stored: the device is still signed out and holds no token',
              not now['signedIn'] and now['tokens'] == 0 and now['account'] is None, f"signedIn={now['signedIn']} tokens={now['tokens']} account={now['account']}")
        check('[THE COLLISION] …nothing was merged and nothing was cleared: the device is byte for byte what it was',
              now == before, json.dumps({k: (before[k], now[k]) for k in before if before[k] != now[k]}, ensure_ascii=False)[:260])
        d = dialog(pg)
        check('[THE DECISION] the previous account is identified only as much as is safe — masked, never the address',
              'a•••@zajil.test' in d and 'a@zajil.test' not in d, d[:110])
        check('[THE DECISION] …and exactly two ways forward are offered: export what is here, or clear it and come in',
              pg.locator('[data-testid=dialog-alt]').inner_text().strip() == 'تصدير البيانات'
              and pg.locator('[data-testid=dialog-confirm]').inner_text().strip() == 'مسح والدخول'
              and pg.locator('[data-testid=dialog-cancel]').count() == 1 if pg.locator('[data-testid=dialog-alt]').count() else False, d[-80:])

        # ── cancel: not signed in, nothing touched ──
        if pg.locator('[data-testid=dialog]').count():
            pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(500)
        check('[CANCEL] backing out leaves the device signed out, untouched, and the screen saying why',
              census(pg) == before and pg.locator('[data-testid=msg-owner]').count() == 1 and pg.url.endswith('/sign-in/'),
              pg.locator('[data-testid=msg-owner]').inner_text().replace('\n', ' ')[:70] if pg.locator('[data-testid=msg-owner]').count() else 'no message')
        check('[CANCEL] …and signing in is not possible past that point: trying again meets the same decision',
              (pg.click('[data-testid=signin-submit]') or True) and pg.locator('[data-testid=dialog]').wait_for(timeout=8000) is None
              and not census(pg)['signedIn'] if pg.locator('[data-testid=signin-submit]').count() and pg.locator('[data-testid=msg-owner]').count() else False)

        # ── export: a copy in hand, and the decision still stands ──
        exported = None
        if pg.locator('[data-testid=dialog-alt]').count():
            with pg.expect_download(timeout=20000) as dl:
                pg.click('[data-testid=dialog-alt]')
            exported = json.loads(open(dl.value.path(), encoding='utf-8').read()); pg.wait_for_timeout(600)
        check('[EXPORT] «تصدير البيانات» hands over the whole loft that is on the device',
              bool(exported) and sorted(x['name'] for x in exported['birds']) == before['birds'] and [l['name'] for l in exported['lofts']] == ['لوفت أ'],
              f"{len(exported['birds'])} birds, loft {[l['name'] for l in exported['lofts']]}" if exported else 'no download')
        check('[EXPORT] …the file carries no session and no owner record — settings never travel',
              bool(exported) and not any(k in json.dumps(exported) for k in ('dataOwner', 'authAccessToken', 'authRefreshToken', 'user-A')))
        check('[EXPORT] …and the decision is asked again: a copy in hand does not settle whose device this is',
              pg.locator('[data-testid=dialog]').count() == 1 and census(pg) == before and srv.calls('B', mark).count(('TOKEN', '')) == len(srv.calls('B', mark)),
              str(srv.calls('B', mark)))

        # ── clear: asked twice, and refusing the second time clears nothing ──
        if pg.locator('[data-testid=dialog-confirm]').count():
            pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(500)
        d2 = dialog(pg)
        check('[CLEAR] never silent: a second confirmation names what goes, in the danger voice',
              'مسح بيانات هذا الجهاز نهائيًا' in d2 and '5' in d2 and 'لا يمكن التراجع' in d2, d2[:120])
        if pg.locator('[data-testid=dialog-cancel]').count():
            pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(500)
        check('[CLEAR] …and declining it clears nothing and returns to the decision',
              census(pg) == before and pg.locator('[data-testid=dialog-alt]').count() == 1)
        mark2 = len(srv.log)
        if pg.locator('[data-testid=dialog-alt]').count():
            pg.click('[data-testid=dialog-confirm]'); pg.wait_for_timeout(400); pg.click('[data-testid=dialog-confirm]')
            pg.wait_for_url(re.compile(r'/tools/$'), timeout=20000); pg.wait_for_timeout(1200)
        after = census(pg)
        check('[CLEAR] chosen twice: the device is now account B\'s, and holds B\'s own loft — pulled from zero',
              after['account'] == 'b@zajil.test' and after['birds'] == ['ب-1', 'ب-2'] and after['lofts'] == ['لوفت ب'],
              f"{after['account']} · {after['birds']} · {after['lofts']}")
        check("[CLEAR] …none of A's records, edits, snapshots or tombstones is left on it",
              not any(n.startswith('أ') for n in after['birds'] + after['unpushed']) and after['counts']['backups'] == 0
              and after['counts']['tombstones'] == 0 and after['counts']['media'] == 0, json.dumps(after['counts']))
        check("[CLEAR] …the first sync as B pulled, and pushed NOTHING of A's",
              ('GET', 'cursor>0: 3') in srv.calls('B', mark2) and not any(m == 'POST' and any(str(n).startswith('أ') or n == 'لوفت أ' for n in d_) for m, d_ in srv.calls('B', mark2)),
              str(srv.calls('B', mark2)))
        check('[CLEAR] …sync_records for account B is STILL unchanged, and account A\'s too — nothing was deleted from the server',
              srv.digest('B') == b0 and srv.digest('A') == a0, f"B {srv.digest('B')} · A {srv.digest('A')}")
        check('[CLEAR] …ownership moved with the data, and only then',
              after['owner'] == 'user-B' and after['hint'] == 'b•••@zajil.test', f"{after['owner']} / {after['hint']}")
        check('[CLEAR] …and what is the DEVICE\'s stayed: its identity and its preferences',
              after['deviceId'] == before['deviceId'] and after['coiDepth'] == 7, f"deviceId kept={after['deviceId'] == before['deviceId']} coiDepth={after['coiDepth']}")
        check('zero page errors through the collision', not pg.errs, '; '.join(pg.errs[:2]))
        ctx.close()

        # ══ 3. THE SAME ACCOUNT SIGNING IN AGAIN IS UNAFFECTED ════════════════════════════
        ctx, pg = device(b)
        name_loft(pg, 'لوفت ج'); birds(pg, ['ج-1'])
        run(pg, "async (db) => { await db.signIn('c@zajil.test', 'pw'); await db.syncNow(); }")
        birds(pg, ['ج-2 غير مرفوع'])
        run(pg, "async (db) => { await db.signOut(); }")
        before = census(pg); mark = len(srv.log); submit(pg, 'c@zajil.test'); settled(pg)
        after = census(pg)
        check('[SAME ACCOUNT] signing in again asks nothing and goes straight through',
              pg.locator('[data-testid=dialog]').count() == 0 and pg.url.endswith('/tools/') and after['account'] == 'c@zajil.test', pg.url)
        check('[SAME ACCOUNT] …exactly as before the fix: pull from its own cursor, then push what was waiting',
              srv.calls('C', mark) == [('TOKEN', ''), ('GET', f"cursor>{before['cursor']}: 0"), ('POST', ['ج-2 غير مرفوع'])], str(srv.calls('C', mark)))
        check('[SAME ACCOUNT] …with every record still there and the owner unchanged',
              after['birds'] == before['birds'] and after['owner'] == 'user-C' and srv.names('C') == ['ج-1', 'ج-2 غير مرفوع'], str(after['birds']))
        ctx.close()

        # ══ 4. GRANDFATHERING — the devices that exist today have no owner record ═════════
        FORGET = "async (db) => { await db.setSetting('dataOwnerId', null); await db.setSetting('dataOwnerHint', null); }"

        # (a) signed in since before the record existed, then signs out
        ctx, pg = device(b)
        name_loft(pg, 'لوفت د'); birds(pg, ['د-1'])
        run(pg, "async (db) => { await db.signIn('d@zajil.test', 'pw'); await db.syncNow(); }"); run(pg, FORGET)
        check('[grandfathered] a device signed in since before the record existed has none', census(pg)['owner'] is None and census(pg)['signedIn'])
        run(pg, "async (db) => { await db.signOut(); }")
        c = census(pg)
        check('[grandfathered] …and signing out writes it down first — the last moment the device knows whose data it holds',
              c['owner'] == 'user-D' and c['hint'] == 'd•••@zajil.test' and not c['signedIn'], f"{c['owner']} / {c['hint']}")
        b0 = srv.digest('B'); mark = len(srv.log); submit(pg, 'b@zajil.test'); settled(pg)
        check('[grandfathered] …so the next account is stopped like any other', pg.locator('[data-testid=dialog]').count() == 1
              and srv.calls('B', mark) == [('TOKEN', '')] and srv.digest('B') == b0, str(srv.calls('B', mark)))
        ctx.close()

        # (b) still signed in, and someone signs in over the top without signing out
        ctx, pg = device(b)
        name_loft(pg, 'لوفت هـ'); birds(pg, ['هـ-1'])
        run(pg, "async (db) => { await db.signIn('e@zajil.test', 'pw'); await db.syncNow(); }"); run(pg, FORGET)
        b0 = srv.digest('B'); mark = len(srv.log); submit(pg, 'b@zajil.test'); settled(pg)
        c = census(pg)
        check('[grandfathered] signing in OVER a live session of another account is stopped too — the session names the owner',
              pg.locator('[data-testid=dialog]').count() == 1 and srv.calls('B', mark) == [('TOKEN', '')] and srv.digest('B') == b0, str(srv.calls('B', mark)))
        check('[grandfathered] …and the session that was there is left exactly as it was',
              c['signedIn'] and c['account'] == 'e@zajil.test' and c['birds'] == ['هـ-1'], f"{c['account']} · {c['birds']}")
        ctx.close()

        # (c) signed in since before the record existed: the next sync establishes it
        ctx, pg = device(b)
        birds(pg, ['و-1']); run(pg, "async (db) => { await db.signIn('f@zajil.test', 'pw'); await db.syncNow(); }"); run(pg, FORGET)
        run(pg, "async (db) => { await db.syncNow(); }")
        check('[grandfathered] a sync establishes ownership for a session older than the record', census(pg)['owner'] == 'user-F', str(census(pg)['owner']))
        ctx.close()

        # (d) THE LIMIT, CLOSED (RULED 2026-10-07): signed OUT before the record existed — no session, no
        #     record — and the op log still names the owner. Proven on the legacy device as measured:
        #     C synced, left one edit unpushed, signed out; B has a loft of its own on the server.
        ctx, pg = device(b)
        name_loft(pg, 'لوفت ج'); birds(pg, ['ج-1', 'ج-2'])
        run(pg, "async (db) => { await db.signIn('g@zajil.test', 'pw'); await db.syncNow(); }"); birds(pg, ['ج-1-edit']); run(pg, "async (db) => { await db.signOut(); }"); run(pg, FORGET)
        before = census(pg); b0, g0 = srv.digest('B'), srv.digest('G')
        check('[CLOSED LIMIT] the legacy device: no session, no owner record, one edit still unpushed',
              not before['signedIn'] and before['owner'] is None and before['unpushed'] == ['ج-1-edit'], f"owner={before['owner']} unpushed={before['unpushed']}")
        mark = len(srv.log); submit(pg, 'b@zajil.test'); settled(pg)
        after = census(pg); d = dialog(pg)
        check('[CLOSED LIMIT] B signing in is STOPPED — the op log named the owner',
              pg.locator('[data-testid=dialog]').count() == 1 and pg.url.endswith('/sign-in/') and srv.calls('B', mark) == [('TOKEN', '')],
              f"{pg.url} · calls {srv.calls('B', mark)} · dialog: {d[:50] or 'NONE'}")
        check("[CLOSED LIMIT] …C's edit stays local, and nothing on the device changed — not even an owner record",
              after == before and after['unpushed'] == ['ج-1-edit'] and after['owner'] is None,
              json.dumps({k: (before[k], after[k]) for k in before if before[k] != after[k]}, ensure_ascii=False)[:200])
        check('[CLOSED LIMIT] …server state for BOTH accounts unchanged, by digest',
              srv.digest('B') == b0 and srv.digest('G') == g0, f"B {b0} -> {srv.digest('B')} · G {g0} -> {srv.digest('G')}")
        check('[CLOSED LIMIT] …and the previous account is named only as what the log knows — no address at all',
              'حساب آخر سبق استخدامه على هذا الجهاز' in d and '@' not in d, d[:100])
        pg.click('[data-testid=dialog-cancel]'); pg.wait_for_timeout(300)
        mark = len(srv.log); submit(pg, 'g@zajil.test'); settled(pg); after = census(pg)
        check('[CLOSED LIMIT] …while the account the log names goes straight through, and its edit goes up',
              pg.locator('[data-testid=dialog]').count() == 0 and after['account'] == 'g@zajil.test' and after['owner'] == 'user-G'
              and ('POST', ['ج-1-edit']) in srv.calls('G', mark), f"{after['account']} / {after['owner']} / {srv.calls('G', mark)}")
        ctx.close()

        # (e) the same, after the log has been PRUNED: the forensic tail (OPLOG_KEEP) still carries the id
        ctx, pg = device(b)
        name_loft(pg, 'لوفت ط'); birds(pg, [f'ط-{i}' for i in range(300)])
        run(pg, "async (db) => { await db.signIn('t@zajil.test', 'pw'); await db.syncNow(); }"); birds(pg, [f'ط-{i}' for i in range(300, 620)])
        run(pg, "async (db) => { await db.syncNow(); await db.signOut(); }"); run(pg, FORGET)
        actors = run(pg, "async (db) => { const a = {}; for (const o of await db.listOps()) a[o.actorId || 'null'] = (a[o.actorId || 'null'] || 0) + 1; return a; }")
        check('[CLOSED LIMIT] a long-synced device, pruned to its tail, still names its owner in every remaining op',
              actors == {'user-T': 500}, str(actors))
        b0 = srv.digest('B'); mark = len(srv.log); submit(pg, 'b@zajil.test'); settled(pg)
        check('[CLOSED LIMIT] …so B is stopped there too', pg.locator('[data-testid=dialog]').count() == 1 and srv.calls('B', mark) == [('TOKEN', '')] and srv.digest('B') == b0,
              str(srv.calls('B', mark)))
        ctx.close()

        # (f) WHAT STILL ADOPTS — and the only thing that does: a device never signed in. Its ops all carry null.
        ctx, pg = device(b)
        name_loft(pg, 'لوفت ك'); birds(pg, ['ك-1'])
        actors = run(pg, "async (db) => { const a = {}; for (const o of await db.listOps()) a[o.actorId || 'null'] = (a[o.actorId || 'null'] || 0) + 1; return a; }")
        mark = len(srv.log); submit(pg, 'h@zajil.test'); settled(pg); c = census(pg)
        check('[NEVER SYNCED] a device never signed in carries no account in its log, and adopts the first account — nothing to protect',
              actors == {'null': 2} and pg.locator('[data-testid=dialog]').count() == 0 and c['account'] == 'h@zajil.test' and c['owner'] == 'user-H',
              f"{actors} · {c['account']} / {c['owner']}")
        ctx.close()
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
