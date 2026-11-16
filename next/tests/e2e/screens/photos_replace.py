"""THE DROPPED BIRD'S PHOTOS (RULED 2026-11-16, P1–P3).

Photos have no server copy and a snapshot carries none, so the copy on the device is the only one.

  P1  A RESTORE is an undo: it deletes no photo. A dropped bird's photos stay on the device and are its photos again
      if the bird returns. The question says so.
  P2  A REPLACE-IMPORT deletes a photo ONLY when its bird is dropped. A photo on a bird that stays is never deleted
      because the file carries no media. (Measured before: a both-birds file with `media: []` deleted every photo on
      the device while the question said «لن يُحذف شيء».)
  P3  The replace question counts the photos that go with the dropped birds and says they cannot be recovered.

Harness build, the net armed. All shapes are CONSTRUCTED: two birds, «قديم» and «جديد», with photos.

    python3 tests/e2e/screens/photos_replace.py
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import os as _o, sys as _s; _h = _o.path.dirname(_o.path.abspath(__file__)); _s.path.insert(0, next(d for d in (_h, _o.path.join(_h, '..'), _o.path.join(_h, '..', 'e2e')) if _o.path.isfile(_o.path.join(d, '_pageerr.py')))); from _pageerr import perr   # TF-12

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'sync'))
from _serve import serve                      # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..'))
from _net import Net                          # noqa: E402  THE NET
from _typography import SCAN                  # noqa: E402
NET = Net()
PAGES = []

passed = failed = 0
def check(n, ok, d=''):
    global passed, failed
    if ok: passed += 1; print(f'  ✓ {n}')
    else: failed += 1; print(f'  ✗ {n}  {d}')

def run(pg, js, *args): return pg.evaluate(f"async (a) => {{ const db = await window.__zajilDb; return ({js})(db, ...a); }}", list(args))
def digits(s): return re.sub(r'[٠-٩]', lambda m: str('٠١٢٣٤٥٦٧٨٩'.index(m.group())), s)
STATE = """async (db) => { const m = await db.idbGetAll('media'); const name = id => (db.getBird(id) || {}).name || '(bird gone)';
  const t = await db.idbGetAll('tombstones'); const ops = await db.listOps();
  return { birds: db.allBirds().map(b => b.name).sort(), media: m.map(x => [x.name, name(x.birdId), x.blob ? x.blob.size : 'NO BLOB']).sort(),
           mediaTombstones: t.filter(x => x.store === 'media').length, mediaDeleteOps: ops.filter(o => o.store === 'media' && o.op === 'delete').length }; }"""
def state(pg): return run(pg, STATE)
BIRD = "async (db, n) => { await new Promise(r => setTimeout(r, 20)); await db.saveBird(db.newBird({ name: n, sex: 'cock' })); }"
PHOTO = "async (db, n, f, body) => { const x = db.allBirds().find(y => y.name === n); await db.addMedia(x.id, 'photo', 'body', f, new Blob([body], { type: 'image/png' })); }"
OLD = ['on-old.png', 'قديم', 2]; NEW = ['on-new.png', 'جديد', 3]; NEW2 = ['on-new-2.png', 'جديد', 4]

def device(b, H):
    ctx = NET.arm(check=check, ctx=b.new_context(viewport={'width': 430, 'height': 900}))
    pg = ctx.new_page(); pg.errs = []; pg.on('pageerror', lambda e, _p=pg: pg.errs.append(perr(e, _p))); PAGES.append(pg)
    pg.goto(H, wait_until='load'); pg.wait_for_function('window.__zajilReady'); return ctx, pg
def both(pg, second_photo=False):
    run(pg, BIRD, 'قديم'); run(pg, PHOTO, 'قديم', 'on-old.png', 'xx'); run(pg, BIRD, 'جديد'); run(pg, PHOTO, 'جديد', 'on-new.png', 'yyy')
    if second_photo: run(pg, PHOTO, 'جديد', 'on-new-2.png', 'zzzz')
def settle(pg):
    try: pg.wait_for_function("() => document.querySelectorAll('[data-testid=toast]').length > 0", timeout=30000)
    except PWTimeout: pass
    pg.wait_for_timeout(1200)
def ask(pg):
    """the open question: its text (Western digits) and the typography scan of it"""
    try: pg.wait_for_selector('[data-testid=dialog]', timeout=8000)
    except PWTimeout: return '', []
    return digits(pg.locator('[data-testid=dialog]').inner_text().replace('\n', ' ')), pg.evaluate(SCAN)
def replace_ui(pg, ROOT, payload):
    pg.goto(ROOT + 'tools/import/', wait_until='load'); pg.wait_for_selector('[data-testid=import-mode]', timeout=15000); pg.click('[data-testid=import-mode] [data-value=replace]')
    pg.set_input_files('[data-testid=file-input]', files=[{'name': 'file.json', 'mimeType': 'application/json', 'buffer': json.dumps(payload).encode()}]); pg.click('[data-testid=import-file]')
    text, typo = ask(pg)
    if text: pg.click('[data-testid=dialog-confirm]'); settle(pg)
    return text, typo
def restore_ui(pg, ROOT, pre):
    pg.goto(ROOT + 'tools/restore/', wait_until='load'); pg.wait_for_selector('[data-testid=snap-list]', timeout=15000); pg.wait_for_timeout(500)
    pg.click(f"[data-testid=snap-row]{'[data-id^=pre-import]' if pre else ':not([data-id^=pre-import])'} [data-testid=snap-restore]")
    text, typo = ask(pg)
    if text: pg.click('[data-testid=dialog-confirm]'); settle(pg)
    return text, typo
LOST = 'عدد الصور والوثائق التي ستُحذف مع هذه الطيور:'; NEVER = 'لا يمكن استرجاعها'; NOTHING = 'لن يُحذف شيء'

srvp, H = serve(); ROOT = H.replace('test-harness/', '')
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ═══ P2 — a file with BOTH birds and NO media: nothing is deleted, and that now includes the photos ═══
        c1, A = device(b, H); both(A)
        f = run(A, "async (db) => await db.exportAll({ includeMedia: false })")
        check('the file under test holds both birds and no media', len(f['birds']) == 2 and f['media'] == [], (len(f['birds']), len(f['media'])))
        q, typo = replace_ui(A, ROOT, f); a = state(A)
        check('[P2 · M-p2 fails here] a replace from a both-birds, no-media file: BOTH photos are still on the device, with their bytes', a['media'] == [NEW, OLD], a)
        check('[P2 · M-p2 fails here] …no photo was tombstoned and no deletion of one is queued for the other devices', a['mediaTombstones'] == 0 and a['mediaDeleteOps'] == 0, a)
        check('[P3] …and the question said «لن يُحذف شيء», which is now true of the photos too; it counted no photo', NOTHING in q and LOST not in q, q)
        check('[typography] that question is drawn in a face that has Arabic', bool(q) and not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        c1.close()

        # ═══ P2 + P3 — a file that DROPS «جديد» (which has two photos) and carries no media ═══
        c2, B = device(b, H); both(B, second_photo=True)
        f = run(B, "async (db) => { const e = await db.exportAll({ includeMedia: false }); e.birds = e.birds.filter(x => x.name === 'قديم'); return e; }")
        q, typo = replace_ui(B, ROOT, f); s = state(B)
        check('[P3 · M-count fails here] the question counts the photos that go with the dropped bird — 2 — and says they cannot be recovered', f'{LOST} 2.' in q and NEVER in q, q)
        check('[P3] …it names 1 bird, and never says «لن يُحذف شيء»', 'سيُحذف من السجلّ 1 طيرًا' in q and NOTHING not in q, q)
        check('[typography] the question with the photo count is drawn in a face that has Arabic', bool(q) and not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        check('[P2 · M-cascade fails here] the dropped bird\'s two photos are deleted with it, each tombstoned and queued as a deletion', s['birds'] == ['قديم'] and s['mediaTombstones'] == 2 and s['mediaDeleteOps'] == 2 and [m for m in s['media'] if m[0].startswith('on-new')] == [], s)
        check('[P2 · M-p2 fails here] …and the photo of the bird that STAYS is kept, bytes and all, though the file carried no media', s['media'] == [OLD], s)
        # what «لا يمكن استرجاعها» means, measured: the rollback snapshot brings the bird back without them
        q2, _ = restore_ui(B, ROOT, pre=True); s2 = state(B)
        check('[P3] the question told the truth: restoring the pre-import snapshot returns «جديد» WITHOUT its photos', s2['birds'] == ['جديد', 'قديم'] and s2['media'] == [OLD], s2)
        c2.close()

        # ═══ P2 — a full export WITH media, taken when only «قديم» existed ═══
        c3, C = device(b, H); run(C, BIRD, 'قديم'); run(C, PHOTO, 'قديم', 'on-old.png', 'xx')
        f = run(C, "async (db) => await db.exportAll()"); run(C, BIRD, 'جديد'); run(C, PHOTO, 'جديد', 'on-new.png', 'yyy')
        q, _ = replace_ui(C, ROOT, f); s = state(C)
        check('[P2] a replace from a file WITH media: the dropped bird\'s photo goes (counted as 1 in the question), the file\'s photo is here with its bytes', f'{LOST} 1.' in q and s['media'] == [OLD] and s['mediaTombstones'] == 1 and s['mediaDeleteOps'] == 1, (q, s))
        c3.close()

        # ═══ P1 — a RESTORE deletes no photo, and a returning bird has its photos again ═══
        c4, D = device(b, H); run(D, BIRD, 'قديم'); run(D, PHOTO, 'قديم', 'on-old.png', 'xx')
        run(D, "async (db) => { await new Promise(r => setTimeout(r, 20)); await db.autoBackup(); }"); run(D, BIRD, 'جديد'); run(D, PHOTO, 'جديد', 'on-new.png', 'yyy')
        q, typo = restore_ui(D, ROOT, pre=False); s = state(D)
        check('[P1 · M-p1 fails here] a restore to a point before «جديد»: the bird goes, and NO photo is deleted — its photo stays on the device, with its bytes', s['birds'] == ['قديم'] and s['media'] == [['on-new.png', '(bird gone)', 3], OLD] and s['mediaTombstones'] == 0 and s['mediaDeleteOps'] == 0, s)
        check('[P1 · wording] the question says what is true: photos stay on this device, and a removed bird\'s photos return if it does', 'الصور والوثائق تبقى على هذا الجهاز' in q and 'تعود إليه إن عاد' in q and 'تبقى كما هي' not in q, q)
        check('[P3] …and it counts no photo as lost, because none is', LOST not in q and NEVER not in q, q)
        check('[typography] the restore question is drawn in a face that has Arabic', bool(q) and not typo, [(x['why'], x['face'], x['text']) for x in typo][:3])
        q, _ = restore_ui(D, ROOT, pre=True); s = state(D)
        mine = run(D, "async (db) => { const x = db.allBirds().find(y => y.name === 'جديد'); return x ? (await db.mediaForBird(x.id)).map(m => [m.name, m.blob ? m.blob.size : 'NO BLOB']) : null; }")
        check('[P1 · M-p1 fails here] undoing the restore: «جديد» returns and its photo is ITS photo again, with its bytes', s['birds'] == ['جديد', 'قديم'] and mine == [['on-new.png', 3]] and s['media'] == [NEW, OLD], (s, mine))
        c4.close()

        check(f'zero page errors across {len(PAGES)} devices', not any(p.errs for p in PAGES), [e[:160] for p in PAGES for e in p.errs][:3])
        NET.assert_empty(check)
        b.close()
finally:
    srvp.terminate()

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
