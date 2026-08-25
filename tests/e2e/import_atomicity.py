import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('ZAJIL_URL','http://127.0.0.1:8123/')
ok=fail=0
def check(n,c,e=''):
    global ok,fail
    if c: ok+=1; print(f'  ✓ {n}')
    else: fail+=1; print(f'  ✗ {n} {e}')
with sync_playwright() as p:
    br=p.chromium.launch(); page=br.new_page(viewport={'width':1000,'height':800})
    errs=[]; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(BASE,wait_until='networkidle'); page.wait_for_timeout(700)
    page.evaluate("""async()=>{const db=await import('./js/db.js');
        await db.importAll(await (await fetch('./example-loft-large.json')).json(),'merge');}""")
    page.wait_for_timeout(600)

    r=page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        const out={};
        const before={birds:db.state.birds.size, pairs:db.state.pairs.size,
                      races:db.state.raceResults.size, health:db.state.healthEvents.size,
                      lofts:db.state.lofts.size, loftId:db.state.currentLoftId};
        out.before=before;
        const good='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
        // a payload that is entirely valid EXCEPT its 3rd media entry
        const poisoned={format:'zajil-export',version:1,exportedAt:new Date().toISOString(),
            lofts:[{id:'imported-loft',name:'مستورد',location:'',statuses:['breeder'],updatedAt:new Date().toISOString()}],
            birds:[{id:'imp-1',rings:[],name:'مستورد',sex:'cock',external:false,status:'stock',
                    sireId:null,damId:null,notes:[],updatedAt:new Date().toISOString()}],
            pairs:[],raceResults:[],healthEvents:[],
            media:[{id:'m1',birdId:'imp-1',kind:'photo',subtype:'body',name:'a.png',dataURL:good},
                   {id:'m2',birdId:'imp-1',kind:'photo',subtype:'body',name:'b.png',dataURL:good},
                   {id:'m3',birdId:'imp-1',kind:'photo',subtype:'body',name:'c.png',dataURL:'data:image/png;base64,@@@NOT-BASE64@@@'},
                   {id:'m4',birdId:'imp-1',kind:'photo',subtype:'body',name:'d.png',dataURL:good}]};
        try { await db.importAll(poisoned,'replace'); out.threw=false; }
        catch(e){ out.threw=true; out.err=String(e.message||e).slice(0,80); }
        out.after={birds:db.state.birds.size, pairs:db.state.pairs.size,
                   races:db.state.raceResults.size, health:db.state.healthEvents.size,
                   lofts:db.state.lofts.size, loftId:db.state.currentLoftId};
        // and the PERSISTED state, not just the in-memory mirror
        out.persisted=(await db.idbGetAll('birds')).length;
        return out;}""")
    check('a malformed media entry is rejected, not swallowed', r['threw'], str(r))
    check('in-memory state is completely untouched',
          r['after']==r['before'], f"{r['before']} -> {r['after']}")
    check('persisted birds are untouched too',
          r['persisted']==r['before']['birds'], f"{r['persisted']} vs {r['before']['birds']}")
    check('currentLoftId still resolves', r['after']['loftId']==r['before']['loftId'])

    # a VALID replace-import must still work end to end
    r2=page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        const good='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
        const clean={format:'zajil-export',version:1,exportedAt:new Date().toISOString(),
            lofts:[{id:'ok-loft',name:'سليم',location:'',statuses:['breeder'],updatedAt:new Date().toISOString()}],
            birds:[{id:'ok-1',rings:[],name:'سليم',sex:'cock',external:false,status:'stock',
                    sireId:null,damId:null,notes:[],updatedAt:new Date().toISOString()}],
            pairs:[],raceResults:[],healthEvents:[],
            media:[{id:'okm',birdId:'ok-1',kind:'photo',subtype:'body',name:'x.png',dataURL:good}]};
        const counts=await db.importAll(clean,'replace');
        return {birds:db.state.birds.size, media:(await db.idbGetAll('media')).length,
                loftId:db.state.currentLoftId, counts};}""")
    check('a valid replace-import still works', r2['birds']==1 and r2['media']==1 and r2['loftId']=='ok-loft', str(r2))
    check('a rollback snapshot was taken before the wipe', page.evaluate("""async()=>{
        const db=await import('./js/db.js');
        const b=await db.listBackups();
        return b.some(x=>String(x.id).includes('pre-import'));}"""))
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
