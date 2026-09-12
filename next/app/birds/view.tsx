'use client';
import { useMemo, useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectBirds } from '@/src/db/react';
import { t, fmtNum, statusLabel } from '@/src/i18n.ext.js';
import { ringKey } from '@/src/engine/rings.js';
import { SyncRow, Empty, toast, primaryRing, seasonLabel, initDB } from '@/src/components';
import sh from '@/src/components/shared.module.css';
import s from './birds.module.css';

// Loft home — design/approved/loft-home-v1.html, behaviour from js/views/birds.js.
// Spec wins on presentation: pills instead of the four selects, a count line,
// generation groups on the phone, a sortable table on desktop (ruling 6), one
// example loader in the empty state. Vanilla wins on wiring: the search fields
// and ring normalisation, the facade calls, the example-load toast.
type Ring = { raw?: string; type?: string };
type Bird = { id: string; name?: string; sex?: string; status?: string; hatchDate?: string; strain?: string; colour?: string; eyeSign?: string; breeder?: string; owner?: string; acquiredFrom?: string; createdAt?: string; external?: boolean; rings?: Ring[]; notes?: Array<{ text?: string }> };
type Race = { birdId: string; date?: string; raceName?: string; position?: number | null; releasePoint?: { name?: string } | null };
type Row = { b: Bird; name: string; ring: string; year: string; sexK: 'm' | 'f' | 'u'; stK: 'race' | 'breed' | 'gone' | 'active'; stLabel: string; last: { w: string; pl: number } | null };
type SortKey = 'ring' | 'name' | 'sex' | 'status' | 'year' | 'res';

// Spec STATUS styles by category; labels stay vanilla's (statusLabel) — the
// spec's «نشط» is not a vanilla status, so stock / young bird / reference keep
// their own words inside the spec's neutral pill. Recorded in the commit.
const stKind = (st?: string): Row['stK'] => st === 'race team' ? 'race' : st === 'breeder' ? 'breed' : (st === 'sold' || st === 'lost' || st === 'dead') ? 'gone' : 'active';
const sexKind = (sx?: string): Row['sexK'] => sx === 'cock' ? 'm' : sx === 'hen' ? 'f' : 'u';
const sexIcon = { m: '♂', f: '♀', u: '?' } as const;
const sexKey = { m: 'sex.cock', f: 'sex.hen', u: 'sex.unknown' } as const;
// js/views/birds.js searchText, verbatim in spirit: every free-text field + rings + notes
const searchText = (b: Bird) => [b.name, b.strain, b.colour, b.eyeSign, b.breeder, b.owner, b.acquiredFrom, ...(b.rings || []).map((r) => r.raw), ...(b.notes || []).map((n) => n.text)].filter(Boolean).join(' ').toLowerCase();

/** js/views/birds.js loadExample — merge, never destroy. */
async function loadExample(file: string) {
  const payload = await (await fetch(file)).json();
  const counts = await db.importAll(payload, 'merge');
  toast(t('bird.exampleLoaded', { n: counts.birds }), { timeout: 7000, kind: 'info' });
}

