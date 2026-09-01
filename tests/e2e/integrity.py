import os
from playwright.sync_api import sync_playwright

# The shipped datasets carry real uuids (v1.9.1). Python's uuid5 derives exactly
# what tools/idmap.js derives from the same namespace and key, so these suites
# keep naming birds by the readable key that documents what they are.
import uuid as _uuid
_ID_NS = _uuid.UUID('7f3c9a54-2b18-4d6e-9c05-1a2b3c4d5e6f')
def bird_id(key):
    return str(_uuid.uuid5(_ID_NS, key))
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

    r=page.evaluate("""async(a)=>{
        const db=await import('./js/db.js');
        const {checkIntegrity}=await import('./js/engine/integrity.js');
        const snap=()=>({birds:db.state.birds,pairs:db.state.pairs,
                         raceResults:db.state.raceResults,healthEvents:db.state.healthEvents});
        const out={};
        out.beforeClean = checkIntegrity(snap()).length;
        // g4-malik: has race results? pairs? make sure the target has all four kinds
        const target = a;   // sire of a 2026 pair, has race results
        out.races  = [...db.state.raceResults.values()].filter(x=>x.birdId===target).length;
        out.pairs  = [...db.state.pairs.values()].filter(x=>x.sireId===target||x.damId===target).length;
        await db.Health.save({id:'ih-1',eventType:'check',birdId:target,date:'2026-01-01',wholeLoft:false});
        out.health = [...db.state.healthEvents.values()].filter(x=>x.birdId===target).length;
        const counts0={b:db.state.birds.size,r:db.state.raceResults.size,
                       h:db.state.healthEvents.size,p:db.state.pairs.size};
        const snapshot = await db.deleteBird(target);
        out.afterDelete = checkIntegrity(snap()).length;
        await db.restoreBird(snapshot);
        out.afterUndo = checkIntegrity(snap()).length;
        const counts1={b:db.state.birds.size,r:db.state.raceResults.size,
                       h:db.state.healthEvents.size,p:db.state.pairs.size};
        out.restored = JSON.stringify(counts0)===JSON.stringify(counts1);
        out.counts0=counts0; out.counts1=counts1;
        return out;}""", bird_id('g4-wisam'))
    check('database starts referentially clean', r['beforeClean']==0, str(r['beforeClean']))
    check('target really had races/pairs/health to orphan',
          r['races']>0 and r['pairs']>0 and r['health']>0, str({k:r[k] for k in ('races','pairs','health')}))
    check('after delete: ZERO dangling references', r['afterDelete']==0, str(r['afterDelete']))
    check('after undo: still zero dangling references', r['afterUndo']==0, str(r['afterUndo']))
    check('after undo: every record count restored', r['restored'], f"{r['counts0']} vs {r['counts1']}")
    check('zero page errors', not errs, '; '.join(errs[:2]))
    br.close()
print(f'\n{ok} passed, {fail} failed')
