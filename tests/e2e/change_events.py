import os
from playwright.sync_api import sync_playwright
BASE = os.environ.get('ZAJIL_URL', 'http://127.0.0.1:8123/')
ok = fail = 0
def check(n, c, e=''):
    global ok, fail
    if c: ok += 1; print(f'  ✓ {n}')
    else: fail += 1; print(f'  ✗ {n} {e}')

with sync_playwright() as p:
    br = p.chromium.launch()
    page = br.new_page(viewport={'width': 900, 'height': 800})
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(BASE, wait_until='networkidle'); page.wait_for_timeout(700)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)

    # 1. a write from OUTSIDE the view must refresh the visible list
    page.goto(BASE + '#/birds'); page.wait_for_timeout(900)
    before = page.locator('.bird-row').count()
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.saveBird(db.newBird({name:'حدث تغيير', sex:'cock'}));}""")
    page.wait_for_timeout(700)
    check('an external write refreshes the register',
          page.locator('.bird-row').count() == before + 1,
          f'{before} -> {page.locator(".bird-row").count()}')

    # 2. THE REGRESSION GUARD: a change event while a dialog is open must not
    #    move the page (v1.5 fixed the page scrolling behind dialogs)
    page.goto(BASE + '#/breeding'); page.wait_for_timeout(900)
    page.evaluate('window.scrollTo(0, 500)'); page.wait_for_timeout(300)
    scroll_before = page.evaluate('window.scrollY')
    page.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('زوج جديد')).click()")
    page.wait_for_timeout(600)
    check('dialog is open', page.locator('.modal-overlay').count() == 1)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.saveBird(db.newBird({name:'أثناء الحوار', sex:'hen'}));}""")
    page.wait_for_timeout(800)
    check('dialog SURVIVES a change event fired while it is open',
          page.locator('.modal-overlay').count() == 1)
    page.keyboard.press('Escape'); page.wait_for_timeout(700)
    scroll_after = page.evaluate('window.scrollY')
    check('page did NOT move (v1.5 scroll fix intact)',
          abs(scroll_after - scroll_before) < 60, f'{scroll_before} -> {scroll_after}')

    # 3. scroll position preserved across a refresh triggered by a change event
    page.goto(BASE + '#/birds'); page.wait_for_timeout(900)
    page.evaluate('window.scrollTo(0, 700)'); page.wait_for_timeout(300)
    y0 = page.evaluate('window.scrollY')
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.saveBird(db.newBird({name:'حفظ الموضع', sex:'cock'}));}""")
    page.wait_for_timeout(800)
    y1 = page.evaluate('window.scrollY')
    check('scroll position preserved across an auto-refresh', abs(y1 - y0) < 80, f'{y0} -> {y1}')

    # 4. undo of a delete must put the bird back in the visible register
    page.goto(BASE + '#/bird/g5-najma26'); page.wait_for_timeout(800)
    page.locator('.detail-actions button.btn-danger').click(); page.wait_for_timeout(400)
    page.locator('.modal-actions .btn-danger').click(); page.wait_for_timeout(900)
    gone = page.locator('.bird-row').count()
    page.locator('.toast-action').click(); page.wait_for_timeout(900)
    check('undo restores the bird INTO the visible list',
          page.locator('.bird-row').count() == gone + 1,
          f'{gone} -> {page.locator(".bird-row").count()}')

    # 5. media writes must go through db.js and emit
    check('no view imports idbPut/idbDelete', page.evaluate("""async()=>{
        const src = await (await fetch('./js/views/bird-detail.js')).text();
        return !/idbPut|idbDelete/.test(src);}"""))

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
