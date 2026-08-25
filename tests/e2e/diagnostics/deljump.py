import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(viewport={'width':800,'height':1280},is_mobile=True,has_touch=True)
    page=ctx.new_page()
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');
        // pad the health log so the list is genuinely long
        for(let i=0;i<25;i++) await db.Health.save({id:'pad-'+i,eventType:'check',wholeLoft:true,
            birdId:null,date:'2026-0'+((i%9)+1)+'-15',medication:'فحص دوري '+i,notes:''});}""")
    page.reload(); page.wait_for_timeout(1200)
    for route, desc in [('#/health','health: delete an event mid-list'),
                        ('#/races','races: delete a result mid-list')]:
        page.goto(BASE+route,wait_until='load'); page.wait_for_timeout(900)
        page.evaluate('window.scrollTo(0, document.body.scrollHeight*0.6)'); page.wait_for_timeout(300)
        before=page.evaluate('window.scrollY'); h0=page.evaluate('document.body.scrollHeight')
        # click a delete button that is already on screen, then confirm
        clicked=page.evaluate("""() => {
            const btns=[...document.querySelectorAll('tbody .btn-danger')];
            for(const b of btns){const r=b.getBoundingClientRect();
                if(r.top>100 && r.bottom<window.innerHeight-100){b.click(); return true;}}
            return false;}""")
        if not clicked: print(f'  [skip] {desc}'); continue
        page.wait_for_timeout(400)
        if page.locator('.modal-actions .btn-danger').count():
            page.locator('.modal-actions .btn-danger').click()
        page.wait_for_timeout(700)
        after=page.evaluate('window.scrollY'); h1=page.evaluate('document.body.scrollHeight')
        v='JUMP' if before-after>150 else 'ok'
        print(f'  [{v:4}] {desc:40} scrollY {before}→{after}  height {h0}→{h1}')
    br.close()
