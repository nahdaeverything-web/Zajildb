'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectPairs } from '@/src/db/react';
import { t, fmtNum } from '@/src/i18n.ext.js';
import { SyncRow, Loading } from '@/src/components';
import { type Pair, Names, Plates, StatusChip, Summary, Chev, Plus, NewPairSheet, seasonOptions, currentYear } from './shared';
import s from './breeding.module.css';

// Breeding, level 1 — the pair list for a season (breeding-v1 «الأزواج»):
// header with the loft and the season select, rows on the phone, a table at
// ≥1100, the empty state, the FAB. Rows open the pair detail at /pair?id=
// (the spec's second level as a route — design/README.md, breeding note 1).
export default function BreedingView() {
  const params = useSearchParams(); const router = useRouter();
  const [booted, setBooted] = useState(false);
  const [season, setSeason] = useState(params.get('season') || currentYear());
  const [sheet, setSheet] = useState(false);
  useEffect(() => { db.initDB().then(() => setBooted(true)); }, []);
  const pairs = useZajilStore(selectPairs) as Pair[];
  useZajilStore((x) => x.birds.size);   // names / plates come from the birds
  if (!booted) return <section className={s.screen}><Loading /></section>;
  const seasons = seasonOptions(pairs, currentYear());
  const vis = pairs.filter((p) => p.season === season).sort((a, b) => (a.nestBox || '').localeCompare(b.nestBox || '', undefined, { numeric: true }));   // breeding.js:34
  const loft = db.currentLoft() as { name?: string } | null;
  const active = vis.filter((p) => p.status === 'active').length;
  return (
    <section className={s.screen}>
      <header className={s.lofthead}><div className={s.in}><div className={s.headrow}>
        <div>
          <div className={s.loft} data-testid="crumb">{loft?.name || t('loft.unnamed')}</div>
          <h1>{t('br.title')}</h1>
          {vis.length > 0 && <div className={s.count} data-testid="count-line">{t('br.countLine', { n: fmtNum(vis.length), m: fmtNum(active) })}</div>}
          <div className={s.seasonrow} data-testid="season-row">
            <span className={s.k}>{t('br.season')}:</span>
            <span className={s.selwrap}><select value={season} onChange={(e) => { setSeason(e.target.value); router.replace(`/breeding?season=${e.target.value}`); }} aria-label={t('br.season')} data-testid="season-select">{seasons.map((y) => <option key={y} value={y}>{y}</option>)}</select></span>
          </div>
        </div>
        <button type="button" className={s['btn-add']} onClick={() => setSheet(true)} data-testid="new-pair-desktop"><Plus />{t('br.newPair')}</button>
      </div></div></header>
      <SyncRow />
      <section className={s.panel}>
        {vis.length === 0 ? (
          <div className={s.empty} data-testid="empty-state">
            <div className={s.ico}><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="12" r="5" /><circle cx="15" cy="12" r="5" /></svg></div>
            <h3>{t('br.noPairs')}</h3><p>{t('br.empty.body')}</p>
          </div>
        ) : (
          <>
            <div className={s.rows} data-testid="pair-rows">
              {vis.map((p) => (
                <Link key={p.id} href={`/pair?id=${p.id}`} className={`${s.row} ${p.status === 'active' ? '' : s.off}`} data-testid="pair-row">
                  <div className={s.body}><Names p={p} /><Plates p={p} />
                    <div className={s.meta}><span className={s.chip}>{t('br.nestBox')} <b>{p.nestBox || '—'}</b></span><StatusChip p={p} /><Summary p={p} /></div></div>
                  <Chev />
                </Link>
              ))}
            </div>
            <div className={s.table} data-testid="pair-table">
              <table>
                <thead><tr><th>{t('br.pair')}</th><th>{t('br.nestBox')}</th><th>{t('bird.status')}</th><th>{t('br.progress')}</th><th /></tr></thead>
                <tbody>{vis.map((p) => (
                  <tr key={p.id} tabIndex={0} onClick={() => router.push(`/pair?id=${p.id}`)} onKeyDown={(e) => { if (e.key === 'Enter') router.push(`/pair?id=${p.id}`); }} data-testid="pair-tr">
                    <td><Names p={p} /><Plates p={p} /></td><td className={s.nest}>{p.nestBox || '—'}</td><td><StatusChip p={p} /></td><td><Summary p={p} /></td><td><Chev /></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </section>
      <div className={s.fab}><button type="button" onClick={() => setSheet(true)} data-testid="new-pair-fab"><Plus />{t('br.newPair')}</button></div>
      {sheet && <NewPairSheet season={season} seasons={seasons} onClose={() => setSheet(false)} onSaved={(id) => { setSheet(false); router.push(`/pair?id=${id}`); }} />}
    </section>
  );
}
