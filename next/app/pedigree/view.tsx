'use client';
import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectBird, selectBirds } from '@/src/db/react';
import { t, fmtDate, fmtNum, fmtPercent } from '@/src/i18n.ext.js';
import { pedigreeGrid } from '@/src/engine/pedigree.js';
import { inbreeding, ancestorLoss, coiBreakdown } from '@/src/engine/coi.js';
import { describeRelationship, pairingWarningLevel } from '@/src/engine/relationship.js';
import { ringKey } from '@/src/engine/rings.js';
import { SyncRow, Loading, COIValue, BirdLabel, SexChip, primaryRing, birdLabelText, seasonLabel, toast, downloadJSON, initDB } from '@/src/components';
import s from './pedigree.module.css';

// Pedigree tree — design/approved/pedigree-tree-v1.html, behaviour from
// js/views/pedigree.js. Spec wins on presentation: the wall chart (subject
// on the RTL start edge, one column per generation, bracket connectors),
// the three tiles, the legend, the common-ancestor dot, the unknown-ancestor
// slot, print / share / certificate actions. Vanilla wins on wiring:
// pedigreeGrid + coiBreakdown + ancestorLoss + describeRelationship from the
// engine, the 3/4/5 generation control, the COI breakdown table and the
// relationship finder — all carried below the chart in the spec's grammar
// (raised in the 4B report: the spec fixes four ancestor generations and
// draws neither panel).
type Ring = { raw?: string; type?: string; year?: number | string | null };
type Bird = { id: string; name?: string; sex?: string; hatchDate?: string; strain?: string; sireId?: string | null; damId?: string | null; rings?: Ring[] };
type Slot = { id: string; bird: Bird | undefined } | null;
type Contribution = { ancestorId: string; nPathPairs: number; ancestorF: number; contribution: number };
const getBird = (id: string) => db.getBird(id) as Bird | undefined;
const GENS = [3, 4, 5] as const;
const HEIGHT: Record<number, number> = { 3: 500, 4: 800, 5: 1600 };
const yy = (b: Bird) => { const r = (b.rings || []).find((x) => x.type === 'FCI') || (b.rings || [])[0]; return r && r.year ? String(r.year).slice(-2) : ''; };
const Plate = ({ b }: { b: Bird }) => { const raw = primaryRing(b); return raw ? <span className={s.plate}><span className={s.yr}>{yy(b)}</span><span className={s.no}>{raw}</span></span> : null; };

