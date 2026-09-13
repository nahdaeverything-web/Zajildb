'use client';
import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectHealth, selectBirds } from '@/src/db/react';
import { t, fmtDate, fmtNum } from '@/src/i18n.ext.js';
import { todayISO } from '@/src/dates.js';
import { SyncRow, Loading, toast, undoToast, primaryRing, seasonLabel, pickerModel, SexChip, Tpl, initDB, useScrim, useScrollLock } from '@/src/components';
import s from './health.module.css';

// Health — design/approved/health-v1.html, behaviour from js/views/health.js.
// Spec wins on presentation: the next-vaccination banner, the type filters,
// phone rows with a coloured type chip and scope, the desktop table, the
// event sheet. Spec also wins on two departures design/README.md rules
// deliberate: an EDIT path (vanilla's eventDialog mints a fresh uuid every
// time, so it can only ever create) and visible inline errors (vanilla's save
// returns false in silence when no bird is chosen). Vanilla wins on wiring:
// Health.save / Health.remove / Health.restore through the facade, the four
// event types, the scope rule (whole loft ⇒ no bird), todayISO.
//
// The banner is ruling 4 (4.0): a healthEvent carries no interval, so the next
// vaccination is DERIVED as the most recent vaccination + 365 days and says in
// the block itself that it is an estimate. Hidden when there is none.
type Bird = { id: string; name?: string; sex?: string; strain?: string; rings?: Array<{ raw?: string; type?: string; year?: number | string | null }> };
type Ev = { id: string; eventType: string; wholeLoft?: boolean; birdId?: string | null; date?: string; medication?: string; notes?: string; loftId?: string };
const EVENT_TYPES = ['vaccination', 'treatment', 'illness', 'check'];
const DOT: Record<string, string> = { vaccination: 'vac', treatment: 'trt', illness: 'ill', check: 'chk' };
const Health = db.Health as { save: (e: Ev) => Promise<Ev>; remove: (id: string) => Promise<Ev>; restore: (e: Ev) => Promise<void> };
const getBird = (id: string) => db.getBird(id) as Bird | undefined;
const nameOf = (b?: Bird) => (b ? (b.name || primaryRing(b) || b.id.slice(0, 8)) : '—');
const plus365 = (iso: string) => { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + 365); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const daysBetween = (a: string, b: string) => Math.round((new Date(b + 'T00:00:00').getTime() - new Date(a + 'T00:00:00').getTime()) / 86400000);
const Plus = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>;

// Chip / Scope / Confirm / Acts (and F, below) live at module scope DELIBERATELY.
// A component declared inside another component's render body is a NEW component
// type on every render, so React unmounts and remounts its whole DOM subtree —
// pointless churn for these rows, and outright broken for a subtree holding a text
// field, which loses the caret after a single keystroke. Whatever they used to
// close over (the delete/edit handlers, setConfirmId) is an explicit prop now.
const Chip = ({ e }: { e: Ev }) => <span className={`${s.chip} ${s[DOT[e.eventType] || 'chk']}`} data-testid="type-chip" data-type={e.eventType}><span className={`${s.dot} ${s[DOT[e.eventType] || 'chk']}`} />{t('health.' + e.eventType)}</span>;
const Scope = ({ e }: { e: Ev }) => e.wholeLoft
  ? <span className={s.scope} data-testid="scope-loft"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l9-7 9 7v9H3z" /></svg>{t('health.wholeLoft')}</span>
  : (e.birdId ? <Link href={`/bird?id=${e.birdId}`} className={s.birdlink} data-testid="scope-bird"><bdi>{nameOf(getBird(e.birdId))}</bdi></Link> : <span>—</span>);
