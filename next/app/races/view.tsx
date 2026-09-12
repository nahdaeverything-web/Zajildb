'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectRaces, selectBirds } from '@/src/db/react';
import { t, fmtDate, fmtNum } from '@/src/i18n.ext.js';
import { resultQualifies, birdEligibility, FCI_MIN_FANCIERS, FCI_MIN_BIRDS } from '@/src/engine/fci.js';
import { velocityMPM, haversineMetres } from '@/src/engine/velocity.js';
import { SyncRow, Loading, toast, undoToast, primaryRing, seasonLabel, seasonStart, pickerModel, SexChip, Tpl, initDB } from '@/src/components';
import s from './races.module.css';

// Races — design/approved/races-v1.html, behaviour from js/views/races.js.
// Spec wins on presentation: the season header and count line, two tabs, phone
// rows grouped by date with an inline delete confirm, a desktop table, the FCI
// checker as cards on the phone and a table on desktop, the result sheet with
// its two groups and the coordinate calculator. Spec also wins on VALIDATION:
// design/README.md rules that races-v1 deliberately replaces two silent
// failures — a save that returns false when no bird is chosen, and a calculate
// that gives up on unparseable coordinates — with visible inline errors, a
// field-level message, an alert banner and a scroll back to the first bad
// field. Vanilla wins on wiring: Races.save / Races.remove / Races.restore
// through the facade, the engine's haversine + velocity, resultQualifies and
// birdEligibility, and setSetting('loftCoords') so the loft's coordinates are
// remembered between results.
type Ring = { raw?: string; type?: string; year?: number | string | null };
type Bird = { id: string; name?: string; sex?: string; strain?: string; rings?: Ring[] };
type Point = { name?: string; lat?: number; lon?: number } | null;
type Race = { id: string; birdId: string; date?: string; raceName?: string; raceType?: string; organisation?: string; country?: string;
  position?: number | null; fanciersEntered?: number | null; birdsEntered?: number | null;
  releasePoint?: Point; loftPoint?: Point; releaseTime?: string | null; arrivalTime?: string | null; distanceKm?: number | null; velocity?: number | null };
const RACE_TYPES = ['training', 'club', 'federation', 'national', 'one-loft', 'international'];
const Races = db.Races as { save: (r: Race) => Promise<Race>; remove: (id: string) => Promise<Race>; restore: (r: Race) => Promise<void> };
const getBird = (id: string) => db.getBird(id) as Bird | undefined;
const nameOf = (b?: Bird) => (b ? (b.name || primaryRing(b) || b.id.slice(0, 8)) : '—');
const yy = (b: Bird) => { const r = (b.rings || []).find((x) => x.type === 'FCI') || (b.rings || [])[0]; return r && r.year ? String(r.year).slice(-2) : ''; };
/** races.js:135 parseCoords — two numbers, any separator. */
const parseCoords = (v: string) => { const m = String(v || '').trim().match(/(-?\d+(?:\.\d+)?)[\s,،;]+(-?\d+(?:\.\d+)?)/); return m && Math.abs(+m[1]) <= 90 && Math.abs(+m[2]) <= 180 ? { lat: +m[1], lon: +m[2] } : null; };
const Plus = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>;

