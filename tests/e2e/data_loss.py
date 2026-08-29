import os
from playwright.sync_api import sync_playwright
ok=fail=0
def check(n,c,e=''):
    global ok,fail
    if c: ok+=1; print(f'  ✓ {n}')
    else: fail+=1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    br=p.chromium.launch(); ctx=br.new_context(viewport={'width':1280,'height':900}); page=ctx.new_page()
    errs=[]; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(os.environ.get('ZAJIL_URL',os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+''),wait_until='networkidle'); page.wait_for_timeout(800)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.reload(); page.wait_for_timeout(1000)

    # ── BUG 1: type into a filled sire field, abandon, save → link must survive
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/g5-faris26/edit'); page.wait_for_timeout(900)
    before=page.evaluate("async()=>{const db=await import('./js/db.js');const b=db.getBird('g5-faris26');return {s:b.sireId,d:b.damId};}")
    sire=page.locator('.bird-picker input').first
    sire.click(); page.wait_for_timeout(200)
    sire.type('xyz'); page.wait_for_timeout(300)
    page.locator('h1').first.click(); page.wait_for_timeout(600)   # abandon
    check('field reverts to the real sire after abandoning a search',
          'الملك' in sire.input_value(), repr(sire.input_value()))
    page.locator('button.btn-primary[type=submit]').click(); page.wait_for_timeout(1000)
    after=page.evaluate("async()=>{const db=await import('./js/db.js');const b=db.getBird('g5-faris26');return {s:b.sireId,d:b.damId};}")
    check('parent links survive the save', after==before, f'{before} -> {after}')

    # explicit clear must STILL work
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/bird/g5-faris26/edit'); page.wait_for_timeout(900)
    page.locator('.bird-picker button', has_text='إزالة').first.click(); page.wait_for_timeout(300)
    page.locator('h1').first.click(); page.wait_for_timeout(500)
    check('explicit clear button still detaches', page.locator('.bird-picker input').first.input_value()=='')

    # ── BUG 2: object URLs revoked on navigation
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/birds'); page.wait_for_timeout(600)
    leak=page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        const blob=new Blob([new Uint8Array(2048)],{type:'image/png'});
        await db.addMedia('g5-faris26','photo','body','t.png',blob);
        const ui=await import('./js/ui.js');
        let revoked=0; const orig=URL.revokeObjectURL;
        URL.revokeObjectURL=(u)=>{revoked++; return orig.call(URL,u);};
        location.hash='#/bird/g5-faris26'; await new Promise(r=>setTimeout(r,900));
        location.hash='#/birds'; await new Promise(r=>setTimeout(r,700));
        URL.revokeObjectURL=orig;
        return revoked;}""")
    check('gallery object URLs revoked when leaving the view', leak>=1, f'revoked={leak}')

    # ── BUG 3: restoring an auto-snapshot must keep photos
    kept=page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        await db.autoBackup();
        const beforeMedia=(await db.idbGetAll('media')).length;
        const snaps=await db.listBackups();
        await db.importAll(snaps[snaps.length-1].payload,'replace');
        const afterMedia=(await db.idbGetAll('media')).length;
        return {beforeMedia, afterMedia};}""")
    check('photos survive an auto-snapshot restore',
          kept['afterMedia']==kept['beforeMedia'] and kept['beforeMedia']>0, str(kept))

    # ── BUG 4: replace-import from another device must not dangle currentLoftId
    res=page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        const foreign={format:'zajil-export',version:1,exportedAt:new Date().toISOString(),
            lofts:[{id:'other-device-loft',name:'لوفت آخر',location:'',statuses:['breeder','stock'],updatedAt:new Date().toISOString()}],
            birds:[],pairs:[],raceResults:[],healthEvents:[],media:[]};
        await db.importAll(foreign,'replace');
        return {current:db.state.currentLoftId, exists:!!db.currentLoft(),
                name:db.currentLoft()?db.currentLoft().name:null};}""")
    check('currentLoftId repaired after a foreign replace-import',
          res['exists'] and res['current']=='other-device-loft', str(res))
    page.reload(); page.wait_for_timeout(900)
    page.goto(os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')+'#/tools'); page.wait_for_timeout(1000)
    # Select the loft card by its HEADING, not by position. This read used to be
    # `.card[1]`, which silently pointed at a different card the moment another
    # was added above it — and the suite then died on a null rather than
    # reporting anything useful.
    loftname=page.evaluate("""() => {
        const card = [...document.querySelectorAll('.card')]
            .find(c => { const h = c.querySelector('h2'); return h && h.textContent.includes('اللوفت'); });
        const input = card && card.querySelector('input');
        return input ? input.value : null;
    }""")
    check('loft settings card is usable, not blank', loftname=='لوفت آخر', repr(loftname))

    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
