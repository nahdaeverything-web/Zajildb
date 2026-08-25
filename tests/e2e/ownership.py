import os
from playwright.sync_api import sync_playwright
ok=fail=0
def check(n,c,e=''):
    global ok,fail
    if c: ok+=1; print(f'  ✓ {n}')
    else: fail+=1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    b=p.chromium.launch(); page=b.new_page(viewport={'width':1280,'height':900})
    errs=[]; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''),wait_until='networkidle'); page.wait_for_timeout(700)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)

    # ownership control on the form
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/new'); page.wait_for_timeout(700)
    own = page.locator('.ownership-section select')
    check('ownership selector present', own.count()==1)
    status_field = page.locator('label.field', has_text='الحالة').first
    check('status visible for an owned bird', status_field.is_visible())
    own.select_option('external'); page.wait_for_timeout(300)
    check('status hidden for an external bird', not status_field.is_visible())
    page.locator('.ring-input').fill('BE-2011-9999001')
    page.locator('button.btn-primary[type=submit]').click(); page.wait_for_timeout(900)
    saved = page.evaluate("""async()=>{const db=await import('./js/db.js');
        const b=db.allBirds().find(x=>(x.rings||[]).some(r=>r.raw==='BE-2011-9999001'));
        return b?{external:b.external,status:b.status}:null;}""")
    check('saved as external with reference status', saved and saved['external'] and saved['status']=='reference', str(saved))

    # register ownership filter
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/birds'); page.wait_for_timeout(900)
    total = page.locator('.bird-row').count()
    sels = page.locator('.filter-bar select')
    sels.nth(0).select_option('owned'); page.wait_for_timeout(500)
    owned = page.locator('.bird-row').count()
    sels.nth(0).select_option('external'); page.wait_for_timeout(500)
    ext = page.locator('.bird-row').count()
    check('ownership filter splits the register', owned+ext==total and ext>0, f'{owned}+{ext} vs {total}')

    # pair provenance + backdating
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/breeding'); page.wait_for_timeout(700)
    page.locator('button', has_text='زوج جديد').click(); page.wait_for_timeout(500)
    dates = page.locator('.modal input[type=date]')
    check('pair dialog exposes pairing + acquired dates', dates.count()==2, str(dates.count()))
    check('pair dialog has acquired-from', page.locator('.modal input[type=text]').count()>=2)
    page.keyboard.press('Escape'); page.wait_for_timeout(300)

    # link-existing on the unringed hatched egg in the example data
    rows = page.locator('.egg-row.egg-hatched')
    linked=False
    for i in range(rows.count()):
        r=rows.nth(i)
        if r.locator('button', has_text='ربط طير مسجَّل').count():
            r.locator('button', has_text='ربط طير مسجَّل').click(); linked=True; break
    check('link-existing button offered on an unringed hatched egg', linked)
    if linked:
        page.wait_for_timeout(500)
        page.locator('.modal .bird-picker input').fill('غيمة'); page.wait_for_timeout(500)
        page.locator('.modal .picker-item').first.click(); page.wait_for_timeout(300)
        page.locator('.modal-actions .btn-primary').click(); page.wait_for_timeout(900)
        check('linking either succeeds or explains why', page.locator('.problems li').count()>0 or page.locator('.modal').count()==0)
    check('zero page errors', not errs, '; '.join(errs[:2]))
    b.close()
print(f'\n{ok} passed, {fail} failed')
