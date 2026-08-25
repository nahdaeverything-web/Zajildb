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
    before = page.evaluate("async () => (await import('./js/db.js')).allBirds().length")

    # reproduce the reported flow: new pair → pick لمى → tap the field again ×5
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/breeding'); page.wait_for_timeout(700)
    page.locator('button', has_text='زوج جديد').click(); page.wait_for_timeout(500)
    dam = page.locator('.modal .bird-picker input').nth(1)
    dam_items = page.locator('.modal .bird-picker').nth(1).locator('.picker-item')
    dam.click(); dam.fill('لمى'); page.wait_for_timeout(400)
    dam_items.first.click(); page.wait_for_timeout(400)
    check('dam selected', 'لمى' in dam.input_value())
    for i in range(5):
        dam.click(); page.wait_for_timeout(250)
        n = page.locator('.modal .bird-picker').nth(1).locator('.picker-create').count()
        if n: check(f'create row wrongly offered on tap {i+1}', False, 'STILL BUGGY'); break
        page.keyboard.press('Escape') if False else None
    else:
        check('no create row when a bird is already selected (×5 taps)', True)
    # exact ring typed by hand must not offer create either
    dam.fill('JO-2020-07021'); page.wait_for_timeout(400)
    check('no create row for an existing ring', page.locator('.modal .bird-picker').nth(1).locator('.picker-create').count() == 0)
    dam.fill('لمى'); page.wait_for_timeout(400)
    check('no create row for an existing name', page.locator('.modal .bird-picker').nth(1).locator('.picker-create').count() == 0)
    # a genuinely new bird still CAN be created
    dam.fill('JO-2099-55555'); page.wait_for_timeout(400)
    dam_create = page.locator('.modal .bird-picker').nth(1).locator('.picker-create')
    check('create row DOES appear for a new ring', dam_create.count() == 1)
    dam_create.click(); page.wait_for_timeout(700)
    after = page.evaluate("async () => (await import('./js/db.js')).allBirds().length")
    check('exactly one bird created', after == before + 1, f'{before} -> {after}')
    page.keyboard.press('Escape'); page.wait_for_timeout(300)

    # duplicate finder: seed a real duplicate, confirm it is found, then delete it
    page.evaluate("""async () => {
        const db = await import('./js/db.js');
        const src = db.getBird('g1-lama');
        // deliberately seeding a duplicate ring to exercise the finder, so the
        // warning is acknowledged explicitly — saveBird refuses it otherwise,
        // which is the write boundary working as intended
        await db.saveBird(db.newBird({ name: src.name + ' (نسخة)', sex: 'hen', rings: JSON.parse(JSON.stringify(src.rings)) }), { allowWarnings: true });
    }""")
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/tools'); page.reload(); page.wait_for_timeout(1200)
    check('duplicate finder lists the clone', page.locator('.dup-group').count() == 1,
          str(page.locator('.dup-group').count()))
    txt = page.locator('.dup-group').inner_text()
    check('shows link status per copy', 'بدون روابط معروفة' in txt, txt[:120])
    page.screenshot(path='/tmp/claude-1000/-home-samir/8788c756-998b-4a82-9d7a-2ebbad47d910/scratchpad/dupes.png')
    page.locator('.dup-group .btn-danger').last.click(); page.wait_for_timeout(400)
    page.locator('.modal-actions .btn-danger').click(); page.wait_for_timeout(800)
    check('clone deleted → no duplicates remain', page.locator('.dup-group').count() == 0)

    check('zero page errors', not errs, '; '.join(errs[:2]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
exit(1 if fail else 0)
