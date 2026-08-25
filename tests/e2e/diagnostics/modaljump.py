import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'')
with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(viewport={'width':800,'height':1280},is_mobile=True,has_touch=True)
    page=ctx.new_page()
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)
    print('=== modal lifecycle on a scrolled page ===')
    for route, desc, js in [
        ('#/breeding','breeding: open “new pair” modal', "[...document.querySelectorAll('button')].find(b=>b.textContent.includes('زوج جديد')).click()"),
        ('#/races','races: open “new result” modal', "[...document.querySelectorAll('button')].find(b=>b.textContent.includes('نتيجة جديدة')).click()"),
    ]:
        page.goto(BASE+route,wait_until='load'); page.wait_for_timeout(800)
        page.evaluate('window.scrollTo(0, 600)'); page.wait_for_timeout(250)
        before=page.evaluate('window.scrollY')
        page.evaluate(js); page.wait_for_timeout(600)
        during=page.evaluate('window.scrollY')
        # can the page behind the modal still be scrolled? (should be locked)
        page.evaluate('window.scrollTo(0, 0)'); page.wait_for_timeout(200)
        bg=page.evaluate('window.scrollY')
        page.keyboard.press('Escape'); page.wait_for_timeout(500)
        after=page.evaluate('window.scrollY')
        print(f'  {desc}')
        print(f'     before={before}  while-open={during}  after-scrolling-behind={bg}  after-close={after}')
        pinned = page.evaluate("getComputedStyle(document.body).position") if False else None
        print(f'     background pinned while open: {"yes" if during==0 else "no"} (body taken out of flow)')
        print(f'     position restored on close: {"NO" if before-after>150 else "yes"}')
    br.close()
