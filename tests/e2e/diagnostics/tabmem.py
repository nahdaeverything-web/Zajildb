import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
with sync_playwright() as p:
    br=p.chromium.launch(); ctx=br.new_context(viewport={'width':800,'height':1280},is_mobile=True,has_touch=True)
    page=ctx.new_page()
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.goto(BASE+'#/races',wait_until='load'); page.wait_for_timeout(900)
    page.evaluate('window.scrollTo(0,500)'); page.wait_for_timeout(300)
    a=page.evaluate('window.scrollY')
    page.evaluate("document.querySelectorAll('.seg-btn')[1].click()"); page.wait_for_timeout(600)
    b=page.evaluate('window.scrollY')
    page.evaluate("document.querySelectorAll('.seg-btn')[0].click()"); page.wait_for_timeout(700)
    c=page.evaluate('window.scrollY')
    print(f'  log@{a} → FCI@{b} → back to log@{c}')
    print(f'  place restored on return: {"YES" if abs(c-a)<60 else "no"}')
    br.close()
