'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useZajilStore, selectBirds } from '@/src/db/react';
import { t, fmtNum } from '@/src/i18n.ext.js';
import { SyncRow, Loading, initDB } from '@/src/components';
import { type Pair, type Round, type Egg, type Bird, getBird, nameOf, Plate, StatusChip, stats, Chev, Plus, LinkSheet, RingSheet,
  toggleActive, addRound, addEgg, hatch, fail, wean, unlink, setEggDate, deletePair, deleteRound, deleteEgg } from '../breeding/shared';
import s from '../breeding/breeding.module.css';

// Breeding, level 2 — one pair (breeding-v1 «تفاصيل زوج»): the pair head
// (parents, status, nest / bought / hatched chips, delete + separate), the
// collapsible rounds with their eggs (state chip, laid date, ⋯ menu, the
// state's actions), «بطن جديد», and the pair's offspring. Deletes for the
// pair, a round or an egg confirm inline (spec) and undo through the shell.
type Sheet = { kind: 'link' | 'ring'; roundId: string; eggId: string } | null;
const chipOf = (e: Egg) => e.state === 'hatched' ? <span className={`${s.chip} ${s.hatch}`}><span className={s.ico}>🐣</span>{t('br.egg.hatched')}</span>
  : e.state === 'failed' ? <span className={`${s.chip} ${s.fail}`}><span className={s.ico}>✕</span><span className={s.t}>{t('br.egg.failed')}</span></span>
  : <span className={`${s.chip} ${s.laid}`}><span className={s.ico}>🥚</span>{t('br.egg.laid')}</span>;
// Confirm and Date_ are declared here, at module scope, on purpose: a component
// created inside the render body is a new component type on every render, so
// React remounts its DOM subtree — Date_'s text field would lose the caret after
// a single keystroke. What they used to close over is passed in instead.
const Confirm = ({ onGo, onNo, small }: { onGo: () => void; onNo: () => void; small?: boolean }) => (
  <div className={`${s.confirm} ${small ? s.sm : ''}`} data-testid="inline-confirm"><span>{t('confirm.deleteGeneric')}</span><div className={s.b}><button type="button" className={s.go} onClick={onGo} data-testid="confirm-go">{t('act.delete')}</button><button type="button" className={s.no} onClick={onNo} data-testid="confirm-no">{t('act.cancel')}</button></div></div>
);
const Date_ = ({ label, egg, k, pair }: { label: string; egg: Egg; k: 'laidDate' | 'hatchDate' | 'weanDate'; pair: Pair }) => (
  <span className={s.df}><label>{label}:</label><input type="date" value={egg[k] || ''} onChange={(e) => setEggDate(pair, egg.id, k, e.target.value)} aria-label={label} data-testid={`egg-${k}`} /></span>
);