const Confirm = ({ onGo, onCancel }: { onGo: () => void; onCancel: () => void }) => (
  <div className={s.confirm} data-testid="inline-confirm"><span>{t('confirm.deleteGeneric')}</span>
    <div className={s.b}><button type="button" className={s.go} onClick={onGo} data-testid="confirm-go">{t('act.delete')}</button><button type="button" className={s.no} onClick={onCancel} data-testid="confirm-no">{t('act.cancel')}</button></div></div>
);
const Acts = ({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) => (
  <div className={s.acts}><button type="button" className={s.act} onClick={onEdit} data-testid="ev-edit">{t('act.edit')}</button>
    <button type="button" className={`${s.act} ${s.x}`} aria-label={t('act.delete')} onClick={onDelete} data-testid="ev-delete">✕</button></div>
);

export default function HealthView() {
  const params = useSearchParams();
  const [booted, setBooted] = useState(false);
  const [filter, setFilter] = useState<string>(params.get('filter') || 'all');
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [sheet, setSheet] = useState<{ editing: Ev | null } | null>(null);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const events = useZajilStore(selectHealth) as Ev[];
  const birds = useZajilStore(selectBirds) as Bird[];
  if (!booted) return <section className={s.screen}><Loading /></section>;

  // RF-7: health events are date-ONLY, so every event on the same day ties
  const all = [...events].sort((a, b) => (b.date || '').localeCompare(a.date || '') || (a.id || '').localeCompare(b.id || ''));   // health.js:20
  const vis = all.filter((e) => filter === 'all' ? true : filter === 'loft' ? !!e.wholeLoft : e.eventType === filter);
  const loft = db.currentLoft() as { name?: string } | null;
  const lastVac = all.find((e) => e.eventType === 'vaccination' && e.date);
  const due = lastVac && lastVac.date ? plus365(lastVac.date) : null;
  const days = due ? daysBetween(todayISO(), due) : 0;

  async function del(e: Ev) {
    setConfirmId(null);
    const snap = await Health.remove(e.id);
    undoToast(t('toast.deleted'), t('act.undo'), async () => { await Health.restore(snap); toast(t('toast.undone'), { kind: 'success' }); });
  }
  const FILTERS: Array<[string, string]> = [['all', t('common.all')], ...EVENT_TYPES.map((k) => [k, t('health.' + k)] as [string, string]), ['loft', t('health.wholeLoft')]];

  return (
    <section className={s.screen}>
      <header className={s.lofthead}><div className={s.in}><div className={s.headrow}>
        <div>
          <div className={s.season}>{seasonLabel()} · {loft?.name || t('loft.unnamed')}</div>
          <h1>{t('health.title')}</h1>
          <div className={s.count} data-testid="count-line">{all.length === 0 ? t('health.noneYet') : t('health.countLine', { n: fmtNum(all.length), d: fmtDate(all[0].date) })}</div>
        </div>
        <button type="button" className={s['btn-add']} onClick={() => setSheet({ editing: null })} data-testid="new-event-desktop"><Plus />{t('health.new')}</button>
      </div></div></header>
      <SyncRow />
      <section className={s.panel}>
        {lastVac && due && (
          <div className={`${s.next} ${days <= 0 ? s.due : ''}`} data-testid="next-vac" data-due={days <= 0 ? '1' : '0'}>
            <div>
              <div className={s.k}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l9 5v8l-9 5-9-5V8z" /></svg>{t('health.next')}</div>
              <div className={s.t}><bdi>{lastVac.medication || t('health.vaccination')}</bdi>{lastVac.wholeLoft ? ` — ${t('health.wholeLoft')}` : ''}</div>
              <div className={s.s} data-testid="dose-line"><Tpl k="health.doseLine" parts={{ last: fmtDate(lastVac.date), due: fmtDate(due) }} /></div>
              <div className={s.est} data-testid="next-estimate">{t('health.next.estimate')}</div>
            </div>
            <div className={s.days}><div className={s.n} data-testid="next-days">{fmtNum(Math.abs(days), { group: false })}</div><div className={s.u}>{t('health.daysUntil')}</div></div>
          </div>
        )}
        <div className={s.filters} role="group" aria-label={t('act.filter')} data-testid="filters">
          {FILTERS.map(([k, label]) => (
            <button key={k} type="button" aria-pressed={filter === k} onClick={() => { setFilter(k); setConfirmId(null); }} data-testid="filter" data-filter={k}>
              {k !== 'all' && k !== 'loft' && <span className={`${s.dot} ${s[DOT[k]]}`} />}{label}
            </button>
          ))}
        </div>
        {vis.length === 0 ? (
          <div className={s.empty} data-testid="empty-state">
            <div className={s.ico}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l2-5 3 10 2-5h7" /></svg></div>
            <h3 data-testid="empty-title">{all.length === 0 ? t('health.noEvents') : t('health.noMatch')}</h3>
            {all.length === 0 && <p>{t('health.empty.body')}</p>}
          </div>
        ) : (
          <>
            <div className={s.list} data-testid="ev-rows">
              {vis.map((e, i) => {
                // one date header per group, decided from the row BEFORE this one rather
                // than by assigning to a variable as the map runs (react-hooks/immutability)
                const head = i === 0 || e.date !== vis[i - 1].date;
                return (
                  <div key={e.id}>
                    {head && <div className={s.datelbl} data-testid="date-group"><bdi>{fmtDate(e.date)}</bdi></div>}
                    <div className={s.hrow} data-testid="ev-row">
                      <div className={s.l1}><div>
                        <div className={s.med}><bdi>{e.medication || '—'}</bdi></div>
                        <div className={s.meta}><Chip e={e} /><Scope e={e} /></div>
                        {e.notes && <div className={s.note}><bdi>{e.notes}</bdi></div>}
                      </div></div>
                      <div className={s.l2}>{confirmId === e.id ? null : <Acts onEdit={() => setSheet({ editing: e })} onDelete={() => setConfirmId(e.id)} />}</div>
                      {confirmId === e.id && <Confirm onGo={() => del(e)} onCancel={() => setConfirmId(null)} />}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className={s.table} data-testid="ev-table">
              <table>
                <thead><tr><th>{t('common.date')}</th><th>{t('health.type')}</th><th>{t('health.scope')}</th><th>{t('health.medication')}</th><th>{t('common.notes')}</th><th /></tr></thead>
                <tbody>{vis.map((e) => (
                  <tr key={e.id} className={confirmId === e.id ? s.cf : ''} data-testid="ev-tr">
                    <td className={s.num}><bdi>{fmtDate(e.date)}</bdi></td>
                    <td><Chip e={e} /></td><td><Scope e={e} /></td>
                    <td className={s.med}><bdi>{e.medication || '—'}</bdi></td>
                    <td className={s.note}><bdi>{e.notes || ''}</bdi></td>
                    <td>{confirmId === e.id ? <Confirm onGo={() => del(e)} onCancel={() => setConfirmId(null)} /> : <Acts onEdit={() => setSheet({ editing: e })} onDelete={() => setConfirmId(e.id)} />}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </section>
      <div className={s.fab} data-bottom-chrome="fab"><button type="button" onClick={() => setSheet({ editing: null })} data-testid="new-event-fab"><Plus />{t('health.new')}</button></div>
      {sheet && <EventSheet editing={sheet.editing} birds={birds} onClose={() => setSheet(null)} />}
    </section>
  );
}

// The field wrapper, at module scope for the reason given above and most sharply
// here: F wraps the sheet's inputs, so re-declaring it each render remounted them
// and the caret was lost after one character — «برق السريع» typed into a name
// field left «ب». It closes over nothing but the CSS module, which is module scope.
const F = ({ label, children, id }: { label: string; children: ReactNode; id?: string }) => (
  <div className={s.field} data-testid={id}><label>{label}</label>{children}</div>
);

/** The event sheet — health.js:60 eventDialog, plus the spec's edit path and its visible error. */
function EventSheet({ editing, birds, onClose }: { editing: Ev | null; birds: Bird[]; onClose: () => void }) {
  const scrim = useScrim(onClose);
  useScrollLock();
  const e = editing;
  const [type, setType] = useState(e?.eventType || 'vaccination');
  const [scope, setScope] = useState<'bird' | 'loft'>(e ? (e.wholeLoft ? 'loft' : 'bird') : 'bird');
  const [birdId, setBirdId] = useState<string | null>(e?.birdId || null);
  const [date, setDate] = useState(e?.date || todayISO());
  const [med, setMed] = useState(e?.medication || '');
  const [notes, setNotes] = useState(e?.notes || '');
  const [err, setErr] = useState(false);
  const [pickOpen, setPickOpen] = useState(false);
  const [q, setQ] = useState('');
  useEffect(() => { const k = (ev: KeyboardEvent) => { if (ev.key === 'Escape') onClose(); }; document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k); }, [onClose]);
  const bird = birdId ? getBird(birdId) : null;
  const model = pickerModel({ all: birds, pool: birds, q, allowCreate: false, selected: birdId });

  async function save() {
    const wholeLoft = scope === 'loft';
    if (!wholeLoft && !birdId) { setErr(true); return; }            // the spec: say so, in place
    await Health.save({ ...(e || { id: db.uuid() as string }), eventType: type, wholeLoft, birdId: wholeLoft ? null : birdId, date, medication: med.trim(), notes: notes.trim() } as Ev);
    toast(t('toast.saved'), { kind: 'success' }); onClose();
  }
  return (
    <div className={s.scrim} {...scrim} data-testid="scrim">
      <div className={s.modal} role="dialog" aria-modal="true" aria-label={e ? t('act.edit') : t('health.new')} data-testid="event-sheet">
        <div className={s.mhead}><h2 data-testid="sheet-title">{e ? t('act.edit') : t('health.new')}</h2>
          <button type="button" className={s['icon-btn']} aria-label={t('act.close')} onClick={onClose} data-testid="sheet-close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button></div>
        {err && <div className={s.alert} role="alert" data-testid="sheet-alert"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v6M12 16.5h.01" /></svg><span>{t('val.notSavedEvent')}</span></div>}
        <div className={s.fields}>
          <F label={t('health.type')}>
            <div className={`${s.selwrap} ${s.hasdot}`}><span className={`${s.dot} ${s[DOT[type]]}`} data-testid="type-dot" data-type={type} />
              <select value={type} onChange={(ev) => setType(ev.target.value)} data-testid="f-type">{EVENT_TYPES.map((k) => <option key={k} value={k}>{t('health.' + k)}</option>)}</select></div>
          </F>
          <F label={t('health.scope')}>
            <div className={s.selwrap}><select value={scope} onChange={(ev) => { setScope(ev.target.value as 'bird' | 'loft'); setErr(false); }} data-testid="f-scope">
              <option value="bird">{t('health.singleBird')}</option><option value="loft">{t('health.wholeLoft')}</option></select></div>
          </F>
          {scope === 'bird' && (
            <div className={`${s.field} ${err ? s.err : ''}`} data-testid="f-bird">
              <label>{t('race.bird')}</label>
              <button type="button" className={s.pick} onClick={() => setPickOpen(!pickOpen)} data-testid="bird-pick">
                {bird ? <span className={s.val}><b><bdi>{nameOf(bird)}</bdi></b>{primaryRing(bird) && <span className={s.plate}><span className={s.num}>{primaryRing(bird)}</span></span>}</span> : <span className={s.ph}>{t('pick.fromLoft')}</span>}
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
              </button>
              <div className={s.msg} role="alert">{t('val.birdRequiredScope')}</div>
              {pickOpen && (
                <div className={s.picklist} data-testid="bird-picklist">
                  <input autoFocus value={q} onChange={(ev) => setQ(ev.target.value)} placeholder={t('act.search')} aria-label={t('race.bird')} data-testid="bird-search" />
                  <div className={s.items}>{model.cands.map((c) => (
                    <button key={c.id} type="button" onClick={() => { setBirdId(c.id); setPickOpen(false); setQ(''); setErr(false); }} data-testid="bird-item">
                      <span><bdi>{nameOf(c as Bird)}</bdi> <span className={s.num}>{primaryRing(c as Bird)}</span></span><SexChip sex={c.sex} />
                    </button>
                  ))}</div>
                </div>
              )}
            </div>
          )}
          <F label={t('common.date')}><input className={s.ltr} type="date" value={date} onChange={(ev) => setDate(ev.target.value)} data-testid="f-date" /></F>
          <F label={t('health.medication')}><input value={med} onChange={(ev) => setMed(ev.target.value)} placeholder={t('health.med.placeholder')} data-testid="f-med" /></F>
          <F label={t('common.notes')}><textarea rows={3} value={notes} onChange={(ev) => setNotes(ev.target.value)} placeholder={t('health.notes.placeholder')} data-testid="f-notes" /></F>
        </div>
        <div className={s.mact}>
          <button type="button" className={s.cancel} onClick={onClose} data-testid="sheet-cancel">{t('act.cancel')}</button>
          <button type="button" className={s.save} onClick={save} data-testid="sheet-save">{t('act.save')}</button>
        </div>
      </div>
    </div>
  );
}