export default function PedigreeView() {
  const params = useSearchParams(); const router = useRouter();
  const id = params.get('id') || '';
  const want = +(params.get('gens') || 4);
  const [gens, setGens] = useState<number>(GENS.includes(want as 3 | 4 | 5) ? want : 4);
  const [booted, setBooted] = useState(false);
  const [q, setQ] = useState(''); const [otherId, setOtherId] = useState<string | null>(null);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const bird = useZajilStore(selectBird(id)) as Bird | null;
  const birds = useZajilStore(selectBirds) as Bird[];
  const st = useZajilStore((x) => x);
  useEffect(() => { if (booted && !bird) router.replace('/birds'); }, [booted, bird, router]);   // pedigree.js:21
  if (!booted || !bird) return <section className={s.screen}><Loading /></section>;

  const depth = +((st.settings as Record<string, unknown>).coiDepth || 10);
  const grid = pedigreeGrid(getBird, id, gens) as Slot[][];
  const grid4 = pedigreeGrid(getBird, id, 4) as Slot[][];
  const coi = (inbreeding(getBird, id, depth) as { coi: number }).coi;
  const loss4 = ancestorLoss(getBird, id, 4) as { filled: number; total: number };
  const avk = ancestorLoss(getBird, id, 5) as { avk: number; completeness: number };
  let complete = 0; for (let g = 1; g < grid4.length; g++) { if (grid4[g].every((x) => x && x.bird)) complete = g; else break; }
  const seen = new Map<string, number>(); for (let g = 1; g < grid.length; g++) for (const x of grid[g]) if (x) seen.set(x.id, (seen.get(x.id) || 0) + 1);
  const isCommon = (bid: string) => (seen.get(bid) || 0) > 1;
  const br = bird.sireId && bird.damId ? (coiBreakdown(getBird, bird.sireId, bird.damId, depth) as { coi: number; contributions: Contribution[]; truncated?: boolean }) : null;
  const loft = db.currentLoft() as { name?: string } | null;
  const rulerLabel = (g: number) => g === 0 ? t('ped.subject') : g === 1 ? t('ped.gen.parents') : g === 2 ? t('ped.gen.grand') : g === 3 ? t('ped.gen.great') : g === 4 ? t('ped.gen.fifth') : t('ped.gen.nth', { n: fmtNum(g + 1, { group: false }) });
  const share = () => db.exportBirdWithAncestry(id, { includeRaces: true, includeMedia: true }).then((payload: unknown) => { downloadJSON(payload, `zajil-bird-${primaryRing(bird).replace(/[^\w-]+/g, '_') || id.slice(0, 8)}.json`); toast(t('toast.exported'), { kind: 'success' }); });

  // finder (pedigree.js:133) — the same candidate rules as the form's picker
  const rk = ringKey(q); const needle = q.trim().toLowerCase();
  const cands = needle ? birds.filter((b) => b.id !== id && ((b.name || '').toLowerCase().includes(needle) || (b.strain || '').toLowerCase().includes(needle) || (rk && (b.rings || []).some((r) => ringKey(r as never).includes(rk))))).slice(0, 30) : [];
  const rel = otherId ? (describeRelationship(getBird, id, otherId, depth) as { key: string; params: Record<string, unknown>; hypotheticalCOI: number }) : null;
  const level = rel ? (pairingWarningLevel(rel.hypotheticalCOI) as string) : null;

  const Node = ({ slot, g, i }: { slot: Slot; g: number; i: number }): ReactNode => {
    const size = s['n' + (g + 1)] || s.n6;
    const b = slot?.bird;
    if (!b) {
      // an unknown ancestor: the spec's slot offers «add» — the port opens the CHILD's edit form, where the parent is picked or created
      const child = g > 0 ? grid[g - 1][Math.floor(i / 2)] : null;
      const inner = <><span>{t('ped.unknownAncestor')}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg></>;
      return child && child.bird
        ? <Link href={`/bird/edit?id=${child.id}`} className={`${s.node} ${size} ${s.unknown}`} aria-label={t('ped.unknown.add')} data-testid="node" data-gen={g} data-known="0">{inner}</Link>
        : <span className={`${s.node} ${size} ${s.unknown}`} data-testid="node" data-gen={g} data-known="0">{inner}</span>;
    }
    const name = <bdi>{b.name || primaryRing(b) || b.id.slice(0, 8)}</bdi>;
    return (
      <Link href={`/bird?id=${b.id}`} className={`${s.node} ${size}`} data-testid={g === 0 ? 'node-subject' : 'node'} data-gen={g} data-known="1" data-common={isCommon(b.id) ? '1' : undefined}>
        {g === 0 ? <><span className={s.nm}>{name}</span><Plate b={b} />{b.hatchDate && <span className={s.dt}>{fmtDate(b.hatchDate)}</span>}</>
          : <>{isCommon(b.id) ? <span className={s.ci}><i className={s.dot} /><span className={s.nm}>{name}</span></span> : <span className={s.nm}>{name}</span>}<span className={s.rg}>{primaryRing(b)}</span></>}
      </Link>
    );
  };

  return (
    <section className={s.screen}>
      <div className={s.top}><div className={s.bar}>
        <Link href={`/bird?id=${id}`} className={s['icon-btn']} aria-label={t('act.back')} data-testid="back-link"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg></Link>
        <span className={s.crumb} data-testid="crumb"><bdi>{bird.name || primaryRing(bird) || id.slice(0, 8)}</bdi></span>
        <div className={s.topicons}>
          <button type="button" className={s['icon-btn']} aria-label={t('act.share')} onClick={share} data-testid="share-btn"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg></button>
          <button type="button" className={s['icon-btn']} aria-label={t('act.print')} onClick={() => window.print()} data-testid="print-btn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="7" /></svg></button>
        </div>
      </div></div>
      <div className={s.headwrap}><div className={s.head}>
        <div>
          <div className={s.eyebrow}>{loft?.name || t('loft.unnamed')} · {seasonLabel()}</div>
          <h1>{t('ped.title')}</h1>
          <div className={s.subject} data-testid="subject"><span className={s.nm}><bdi>{bird.name || primaryRing(bird) || id.slice(0, 8)}</bdi></span><Plate b={bird} /><span className={s.sex}>{t('sex.' + (bird.sex || 'unknown'))}</span></div>
        </div>
        <div className={s.tiles}>
          <div className={s.tile} data-testid="tile-coi"><div className={s.n}><COIValue coi={coi} mono={false} /></div><div className={s.l}>{t('tile.coi')}</div></div>
          <div className={s.tile} data-testid="tile-ancestors"><div className={s.n}>{fmtNum(loss4.filled)}</div><div className={s.l}>{t('ped.tile.ancestors', { total: fmtNum(loss4.total) })}</div></div>
          <div className={s.tile} data-testid="tile-complete"><div className={s.n}>{fmtNum(complete)}</div><div className={s.l}>{t('ped.tile.complete')}</div></div>
        </div>
        <div className={s.actions}>
          <button type="button" className={`${s.btn} ${s['btn-outline']}`} onClick={() => window.print()}>{t('act.print')}</button>
          <button type="button" className={`${s.btn} ${s['btn-outline']}`} onClick={share}>{t('act.share')}</button>
          <Link href={`/cert?id=${id}`} className={`${s.btn} ${s['btn-primary']}`} data-testid="hero-cert">{t('act.certificate')}</Link>
        </div>
      </div></div>
      <SyncRow />
      <div className={s.body}>
        <div className={s.legend}><span>{t('ped.legend.order')}</span><span><i className={s.dot} />{t('ped.legend.common')}</span><span><i className={s.dash} />{t('ped.legend.unknown')}</span></div>
        <div className={s.gensel} role="group" aria-label={t('ped.generations')} data-testid="gensel">
          {GENS.map((g) => <button key={g} type="button" aria-pressed={gens === g} onClick={() => setGens(g)} data-testid="gen-btn" data-gens={g}>{fmtNum(g, { group: false })}</button>)}
        </div>
        <div className={s.hint}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16M14 6l6 6-6 6" /></svg>{t('ped.hint.scroll')}</div>
        <div className={s.chartwrap}><div className={`${s.chart} ${gens === 5 ? s.deep : gens === 3 ? s.shallow : ''}`} data-testid="chart">
          <div className={s.ruler}>{grid.map((_, g) => <div key={g} data-testid="ruler-label">{rulerLabel(g)}</div>)}</div>
          <div className={s.gens} style={{ height: HEIGHT[gens] }}>
            <div className={`${s.gen} ${s.g1}`}><Node slot={grid[0][0]} g={0} i={0} /></div>
            {grid.slice(1).map((col, gi) => {
              const g = gi + 1; const pairs = [];
              for (let i = 0; i < col.length; i += 2) pairs.push(<div key={i} className={s.pair}><div className={s.slot}><Node slot={col[i]} g={g} i={i} /></div><div className={s.slot}><Node slot={col[i + 1]} g={g} i={i + 1} /></div></div>);
              return <div key={g} className={`${s.gen} ${s['g' + (g + 1)] || s.g6}`}>{pairs}</div>;
            })}
          </div>
        </div></div>

        {/* carried from pedigree.js:90-160 — the COI panel and the relationship finder */}
        <div className={s.cards}>
          <div className={s.card} data-testid="coi-card">
            <h2>{t('ped.coi')}</h2>
            {!br ? <p className={s.muted}>{t('ped.noCommonAncestors')}</p> : (
              <>
                <p data-testid="coi-headline">{t('ped.coiAtN', { n: fmtNum(depth) })}: <COIValue coi={br.coi} /></p>
                <p className={s.muted}>{t('ped.coiCaveat')}</p>
                <p><b>{t('ped.avk')}:</b> {fmtPercent(avk.avk / 100, 1)} <span className={s.muted}>({t('ped.completeness')}: {fmtPercent(avk.completeness / 100, 0)})</span></p>
                <p className={s.muted}>{t('ped.avkHint')}</p>
                {br.truncated && <p>{t('ped.breakdownTruncated')}</p>}
                {br.contributions.length ? (
                  <>
                    <p><b>{t('ped.breakdown')}</b></p>
                    <div className={s.tbl}><table>
                      <thead><tr><th>{t('ped.commonAncestor')}</th><th className={s.num}>{t('ped.pathPairs')}</th><th className={s.num}>{t('ped.ancestorF')}</th><th className={s.num}>{t('ped.contribution')}</th></tr></thead>
                      <tbody>{br.contributions.map((c) => { const a = getBird(c.ancestorId); return (
                        <tr key={c.ancestorId} data-testid="breakdown-row">
                          <td>{a ? <Link href={`/bird?id=${c.ancestorId}`}><BirdLabel bird={a} /></Link> : c.ancestorId.slice(0, 8)}</td>
                          <td className={s.num}>{fmtNum(c.nPathPairs)}</td><td className={s.num}>{fmtPercent(c.ancestorF, 1)}</td><td className={s.num}>{fmtPercent(c.contribution, 2)}</td>
                        </tr>); })}</tbody>
                    </table></div>
                  </>
                ) : <p className={s.muted}>{t('ped.noCommonAncestors')}</p>}
              </>
            )}
          </div>
          <div className={`${s.card} ${s.finder}`} data-testid="finder">
            <h2>{t('rel.finder')}</h2>
            <input value={q} onChange={(e) => { setQ(e.target.value); setOtherId(null); }} placeholder={t('bird.chooseBird')} aria-label={t('rel.finder')} data-testid="finder-input" />
            {!otherId && cands.length > 0 && <div className={s.list}>{cands.map((c) => <button key={c.id} type="button" onClick={() => { setOtherId(c.id); setQ(birdLabelText(c)); }} data-testid="finder-item"><BirdLabel bird={c} /> <SexChip sex={c.sex} /></button>)}</div>}
            {rel && level && (
              <div className={s.rel} data-testid="rel-result" data-level={level}>
                <p><b>{t('rel.title')}:</b> <span data-testid="rel-key">{t(rel.key, rel.params)}</span></p>
                <p>{t('rel.hypCOI')}: <COIValue coi={rel.hypotheticalCOI} /></p>
                <span className={`${s.lvl} ${s[level]}`}>{t('rel.warn.' + level, { coi: fmtPercent(rel.hypotheticalCOI, 2) })}</span>
              </div>
            )}
          </div>
        </div>
      </div>
      <div className={s.cta} data-bottom-chrome="cta"><Link href={`/cert?id=${id}`} data-testid="cta-cert">{t('act.certificate')}</Link></div>
    </section>
  );
}
