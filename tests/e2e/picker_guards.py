import os
from playwright.sync_api import sync_playwright
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={'width': 1280, 'height': 900})
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''), wait_until='networkidle'); page.wait_for_timeout(700)
    page.evaluate("""async () => {
        const db = await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(), 'merge');
    }"""); page.reload(); page.wait_for_timeout(1000)

    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/new'); page.wait_for_timeout(700)
    sire = page.locator('.bird-picker input').first

    # FINDING 5: a hen's ring typed into the SIRE picker must explain, not vanish
    sire.fill('JO-2020-07021')  # لمى, a hen
    page.wait_for_timeout(500)
    check('filtered-out match explains itself (no silent empty dropdown)',
          page.locator('.picker-note').count() == 1, 'note missing')
    check('…and does NOT offer to create a clone', page.locator('.picker-create').count() == 0)

    # FINDING 15: Eastern-Arabic digits must be treated as a RING, not a name
    sire.fill('JO-٢٠٩٩-٧٧٧٧'); page.wait_for_timeout(500)
    check('Eastern-Arabic ring offers create', page.locator('.picker-create').count() == 1)
    page.locator('.picker-create').click(); page.wait_for_timeout(700)
    stub = page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const b = db.allBirds().find(x => (x.rings||[]).some(r => (r.raw||'').includes('٧٧٧٧')));
        return b ? { rings: b.rings.length, name: b.name } : null;
    }""")
    check('Eastern ring stored as a RING not a name', stub and stub['rings'] == 1 and not stub['name'],
          str(stub))
    # and typing the SAME ring in Western digits must now find it, not clone it
    sire.fill(''); page.wait_for_timeout(200)
    sire.fill('JO-2099-7777'); page.wait_for_timeout(500)
    check('same ring in Western digits matches the Eastern-entered bird (no clone)',
          page.locator('.picker-create').count() == 0)

    # FINDING 18: re-focusing a filled picker browses instead of showing nothing
    page.locator('.picker-item').first.click(); page.wait_for_timeout(400)
    sire.click(); page.wait_for_timeout(400)
    check('re-focus browses the list (not empty)', page.locator('.picker-item').count() > 0,
          str(page.locator('.picker-item').count()))

    # FINDING 16: typing over a selection must clear the consumer's copy
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/breeding'); page.wait_for_timeout(700)
    page.locator('button', has_text='زوج جديد').click(); page.wait_for_timeout(500)
    s_in = page.locator('.modal .bird-picker input').first
    d_in = page.locator('.modal .bird-picker input').nth(1)
    sire_pick = page.locator('.modal .bird-picker').nth(0).locator('.picker-item')
    dam_pick = page.locator('.modal .bird-picker').nth(1).locator('.picker-item')
    s_in.fill('الملك'); page.wait_for_timeout(400); sire_pick.first.click()
    d_in.fill('سديم'); page.wait_for_timeout(400); dam_pick.first.click()
    page.wait_for_timeout(300)
    # now wipe the sire text without picking anything, then try to save
    s_in.fill('xyz-nonexistent'); page.wait_for_timeout(400)
    pairs_before = page.evaluate("async () => (await import('./js/db.js')).state.pairs.size")
    page.locator('.modal-actions .btn-primary').click(); page.wait_for_timeout(700)
    pairs_after = page.evaluate("async () => (await import('./js/db.js')).state.pairs.size")
    check('cleared sire blocks the save (no stale pair)', pairs_after == pairs_before,
          f'{pairs_before} -> {pairs_after}')
    check('dialog stays open for correction', page.locator('.modal').count() == 1)
    page.keyboard.press('Escape')

    check('zero page errors', not errs, '; '.join(errs[:2]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
