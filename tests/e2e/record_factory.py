import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')
ok=fail=0
def check(n,c,e=''):
    global ok,fail
    if c: ok+=1; print(f'  ✓ {n}')
    else: fail+=1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    br=p.chromium.launch(); page=br.new_page(viewport={'width':1100,'height':900})
    errs=[]; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(700)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)

    # ---- every creation PATH must produce a consistent external bird ----
    # path 1: the form's ownership selector
    page.goto(BASE+'#/bird/new'); page.wait_for_timeout(800)
    page.locator('.ownership-section select').select_option('external'); page.wait_for_timeout(250)
    page.locator('.ring-input').fill('BE-2001-9000001')
    page.locator('button.btn-primary[type=submit]').click(); page.wait_for_timeout(900)
    # path 2: the picker's inline create
    page.goto(BASE+'#/bird/new'); page.wait_for_timeout(800)
    sire=page.locator('.bird-picker input').first
    sire.fill('BE-2001-9000002'); page.wait_for_timeout(450)
    page.locator('.picker-create').click(); page.wait_for_timeout(700)

    r=page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        const ext=db.allBirds().filter(b=>b.external);
        return {n:ext.length, allReference:ext.every(b=>b.status===db.REFERENCE_STATUS),
                offenders:ext.filter(b=>b.status!==db.REFERENCE_STATUS).map(b=>({n:b.name,s:b.status}))};}""")
    check('every external bird from every path carries REFERENCE_STATUS',
          r['allReference'] and r['n']>=2, f"{r['n']} external, offenders={r['offenders']}")

    # ---- add-sibling must write NOTHING when abandoned ----
    # deterministic fixture: an owned bird with no recorded parents
    target=page.evaluate("""async()=>{const db=await import('./js/db.js');
        const b=await db.saveBird(db.newBird({name:'بلا أبوين', sex:'hen'}));
        return b.id;}""")
    before=page.evaluate(f"""async()=>{{const db=await import('./js/db.js');
        const b=db.getBird('{target}'); return {{s:b.sireId,d:b.damId,n:db.allBirds().length}};}}""")
    page.goto(BASE+f'#/bird/{target}'); page.wait_for_timeout(800)
    page.locator('button', has_text='إضافة شقيق').click(); page.wait_for_timeout(500)
    page.locator('.modal-actions .btn-primary').click(); page.wait_for_timeout(800)
    check('add-sibling routes to the form with an intent', 'siblingOf=' in page.url, page.url)
    check('a notice explains what will happen on save', page.locator('.banner-warn').count()>=1)
    page.goto(BASE+'#/birds'); page.wait_for_timeout(800)   # ABANDON
    after=page.evaluate(f"""async()=>{{const db=await import('./js/db.js');
        const b=db.getBird('{target}'); return {{s:b.sireId,d:b.damId,n:db.allBirds().length}};}}""")
    check('abandoning add-sibling leaves the original bird untouched',
          after['s']==before['s'] and after['d']==before['d'], f"{before} -> {after}")
    check('abandoning add-sibling creates no placeholder records',
          after['n']==before['n'], f"{before['n']} -> {after['n']}")

    # ---- completing it DOES link both birds ----
    page.goto(BASE+f'#/bird/{target}'); page.wait_for_timeout(700)
    page.locator('button', has_text='إضافة شقيق').click(); page.wait_for_timeout(500)
    page.locator('.modal-actions .btn-primary').click(); page.wait_for_timeout(800)
    page.locator('.ring-input').fill('JO-2026-8800001')
    page.locator('button.btn-primary[type=submit]').click(); page.wait_for_timeout(1200)
    done=page.evaluate(f"""async()=>{{const db=await import('./js/db.js');
        const orig=db.getBird('{target}');
        const sib=db.allBirds().find(b=>(b.rings||[]).some(r=>r.raw==='JO-2026-8800001'));
        const {{checkIntegrity}}=await import('./js/engine/integrity.js');
        return {{origS:orig.sireId,origD:orig.damId,
                sibS:sib?sib.sireId:null,sibD:sib?sib.damId:null,
                dangling:checkIntegrity({{birds:db.state.birds,pairs:db.state.pairs,
                    raceResults:db.state.raceResults,healthEvents:db.state.healthEvents}}).length}};}}""")
    check('completing it links BOTH birds to the same parents',
          done['origS'] and done['origS']==done['sibS'] and done['origD']==done['sibD'], str(done))
    check('and leaves the database referentially clean', done['dangling']==0, str(done['dangling']))
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