export default function PairView() {
  const params = useSearchParams(); const router = useRouter();
  const id = params.get('id') || '';
  const [booted, setBooted] = useState(false);
  const [open, setOpen] = useState<Set<string> | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [sheet, setSheet] = useState<Sheet>(null);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const pair = useZajilStore((x) => x.pairs.get(id) as Pair | undefined) ?? null;
  const birds = useZajilStore(selectBirds) as Bird[];
  useEffect(() => { if (booted && !pair) router.replace('/breeding'); }, [booted, pair, router]);
  useEffect(() => { if (!menu) return; const f = (e: MouseEvent) => { if (!(e.target as HTMLElement).closest?.('[data-more]')) setMenu(null); }; document.addEventListener('click', f); return () => document.removeEventListener('click', f); }, [menu]);
  if (!booted || !pair) return <section className={s.screen}><Loading /></section>;
  const rounds = pair.rounds || [];
  const isOpen = (r: Round) => open ? open.has(r.id) : r.id === rounds[rounds.length - 1]?.id;   // the newest round starts open
  const toggleRound = (r: Round) => { const n = new Set(open ?? (rounds.length ? [rounds[rounds.length - 1].id] : [])); if (n.has(r.id)) n.delete(r.id); else n.add(r.id); setOpen(n); setMenu(null); };
  const sire = getBird(pair.sireId), dam = getBird(pair.damId);
  const x = stats(pair);
  const chickIds = new Set(rounds.flatMap((r) => r.eggs || []).map((e) => e.chickId).filter(Boolean) as string[]);
  const kids = birds.filter((b) => (b.sireId === pair.sireId && b.damId === pair.damId) || chickIds.has(b.id));   // breeding.js:117 + the linked chicks
  const active = pair.status === 'active';
  const sheetEgg = sheet ? rounds.find((r) => r.id === sheet.roundId)?.eggs?.find((e) => e.id === sheet.eggId) : null;

  return (
    <section className={s.screen}>
      <header className={s.lofthead}><div className={s.in}><div className={s.headrow}>
        <div>
          <Link href={`/breeding?season=${pair.season || ''}`} className={s.back} data-testid="back-link"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>{t('br.pairsSeason', { y: pair.season || '' })}</Link>
          <h1 data-testid="pair-title"><bdi>{nameOf(sire)}</bdi> × <bdi>{nameOf(dam)}</bdi></h1>
        </div>
      </div></div></header>
      <SyncRow />
      <section className={s.panel}>
        <div className={s.detail}>
          <article className={`${s.pair} ${active ? '' : s.off}`} data-testid="pair-card" data-status={pair.status}>
            <div className={s.phead}>
              <div className={s.ptop}>
                <div className={s.parents}>
                  <Link href={`/bird?id=${pair.sireId}`} className={s.parent} data-testid="parent-sire"><span className={s.nm}><span className={`${s.sex} ${s.m}`}>♂</span><bdi>{nameOf(sire)}</bdi></span><Plate b={sire} /></Link>
                  <span className={s.x}>×</span>
                  <Link href={`/bird?id=${pair.damId}`} className={s.parent} data-testid="parent-dam"><span className={s.nm}><span className={`${s.sex} ${s.f}`}>♀</span><bdi>{nameOf(dam)}</bdi></span><Plate b={dam} /></Link>
                </div>
                <StatusChip p={pair} />
              </div>
              <div className={s.chips}>
                <span className={s.chip}>{t('br.nestBox')} <b>{pair.nestBox || '—'}</b></span>
                {pair.acquiredFrom && <span className={s.chip}>{t('br.bought')}: <bdi>{pair.acquiredFrom}</bdi></span>}
                {x.eggs > 0 && <span className={s.stat} data-testid="pair-stat">🐣 {t('br.hatchedOf', { h: fmtNum(x.hatched), n: fmtNum(x.eggs) })}</span>}
              </div>
              <div className={s.pacts}>
                {confirm === 'pair' ? <Confirm onNo={() => setConfirm(null)} onGo={async () => { setConfirm(null); await deletePair(pair); router.replace(`/breeding?season=${pair.season || ''}`); }} />
                  : <button type="button" className={`${s.act} ${s.x}`} onClick={() => setConfirm('pair')} data-testid="pair-delete">{t('act.delete')}</button>}
                <button type="button" className={`${s.act} ${s.toggle}`} title={active ? t('br.separate') : t('br.reactivate')} onClick={() => toggleActive(pair)} data-testid="pair-toggle">{active ? t('br.separated') : t('br.active')}</button>
              </div>
            </div>
            <div className={s.divider} />
            {rounds.length > 0 && (
              <div className={s.rounds}>
                {rounds.map((r, i) => {
                  const eggs = r.eggs || []; const h = eggs.filter((e) => e.state === 'hatched').length, f = eggs.filter((e) => e.state === 'failed').length;
                  return (
                    <div key={r.id} className={`${s.round} ${isOpen(r) ? s.open : ''}`} data-testid="round" data-open={isOpen(r) ? '1' : '0'}>
                      <button type="button" className={s.rsum} aria-expanded={isOpen(r)} onClick={() => toggleRound(r)} data-testid="round-toggle">
                        <Chev /><h3>{t('br.round')} {fmtNum(i + 1, { group: false })}</h3>
                        <span className={s.m}>{eggs.length ? <>{t('br.eggsCount', { n: fmtNum(eggs.length) })} · <span className={s.h}>{fmtNum(h)} {t('br.egg.hatched')}</span>{f ? <> · <span className={s.n}>{fmtNum(f)} {t('br.egg.failed')}</span></> : null}</> : <span className={s.n}>{t('br.noEggs')}</span>}</span>
                      </button>
                      <div className={s.rbody}>
                        <div className={s.eggs}>
                          {eggs.map((e) => {
                            const k = 'e' + e.id; const chick = getBird(e.chickId);
                            if (confirm === k) return <div key={e.id} className={s.egg} data-testid="egg"><div className={s.l1}>{chipOf(e)}<Confirm small onNo={() => setConfirm(null)} onGo={async () => { setConfirm(null); await deleteEgg(pair, r.id, e.id); }} /></div></div>;
                            return (
                              <div key={e.id} className={s.egg} data-testid="egg" data-state={e.state}>
                                <div className={s.l1}>
                                  {chipOf(e)}<Date_ label={t('br.laidDate')} egg={e} k="laidDate" pair={pair} />
                                  <span className={s.more} data-more="1">
                                    <button type="button" className={`${s.act} ${s.q}`} aria-label={t('act.more')} aria-expanded={menu === k} onClick={() => setMenu(menu === k ? null : k)} data-testid="egg-more">⋯</button>
                                    {menu === k && (
                                      <div className={s.menu} role="menu" data-testid="egg-menu">
                                        {e.state === 'hatched' && chick && <><button type="button" onClick={() => { setMenu(null); unlink(pair, e.id); }} data-testid="egg-unlink"><span>⛓</span>{t('br.unlink')}</button>{e.weaned && <div className={s.df}><label>{t('br.weanDate')}:</label><input type="date" value={e.weanDate || ''} onChange={(ev) => setEggDate(pair, e.id, 'weanDate', ev.target.value)} aria-label={t('br.weanDate')} data-testid="egg-weanDate" /></div>}<div className={s.sep} /></>}
                                        <button type="button" className={s.del} onClick={() => { setMenu(null); setConfirm(k); }} data-testid="egg-delete">{t('br.deleteEgg')}</button>
                                      </div>
                                    )}
                                  </span>
                                </div>
                                <div className={s.l2}>
                                  {e.state === 'laid' && <><button type="button" className={`${s.act} ${s.p}`} onClick={() => hatch(pair, e.id)} data-testid="egg-hatch">{t('br.markHatched')}</button><button type="button" className={s.act} onClick={() => fail(pair, e.id)} data-testid="egg-fail">{t('br.markFailed')}</button></>}
                                  {e.state === 'hatched' && (
                                    <>
                                      <Date_ label={t('br.hatch')} egg={e} k="hatchDate" pair={pair} />
                                      {!chick ? <><button type="button" className={`${s.act} ${s.p}`} onClick={() => setSheet({ kind: 'ring', roundId: r.id, eggId: e.id })} data-testid="egg-ring">{t('br.ringChick')}</button><button type="button" className={s.act} onClick={() => setSheet({ kind: 'link', roundId: r.id, eggId: e.id })} data-testid="egg-link">{t('br.linkExisting')}</button></>
                                        : <><Link href={`/bird?id=${chick.id}`} className={s.chick} data-testid="egg-chick"><span className={s.bird}>🐦</span><bdi>{nameOf(chick)}</bdi><Plate b={chick} /></Link>{e.weaned ? <span className={`${s.chip} ${s.wean}`} data-testid="egg-weaned">{t('br.weaned')}</span> : <button type="button" className={`${s.act} ${s.dk}`} onClick={() => wean(pair, e.id)} data-testid="egg-wean">{t('br.wean')}</button>}</>}
                                    </>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <div className={s.addrow} style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                          <button type="button" className={s.ghost} onClick={() => addEgg(pair, r.id)} data-testid="add-egg"><Plus />{t('br.addEgg')}</button>
                          {confirm === 'r' + r.id ? <Confirm small onNo={() => setConfirm(null)} onGo={async () => { setConfirm(null); await deleteRound(pair, r.id); }} />
                            : <button type="button" className={`${s.act} ${s.q}`} style={{ fontSize: 13, letterSpacing: 0, color: 'var(--ink-3)' }} onClick={() => setConfirm('r' + r.id)} data-testid="round-delete">{t('br.deleteRound')}</button>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div className={s.addrow} style={{ marginTop: rounds.length ? 10 : 14 }}><button type="button" className={`${s.ghost} ${s.wide}`} onClick={async () => { const rid = await addRound(pair); setOpen(new Set([...(open ?? []), rid])); }} data-testid="add-round"><Plus />{t('br.addRound')}</button></div>
            {kids.length > 0 && <div className={s['off-block']} data-testid="offspring"><div className={s.k}>{t('br.offspringOf')}</div><div className={s.list}>{kids.map((b) => <Link key={b.id} href={`/bird?id=${b.id}`} className={s.birdpill} data-testid="offspring-pill"><bdi>{nameOf(b)}</bdi><Plate b={b} /></Link>)}</div></div>}
          </article>
        </div>
      </section>
      {sheet && sheetEgg && sheet.kind === 'link' && <LinkSheet pair={pair} egg={sheetEgg} onClose={() => setSheet(null)} onDone={() => setSheet(null)} />}
      {sheet && sheetEgg && sheet.kind === 'ring' && <RingSheet pair={pair} roundIndex={rounds.findIndex((r) => r.id === sheet.roundId)} egg={sheetEgg} onClose={() => setSheet(null)} onDone={() => setSheet(null)} />}
    </section>
  );
}