export default function BirdsView() {
  // the desktop table row navigates through the router, like every Link in the app: a raw
  // `location.href = '/bird?id='` is not rewritten by basePath and does not resolve on a
  // plain file server, where the document is bird.html (found in the Phase 5 survey)
  const router = useRouter();
  const birds = useZajilStore(selectBirds) as Bird[];
  const version = useZajilStore(() => db.state);          // races change too
  const [q, setQ] = useState(''); const [filter, setFilter] = useState<string>('all'); const [year, setYear] = useState<string | null>(null);
  const [sortK, setSortK] = useState<SortKey>('year'); const [desc, setDesc] = useState(true);
  const [booted, setBooted] = useState(false);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);

  const rows = useMemo<Row[]>(() => {
    const lastByBird = new Map<string, Race>();
    for (const r of (version.raceResults as Map<string, Race>).values()) {
      const prev = lastByBird.get(r.birdId); if (!prev || (r.date || '') > (prev.date || '')) lastByBird.set(r.birdId, r);
    }
    return birds.map((b) => {
      const lr = lastByBird.get(b.id);
      return { b, name: b.name || '', ring: primaryRing(b), year: b.hatchDate ? b.hatchDate.slice(0, 4) : '—', sexK: sexKind(b.sex), stK: stKind(b.status), stLabel: statusLabel(b.status || ''),
        last: lr && lr.position ? { w: lr.raceName || lr.releasePoint?.name || '', pl: lr.position } : null };
    });
  }, [birds, version]);
  const years = useMemo(() => [...new Set(rows.map((r) => r.year).filter((y) => y !== '—'))].sort().reverse(), [rows]);
  const filtered = useMemo(() => {
    let rs = rows;
    const qq = q.trim().toLowerCase();
    if (qq) { const rk = ringKey(qq); rs = rs.filter((r) => searchText(r.b).includes(qq) || (rk && (r.b.rings || []).some((x) => ringKey(x as never).includes(rk)))); }
    if (filter === 'm' || filter === 'f') rs = rs.filter((r) => r.sexK === filter);
    if (filter === 'race' || filter === 'breed') rs = rs.filter((r) => r.stK === filter);
    if (filter === 'ext') rs = rs.filter((r) => !!r.b.external);          // birds.js:37 — ruling 14 (4A): kit over spec
    if (year) rs = rs.filter((r) => r.year === year);
    return rs;
  }, [rows, q, filter, year]);
  const sorted = useMemo(() => {
    const key: Record<SortKey, (r: Row) => string | number> = { ring: (r) => r.ring, name: (r) => r.name, sex: (r) => r.sexK, status: (r) => r.stLabel, year: (r) => r.year, res: (r) => (r.last ? r.last.pl : 999) };
    const k = key[sortK];
    return [...filtered].sort((a, b) => { const x = k(a), y = k(b); return (x > y ? 1 : x < y ? -1 : 0) * (desc ? -1 : 1); });
  }, [filtered, sortK, desc]);
  const groups = useMemo(() => { const g = new Map<string, Row[]>(); for (const r of [...filtered].sort((a, b) => (b.b.createdAt || '').localeCompare(a.b.createdAt || ''))) { (g.get(r.year) ?? g.set(r.year, []).get(r.year)!).push(r); } return [...g.entries()].sort((a, b) => (b[0] > a[0] ? 1 : -1)); }, [filtered]);

  const m = rows.filter((r) => r.sexK === 'm').length, f = rows.filter((r) => r.sexK === 'f').length;
  const loft = db.currentLoft() as { name?: string } | null;
  const empty = booted && rows.length === 0;
  const onSort = (k: SortKey) => { if (k === sortK) setDesc(!desc); else { setSortK(k); setDesc(k === 'year' || k === 'res'); } };
  const pill = (label: string, active: boolean, onClick: () => void, extra: Record<string, string> = {}) => (
    <button key={label + JSON.stringify(extra)} type="button" className={`${s.fp} ${active ? s.on : ''}`} onClick={onClick} data-testid="filter-pill" {...extra}>{label}</button>
  );
  const Plate = ({ ring }: { ring: string }) => <span className={s.plate}><span className={s.yr}>{ring.split(' ')[1] ?? ''}</span><span className={s.no}>{ring}</span></span>;
  const Sx = ({ k }: { k: Row['sexK'] }) => <span className={`${s.sx} ${s[k]}`} data-sex={k === 'm' ? 'cock' : k === 'f' ? 'hen' : 'unknown'} aria-label={t(sexKey[k])}><span className={s.g}>{sexIcon[k]}</span>{t(sexKey[k])}</span>;
  const St = ({ r }: { r: Row }) => <span className={`${s.st} ${s[r.stK]}`} data-testid="status-pill">{r.stLabel}</span>;
  // birds.js:102 chip-ext — the external marker, ruled in at 4A acceptance (kit over spec: reference birds are a real feature)
  const Ext = () => <span className={s.ext} data-testid="ext-tag">{t('bird.externalShort')}</span>;
  const Res = ({ r }: { r: Row }) => r.last ? <span className={s.res}><span className={`${s.pl} ${r.last.pl <= 10 ? s.top : ''}`}>{fmtNum(r.last.pl, { group: false })}</span><span className={s.w}>{r.last.w}</span></span> : <span className={`${s.res} ${s.none}`}>{t('race.noneShort')}</span>;

  return (
    <section className={s.screen}>
      <div className={s.lofthead}>
        <div className={s.headrow}>
          <div><div className={s.eyebrow} data-testid="season-eyebrow">{seasonLabel()}</div><h1>{loft?.name || t('loft.unnamed')}</h1>
            <div className={s.count} data-testid="count-line">{empty ? t('empty.firstRun.title') : !booted ? '' : t('loft.countLine', { n: fmtNum(rows.length), m: fmtNum(m), f: fmtNum(f) })}</div></div>
          {!empty && booted && (
            <div className={s.tools}>
              <label className={s.search}><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('loft.search.placeholder')} aria-label={t('act.search')} data-testid="search-input" /></label>
              <Link href="/bird/new" className={s['btn-add']} data-testid="add-bird">{t('act.newBird')}</Link>
            </div>
          )}
        </div>
      </div>
      {!booted ? null : empty ? (
        <Empty title={t('empty.firstRun.cta')} body={t('empty.loft.body')}
          cta={{ label: t('empty.firstRun.cta'), href: '/bird/new', testid: 'empty-cta' }}
          alt={{ label: t('empty.example.cta'), onClick: () => loadExample('./example-loft-large.json'), testid: 'empty-example' }}
          hint={t('empty.example.hint', { n: fmtNum(38) })} />
      ) : (
        <div>
          <div className={s.filters} role="group">
            {pill(t('common.all'), filter === 'all' && !year, () => { setFilter('all'); setYear(null); }, { 'data-filter': 'all' })}
            {pill(t('filter.males'), filter === 'm', () => { setFilter('m'); setYear(null); }, { 'data-filter': 'm' })}
            {pill(t('filter.females'), filter === 'f', () => { setFilter('f'); setYear(null); }, { 'data-filter': 'f' })}
            {pill(statusLabel('race team'), filter === 'race', () => { setFilter('race'); setYear(null); }, { 'data-filter': 'race' })}
            {pill(statusLabel('breeder'), filter === 'breed', () => { setFilter('breed'); setYear(null); }, { 'data-filter': 'breed' })}
            {pill(t('filter.externalOnly'), filter === 'ext', () => { setFilter('ext'); setYear(null); }, { 'data-filter': 'ext' })}
            {years.map((y) => pill(y, year === y, () => { setYear(year === y ? null : y); setFilter('all'); }, { 'data-year': y }))}
          </div>
          <SyncRow />
          <div className={s.list} data-testid="bird-list">
            {groups.length === 0 ? <div className={s.yearlbl} data-testid="year-label"><span className={s.y}>{t('loft.noResults')}</span></div> : groups.map(([y, rs]) => (
              <div key={y}>
                <div className={s.yearlbl} data-testid="year-label"><span className={s.y}>{t('loft.generation', { y })}</span><span className={s.c}>{fmtNum(rs.length)}</span></div>
                {rs.map((r) => (
                  <Link key={r.b.id} href={`/bird?id=${r.b.id}`} className={`${s.brow} ${r.stK === 'gone' ? s.gone : ''}`} data-testid="bird-row">
                    <span className={s.mid}><span className={s.nm}>{r.name || r.ring || r.b.id.slice(0, 8)}</span><span className={s.sub}>{r.ring && <Plate ring={r.ring} />}<Sx k={r.sexK} /><St r={r} />{r.b.external && <Ext />}</span></span>
                    <svg className={s.chev} viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
                  </Link>
                ))}
              </div>
            ))}
          </div>
          <div className={s.table}>
            <table>
              <thead><tr>
                {([['ring', 'col.ring'], ['name', 'bird.name'], ['sex', 'bird.sex'], ['status', 'bird.status'], ['year', 'col.generation'], ['res', 'col.lastResult']] as Array<[SortKey, string]>).map(([k, key]) => (
                  <th key={k} className={sortK === k ? s.on : ''} onClick={() => onSort(k)} data-testid="th-sort" data-key={k} aria-sort={sortK === k ? (desc ? 'descending' : 'ascending') : 'none'}><span>{t(key)}</span></th>
                ))}
              </tr></thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.b.id} tabIndex={0} className={r.stK === 'gone' ? s.gone : ''} data-testid="table-row" onClick={() => router.push(`/bird?id=${r.b.id}`)}>
                    <td className={s.ltr}>{r.ring ? <Plate ring={r.ring} /> : '—'}</td>
                    <td className={s.nm} data-testid="cell-name">{r.name}{r.b.external && <> <Ext /></>}</td>
                    <td><Sx k={r.sexK} /></td>
                    <td><St r={r} /></td>
                    <td className={`${s.yr} ${s.ltr}`}>{r.year}</td>
                    <td><Res r={r} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={s.fab} data-bottom-chrome="fab" data-testid="fab-add"><Link href="/bird/new"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>{t('act.newBird')}</Link></div>
        </div>
      )}
      <span className={sh.muted} hidden>{version ? '' : ''}</span>
    </section>
  );
}