export default function RacesView() {
  const params = useSearchParams();
  const [booted, setBooted] = useState(false);
  const [tab, setTab] = useState<'log' | 'fci'>(params.get('tab') === 'fci' ? 'fci' : 'log');
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [sheet, setSheet] = useState<{ editing: Race | null } | null>(null);
  // ruling 3: the log shows the season the header states. 'all' is the way out of that filter.
  const [season, setSeason] = useState<string>(params.get('season') || String(seasonStart()));
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const races = useZajilStore(selectRaces) as Race[];
  const birds = useZajilStore(selectBirds) as Bird[];
  if (!booted) return <section className={s.screen}><Loading /></section>;

  const sorted = [...races].sort((a, b) => (b.date || '').localeCompare(a.date || ''));   // races.js:48
  const seasons = [...new Set(sorted.map((r) => (r.date ? seasonStart(r.date) : 0)).filter(Boolean))].sort((a, b) => b - a).map(String);
  const results = season === 'all' ? sorted : sorted.filter((r) => r.date && String(seasonStart(r.date)) === season);
  const empty = results.length === 0;
  const loft = db.currentLoft() as { name?: string } | null;
  const nBirds = new Set(results.map((r) => r.birdId)).size;

  // races.js:88 — a bird appears in the checker once it has an FCI ring or any result
  const fciRows = birds.map((b) => ({ b, e: birdEligibility(b, sorted.filter((r) => r.birdId === b.id)) as { hasRing: boolean; qualifyingResults: Race[]; nonQualifying: Array<{ result: Race; reasons: string[] }> } }))
    .filter(({ b, e }) => e.hasRing || sorted.some((r) => r.birdId === b.id))
    .sort((x, y) => (y.e.hasRing ? 1 : 0) - (x.e.hasRing ? 1 : 0) || y.e.qualifyingResults.length - x.e.qualifyingResults.length);

  async function del(r: Race) {
    setConfirmId(null);
    const snap = await Races.remove(r.id);
    undoToast(t('toast.deleted'), t('act.undo'), async () => { await Races.restore(snap); toast(t('toast.undone'), { kind: 'success' }); });
  }
  const Pill = ({ pos }: { pos?: number | null }) => pos ? <span className={`${s.pill} ${pos <= 10 ? s.top : ''}`} data-testid="pos-pill">{fmtNum(pos, { group: false })}</span> : <span className={`${s.pill} ${s.none}`} data-testid="pos-pill">—</span>;
  const Fci = ({ on }: { on: boolean }) => <span className={`${s.fci} ${on ? s.on : ''}`} data-testid="fci-chip" data-on={on ? '1' : '0'}>{on ? '✓' : '—'}</span>;
  const Type = ({ r }: { r: Race }) => <span className={`${s.type} ${(r.raceType || 'training') === 'training' ? s.train : ''}`} data-testid="type-tag">{t('raceType.' + (r.raceType || 'training'))}</span>;
  const Confirm = ({ r, inCell }: { r: Race; inCell?: boolean }) => (
    <div className={s.confirm} style={inCell ? { margin: 0, padding: '6px 6px 6px 14px' } : undefined} data-testid="inline-confirm">
      <span>{t('confirm.deleteGeneric')}</span>
      <div className={s.b}><button type="button" className={s.no} onClick={() => setConfirmId(null)} data-testid="confirm-no">{t('act.cancel')}</button><button type="button" className={s.go} onClick={() => del(r)} data-testid="confirm-go">{t('act.delete')}</button></div>
    </div>
  );
  const Acts = ({ r, end }: { r: Race; end?: boolean }) => (
    <div className={s.acts} style={end ? { justifyContent: 'flex-end' } : undefined}>
      <button type="button" className={s.act} onClick={() => setSheet({ editing: r })} data-testid="race-edit">{t('act.edit')}</button>
      <button type="button" className={`${s.act} ${s.x}`} aria-label={t('act.delete')} onClick={() => setConfirmId(r.id)} data-testid="race-delete">✕</button>
    </div>
  );

  let lastDate: string | null = null;
  return (
    <section className={s.screen}>
      <header className={s.lofthead}><div className={s.in}><div className={s.headrow}>
        <div>
          <div className={s.season} data-testid="season-line">{season === 'all' ? t('race.allSeasons') : seasonLabel(`${season}-07-01`)} · {loft?.name || t('loft.unnamed')}</div>
          <h1>{t('nav.races')}</h1>
          <div className={s.count} data-testid="count-line">{empty ? t('race.noneThisSeason') : t('race.countLine', { n: fmtNum(results.length), b: fmtNum(nBirds) })}</div>
          {tab === 'log' && (
            <div className={s.seasonrow} data-testid="season-row">
              <span className={s.k}>{t('br.season')}:</span>
              <span className={s.selwrap}><select value={season} onChange={(e) => setSeason(e.target.value)} aria-label={t('br.season')} data-testid="season-select">
                <option value={String(seasonStart())}>{seasonLabel()}</option>
                {seasons.filter((y) => y !== String(seasonStart())).map((y) => <option key={y} value={y}>{seasonLabel(`${y}-07-01`)}</option>)}
                <option value="all">{t('race.allSeasons')}</option>
              </select></span>
            </div>
          )}
        </div>
        <button type="button" className={s['btn-add']} onClick={() => setSheet({ editing: null })} data-testid="new-result-desktop"><Plus />{t('race.new')}</button>
      </div></div></header>
      <SyncRow />
      <nav className={s.seg} role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'log'} aria-controls="p-log" onClick={() => setTab('log')} data-testid="tab-log">{t('race.title')}</button>
        <button type="button" role="tab" aria-selected={tab === 'fci'} aria-controls="p-fci" onClick={() => setTab('fci')} data-testid="tab-fci">{t('fci.title')}</button>
      </nav>

      <section className={s.panel} id="p-log" role="tabpanel" hidden={tab !== 'log'} data-testid="panel-log">
        {empty ? (
          <div className={s.empty} data-testid="log-empty">
            <div className={s.ico}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3" /></svg></div>
            <h3>{t('race.noRaces')}</h3><p>{t('race.empty.body')}</p>
          </div>
        ) : (
          <>
            <div className={s.list} data-testid="race-rows">
              {results.map((r) => {
                const head = r.date !== lastDate ? (lastDate = r.date || null, true) : false;
                const b = getBird(r.birdId);
                return (
                  <div key={r.id}>
                    {head && <div className={s.datelbl} data-testid="date-group"><bdi>{fmtDate(r.date)}</bdi></div>}
                    <div className={s.rrow} data-testid="race-row">
                      <div className={s.l1}>
                        <div>
                          <Link href={`/bird?id=${r.birdId}`} className={s.bird} data-testid="row-bird"><bdi>{nameOf(b)}</bdi></Link>
                          <div className={s.race}><bdi>{r.raceName || '—'}</bdi><Type r={r} /></div>
                        </div>
                        <Pill pos={r.position} />
                      </div>
                      <div className={s.l2}>
                        <div className={s.stat}><span className={s.k}>{t('race.km')}</span><span className={`${s.v} ${s.num}`}>{r.distanceKm ? fmtNum(r.distanceKm, { dp: 1 }) : '—'}</span></div>
                        <div className={s.stat}><span className={s.k}>{t('race.mpm')}</span><span className={`${s.v} ${s.num}`}>{r.velocity ? fmtNum(r.velocity, { dp: 0 }) : '—'}</span></div>
                        <div className={s.stat}><span className={s.k}>FCI</span><Fci on={(resultQualifies(r) as { qualifies: boolean }).qualifies} /></div>
                        <Acts r={r} />
                      </div>
                      {confirmId === r.id && <Confirm r={r} />}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className={s.table} data-testid="race-table">
              <table>
                <thead><tr><th>{t('common.date')}</th><th>{t('race.bird')}</th><th>{t('race.name')}</th><th>{t('race.type')}</th><th className={s.num}>{t('race.distance')} {t('race.km')}</th><th className={s.num}>{t('race.velocity')} {t('race.mpm')}</th><th>{t('race.position')}</th><th>FCI</th><th /></tr></thead>
                <tbody>{results.map((r) => (
                  <tr key={r.id} data-testid="race-tr">
                    <td className={s.num}><bdi>{fmtDate(r.date)}</bdi></td>
                    <td><Link href={`/bird?id=${r.birdId}`} className={s.link}><bdi>{nameOf(getBird(r.birdId))}</bdi></Link></td>
                    <td><bdi>{r.raceName || '—'}</bdi></td>
                    <td><Type r={r} /></td>
                    <td className={s.num}>{r.distanceKm ? fmtNum(r.distanceKm, { dp: 1 }) : '—'}</td>
                    <td className={s.num}>{r.velocity ? fmtNum(r.velocity, { dp: 0 }) : '—'}</td>
                    <td><Pill pos={r.position} /></td>
                    <td><Fci on={(resultQualifies(r) as { qualifies: boolean }).qualifies} /></td>
                    <td>{confirmId === r.id ? <Confirm r={r} inCell /> : <Acts r={r} end />}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section className={s.panel} id="p-fci" role="tabpanel" hidden={tab !== 'fci'} data-testid="panel-fci">
        <p className={s.intro} data-testid="fci-rule">{t('fci.rule', { f: fmtNum(FCI_MIN_FANCIERS), b: fmtNum(FCI_MIN_BIRDS) })}</p>
        {fciRows.length === 0 ? (
          <div className={s.empty} data-testid="fci-empty">
            <div className={s.ico}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l4 4L19 7" /></svg></div>
            <h3>{t('common.none')}</h3><p>{t('fci.empty.body')}</p>
          </div>
        ) : (
          <>
            <div className={s.flist} data-testid="fci-cards">
              {fciRows.map(({ b, e }) => (
                <div key={b.id} className={`${s.fcard} ${e.qualifyingResults.length ? s.q : ''}`} data-testid="fci-card" data-qualified={e.qualifyingResults.length ? '1' : '0'}>
                  <div className={s.l1}>
                    <Link href={`/bird?id=${b.id}`} className={s.nm}><bdi>{nameOf(b)}</bdi></Link>
                    <span className={s.ring}>{t('fci.ringShort')} <span className={`${s.fci} ${e.hasRing ? s.on : s.off}`} data-testid="fci-ring" data-on={e.hasRing ? '1' : '0'}>{e.hasRing ? '✓' : '✗'}</span></span>
                  </div>
                  <div className={s.cnt}>
                    <div><div className={`${s.v} ${e.qualifyingResults.length ? s.ok : ''}`} data-testid="fci-q">{fmtNum(e.qualifyingResults.length)}</div><div className={s.k}>{t('fci.qualifying')}</div></div>
                    <div><div className={s.v} style={{ color: 'var(--ink-3)' }} data-testid="fci-nq">{fmtNum(e.nonQualifying.length)}</div><div className={s.k}>{t('fci.nonQualifyingShort')}</div></div>
                  </div>
                  {e.nonQualifying.length > 0 && (
                    <div className={s.why} data-testid="fci-why">
                      {e.nonQualifying.flatMap(({ result, reasons }) => reasons.map((k, i) => (
                        <div key={result.id + i}><b><bdi>{result.raceName || fmtDate(result.date)}</bdi>:</b> {t(k)}</div>
                      )))}
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className={s.table} data-testid="fci-table">
              <table>
                <thead><tr><th>{t('race.bird')}</th><th>{t('fci.hasRing')}</th><th className={s.num}>{t('fci.qualifying')}</th><th>{t('fci.nonQualifying')}</th></tr></thead>
                <tbody>{fciRows.map(({ b, e }) => (
                  <tr key={b.id} className={e.hasRing && e.qualifyingResults.length ? s.q : ''} data-testid="fci-tr">
                    <td><Link href={`/bird?id=${b.id}`} className={s.link}><bdi>{nameOf(b)}</bdi></Link></td>
                    <td><span className={`${s.fci} ${e.hasRing ? s.on : s.off}`} data-on={e.hasRing ? '1' : '0'}>{e.hasRing ? '✓' : '✗'}</span></td>
                    <td className={s.num}><span className={`${s.bigv} ${e.qualifyingResults.length ? s.ok : ''}`} style={e.qualifyingResults.length ? undefined : { color: 'var(--ink-3)' }}>{fmtNum(e.qualifyingResults.length)}</span></td>
                    <td>{e.nonQualifying.length ? (
                      <div className={s.reasons}>{e.nonQualifying.flatMap(({ result, reasons }) => reasons.map((k, i) => (
                        <div key={result.id + i}><b><bdi>{result.raceName || fmtDate(result.date)}</bdi>:</b> {t(k)}</div>
                      )))}</div>
                    ) : <span style={{ color: 'var(--ink-3)' }}>—</span>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <div className={s.fab} data-bottom-chrome="fab"><button type="button" onClick={() => setSheet({ editing: null })} data-testid="new-result-fab"><Plus />{t('race.new')}</button></div>
      {sheet && <ResultSheet editing={sheet.editing} birds={birds} onClose={() => setSheet(null)} />}
    </section>
  );
}

/** The result sheet — races.js:116 resultDialog in races-v1's two groups, with the spec's visible errors. */
function ResultSheet({ editing, birds, onClose }: { editing: Race | null; birds: Bird[]; onClose: () => void }) {
  const r = editing;
  const [birdId, setBirdId] = useState<string | null>(r ? r.birdId : null);
  const [name, setName] = useState(r?.raceName || '');
  const [date, setDate] = useState(r?.date || '');
  const [type, setType] = useState(r?.raceType || 'club');
  const [org, setOrg] = useState(r?.organisation || '');
  const [country, setCountry] = useState(r?.country || '');
  const [pos, setPos] = useState(r?.position ? String(r.position) : '');
  const [fanciers, setFanciers] = useState(r?.fanciersEntered ? String(r.fanciersEntered) : '');
  const [birdsEntered, setBirdsEntered] = useState(r?.birdsEntered ? String(r.birdsEntered) : '');
  const [relName, setRelName] = useState(r?.releasePoint?.name || '');
  const [relCoord, setRelCoord] = useState(r?.releasePoint && r.releasePoint.lat != null ? `${r.releasePoint.lat}, ${r.releasePoint.lon}` : '');
  const [loftCoord, setLoftCoord] = useState(r?.loftPoint && r.loftPoint.lat != null ? `${r.loftPoint.lat}, ${r.loftPoint.lon}` : String((db.state.settings as Record<string, unknown>).loftCoords || ''));
  const [relTime, setRelTime] = useState(r?.releaseTime || '');
  const [arrTime, setArrTime] = useState(r?.arrivalTime || '');
  const [dist, setDist] = useState(r?.distanceKm != null ? String(r.distanceKm) : '');
  const [vel, setVel] = useState(r?.velocity != null ? String(r.velocity) : '');
  const [errs, setErrs] = useState<Record<string, boolean>>({});
  const [alert, setAlert] = useState(false);
  const [calcOk, setCalcOk] = useState<{ km: string; mpm: string } | null>(null);
  const [pickOpen, setPickOpen] = useState(false);
  const [q, setQ] = useState('');
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k); }, [onClose]);

  const bird = birdId ? getBird(birdId) : null;
  const model = pickerModel({ all: birds, pool: birds, q, allowCreate: false, selected: birdId });
  const clearErr = () => { setErrs({}); setAlert(false); };

  function calc() {
    setCalcOk(null);
    const a = parseCoords(relCoord), b = parseCoords(loftCoord);
    const bad = { coords: !a, loft: !b };
    setErrs((e) => ({ ...e, ...bad }));
    if (!a || !b) return;                                   // the spec: each bad field says why, in place
    const km = haversineMetres(a, b) / 1000;
    setDist(km.toFixed(1));
    let mpm: number | null = null;
    if (relTime && arrTime) { mpm = velocityMPM(a, b, relTime, arrTime) as number | null; if (mpm) setVel(String(Math.round(mpm))); }
    setCalcOk({ km: `${km.toFixed(1)} km`, mpm: mpm ? `${Math.round(mpm)} m/min` : '—' });
  }
  async function save() {
    if (!birdId) { setErrs((e) => ({ ...e, bird: true })); setAlert(true); box.current?.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    const rel = parseCoords(relCoord), loft = parseCoords(loftCoord);
    if (loftCoord.trim()) await db.setSetting('loftCoords', loftCoord.trim());   // races.js:181 — remembered for the next result
    await Races.save({
      ...(r || { id: db.uuid() as string }), birdId, raceName: name.trim(), date, raceType: type,
      organisation: org.trim(), country: country.trim(),
      position: pos ? +pos : null, fanciersEntered: fanciers ? +fanciers : null, birdsEntered: birdsEntered ? +birdsEntered : null,
      releasePoint: rel ? { name: relName.trim(), ...rel } : (relName.trim() ? { name: relName.trim() } : null),
      loftPoint: loft, releaseTime: relTime || null, arrivalTime: arrTime || null,
      distanceKm: dist ? +dist : null, velocity: vel ? +vel : null,
    } as Race);
    toast(t('toast.saved'), { kind: 'success' }); onClose();
  }
  const F = ({ id, label, w, children, msg }: { id?: string; label: string; w?: 'w2' | 'w3'; children: React.ReactNode; msg?: string }) => (
    <div className={`${s.field} ${w ? s[w] : ''} ${id && errs[id] ? s.err : ''}`} data-testid={id ? `f-${id}` : undefined}>
      <label>{label}</label>{children}{msg && <div className={s.msg} role="alert">{msg}</div>}
    </div>
  );

  return (
    <div className={s.scrim} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }} data-testid="scrim">
      <div className={s.modal} role="dialog" aria-modal="true" aria-label={r ? t('act.edit') : t('race.new')} ref={box} data-testid="result-sheet">
        <div className={s.mhead}><h2 data-testid="sheet-title">{r ? t('act.edit') : t('race.new')}</h2>
          <button type="button" className={s['icon-btn']} aria-label={t('act.close')} onClick={onClose} data-testid="sheet-close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button></div>
        {alert && <div className={s.alert} role="alert" data-testid="sheet-alert"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v6M12 16.5h.01" /></svg><span>{t('val.notSaved')}</span></div>}

        <div className={s.grp}>
          <div className={s.fields}>
            <div className={`${s.field} ${s.w3} ${errs.bird ? s.err : ''}`} data-testid="f-bird">
              <label>{t('race.bird')}</label>
              <button type="button" className={s.pick} onClick={() => setPickOpen(!pickOpen)} data-testid="bird-pick">
                {bird ? <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}><b style={{ fontSize: 17, fontWeight: 800 }}><bdi>{nameOf(bird)}</bdi></b>{primaryRing(bird) && <span className={s.plate}><span className={s.season}>{yy(bird)}</span><span className={s.num}>{primaryRing(bird)}</span></span>}</span>
                  : <span className={s.ph}>{t('pick.fromLoft')}</span>}
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
              </button>
              <div className={s.msg} role="alert">{t('val.birdRequired')}</div>
              {pickOpen && (
                <div className={s.picklist} data-testid="bird-picklist">
                  <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('act.search')} aria-label={t('race.bird')} data-testid="bird-search" />
                  <div className={s.items}>{model.cands.map((c) => (
                    <button key={c.id} type="button" onClick={() => { setBirdId(c.id); setPickOpen(false); setQ(''); clearErr(); }} data-testid="bird-item">
                      <span><bdi>{nameOf(c as Bird)}</bdi> <span className={s.num}>{primaryRing(c as Bird)}</span></span><SexChip sex={c.sex} />
                    </button>
                  ))}</div>
                </div>
              )}
            </div>
            <F label={t('race.name')} w="w2"><input value={name} onChange={(e) => setName(e.target.value)} data-testid="f-name" /></F>
            <F label={t('common.date')}><input className={s.ltr} type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="f-date" /></F>
            <F label={t('race.type')}><div className={s.selwrap}><select value={type} onChange={(e) => setType(e.target.value)} data-testid="f-type">{RACE_TYPES.map((rt) => <option key={rt} value={rt}>{t('raceType.' + rt)}</option>)}</select></div></F>
            <F label={t('race.org')}><input value={org} onChange={(e) => setOrg(e.target.value)} data-testid="f-org" /></F>
            <F label={t('race.country')}><input className={s.ltr} value={country} onChange={(e) => setCountry(e.target.value)} data-testid="f-country" /></F>
            <F label={t('race.position')}><input className={s.ltr} inputMode="numeric" value={pos} onChange={(e) => setPos(e.target.value)} data-testid="f-pos" /></F>
            <F label={t('race.fanciers')}><input className={s.ltr} inputMode="numeric" value={fanciers} onChange={(e) => setFanciers(e.target.value)} data-testid="f-fanciers" /></F>
            <F label={t('race.birdsEntered')}><input className={s.ltr} inputMode="numeric" value={birdsEntered} onChange={(e) => setBirdsEntered(e.target.value)} data-testid="f-birds" /></F>
          </div>
        </div>

        <div className={s.grp}>
          <h3>{t('race.velocity')}</h3>
          <div className={s.sub}>{t('race.velocity.sub')}</div>
          <div className={s.fields}>
            <F label={t('race.releasePoint')}><input value={relName} onChange={(e) => setRelName(e.target.value)} data-testid="f-relname" /></F>
            <F id="coords" label={t('race.coords')} w="w2" msg={t('val.coords')}><input className={s.ltr} value={relCoord} onChange={(e) => { setRelCoord(e.target.value); setErrs((x) => ({ ...x, coords: false })); }} placeholder="29.5321, 35.0063" data-testid="i-coords" /></F>
            <F id="loft" label={t('race.loftCoords')} w="w3" msg={t('val.loftCoords')}><input className={s.ltr} value={loftCoord} onChange={(e) => { setLoftCoord(e.target.value); setErrs((x) => ({ ...x, loft: false })); }} placeholder="31.9539, 35.9106" data-testid="i-loftcoords" /></F>
            <F label={t('race.releaseTime')}><input className={s.ltr} type="datetime-local" value={relTime} onChange={(e) => setRelTime(e.target.value)} data-testid="f-reltime" /></F>
            <F label={t('race.arrivalTime')}><input className={s.ltr} type="datetime-local" value={arrTime} onChange={(e) => setArrTime(e.target.value)} data-testid="f-arrtime" /></F>
            <F label={`${t('race.distance')} (${t('race.km')})`}><input className={s.ltr} inputMode="decimal" value={dist} onChange={(e) => setDist(e.target.value)} data-testid="f-dist" /></F>
            <F label={`${t('race.velocity')} (${t('race.mpm')})`}><input className={s.ltr} inputMode="numeric" value={vel} onChange={(e) => setVel(e.target.value)} data-testid="f-vel" /></F>
          </div>
          <button type="button" className={s.calc} onClick={calc} data-testid="calc-btn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11A8 8 0 1 0 12 20M20 5v6h-6" /></svg>{t('race.calcVelocity')}</button>
          {calcOk && <div className={s['calc-ok']} data-testid="calc-ok"><Tpl k="race.calcDone" parts={{ km: calcOk.km, mpm: calcOk.mpm }} /></div>}
        </div>

        <div className={s.mact}>
          <button type="button" className={s.cancel} onClick={onClose} data-testid="sheet-cancel">{t('act.cancel')}</button>
          <button type="button" className={s.save} onClick={save} data-testid="sheet-save">{t('act.save')}</button>
        </div>
      </div>
    </div>
  );
}
