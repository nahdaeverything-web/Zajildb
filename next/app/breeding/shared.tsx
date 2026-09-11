'use client';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { t, fmtNum, fmtDate, fmtPercent } from '@/src/i18n.ext.js';
import { validatePairSexes } from '@/src/engine/validate.js';
import { describeRelationship, pairingWarningLevel } from '@/src/engine/relationship.js';
import { parseRing, ringKey } from '@/src/engine/rings.js';
import { todayISO } from '@/src/dates.js';
import { toast, undoToast, primaryRing, birdLabelText, COIValue, SexChip } from '@/src/components';
import s from './breeding.module.css';

// Breeding — design/approved/breeding-v1.html, behaviour from js/views/breeding.js.
// Shared by the list (/breeding) and the detail (/pair?id=): record types, the
// pair card with its rounds and eggs, the three sheets (new pair, link an
// existing bird, ring a chick) and the mutations, every one of which goes
// through Pairs.save / saveBird on the facade exactly as vanilla does.
export type Egg = { id: string; laidDate?: string; state: 'laid' | 'hatched' | 'failed'; hatchDate?: string; chickId?: string | null; ringed?: boolean; weaned?: boolean; weanDate?: string };
export type Round = { id: string; number?: number; eggs?: Egg[] };
export type Pair = { id: string; sireId: string; damId: string; season?: string; nestBox?: string; status?: string; startDate?: string; acquiredFrom?: string; acquiredDate?: string; rounds?: Round[] };
export type Bird = { id: string; name?: string; sex?: string; strain?: string; hatchDate?: string; sireId?: string | null; damId?: string | null; rings?: Array<{ raw?: string; type?: string; year?: number | string | null }> };
type Problem = { key: string; params?: Record<string, unknown> };
export const getBird = (id: string | null | undefined) => (id ? (db.getBird(id) as Bird | undefined) : undefined);
const Pairs = db.Pairs as { save: (p: Pair) => Promise<Pair>; remove: (id: string) => Promise<Pair>; restore: (p: Pair) => Promise<void> };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const yy = (b: Bird) => { const r = (b.rings || []).find((x) => x.type === 'FCI') || (b.rings || [])[0]; return r && r.year ? String(r.year).slice(-2) : ''; };
export const nameOf = (b?: Bird) => (b ? (b.name || primaryRing(b) || b.id.slice(0, 8)) : t('common.unknown'));

export const Plate = ({ b }: { b?: Bird }) => { const raw = b ? primaryRing(b) : ''; return raw ? <span className={s.plate}><span className={s.yr}>{yy(b!)}</span><span className={s.no}>{raw}</span></span> : null; };
export const Chev = () => <svg className={s.chev} viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>;
export const Plus = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>;
/** The list row's «♂ sire × ♀ dam» line and the plates line (spec namesHtml / miniPlates). */
export const Names = ({ p }: { p: Pair }) => { const sire = getBird(p.sireId), dam = getBird(p.damId); return <div className={s.names}><span className={`${s.sex} ${s.m}`}>♂</span><bdi>{nameOf(sire)}</bdi><span className={s.x}>×</span><span className={`${s.sex} ${s.f}`}>♀</span><bdi>{nameOf(dam)}</bdi></div>; };
export const Plates = ({ p }: { p: Pair }) => <div className={s.plates}><Plate b={getBird(p.sireId)} /><span className={s.x}>×</span><Plate b={getBird(p.damId)} /></div>;
export const StatusChip = ({ p }: { p: Pair }) => p.status === 'active' ? <span className={`${s.chip} ${s.on}`} data-testid="pair-status">{t('br.active')}</span> : <span className={`${s.chip} ${s.off}`} data-testid="pair-status">{t('br.separated')}</span>;
export function stats(p: Pair) {
  const eggs = (p.rounds || []).flatMap((r) => r.eggs || []);
  return { rounds: (p.rounds || []).length, eggs: eggs.length, hatched: eggs.filter((e) => e.state === 'hatched').length, failed: eggs.filter((e) => e.state === 'failed').length };
}
/** spec summary(): «3 بطون · 5 بيض · 2 فقست» or «لا بطون بعد». */
export const Summary = ({ p }: { p: Pair }) => { const x = stats(p); return x.rounds ? <span className={s.sum}>{t('br.roundsCount', { n: fmtNum(x.rounds) })} · {t('br.eggsCount', { n: fmtNum(x.eggs) })} · <span className={s.h}>{fmtNum(x.hatched)} {t('br.egg.hatched')}</span></span> : <span className={s.sum}>{t('br.noRounds')}</span>; };

// ── mutations (breeding.js) — always a fresh copy through Pairs.save ──
export async function savePair(p: Pair) { return Pairs.save(clone(p)); }
export async function toggleActive(p: Pair) { const c = clone(p); c.status = c.status === 'active' ? 'separated' : 'active'; await Pairs.save(c); }
export async function addRound(p: Pair) { const c = clone(p); c.rounds = c.rounds || []; const r = { id: db.uuid() as string, number: c.rounds.length + 1, eggs: [] }; c.rounds.push(r); await Pairs.save(c); return r.id; }
export async function addEgg(p: Pair, roundId: string) {
  const c = clone(p); const r = (c.rounds || []).find((x) => x.id === roundId)!; r.eggs = r.eggs || [];
  const prev = r.eggs[r.eggs.length - 1];   // a second egg of a clutch is laid within a day or two of the first
  r.eggs.push({ id: db.uuid() as string, laidDate: (prev && prev.laidDate) || todayISO(), state: 'laid' }); await Pairs.save(c);
}
async function withEgg(p: Pair, eggId: string, fn: (e: Egg) => void | Promise<void>) { const c = clone(p); const e = (c.rounds || []).flatMap((r) => r.eggs || []).find((x) => x.id === eggId)!; await fn(e); await Pairs.save(c); }
export const hatch = (p: Pair, eggId: string) => withEgg(p, eggId, (e) => { e.state = 'hatched'; e.hatchDate = todayISO(); });
export const fail = (p: Pair, eggId: string) => withEgg(p, eggId, (e) => { e.state = 'failed'; });
export const wean = (p: Pair, eggId: string) => withEgg(p, eggId, (e) => { e.weaned = true; e.weanDate = todayISO(); });
export const unlink = (p: Pair, eggId: string) => withEgg(p, eggId, (e) => { e.chickId = null; e.ringed = false; e.weaned = false; e.weanDate = ''; });   // only detaches the egg; the bird stays
export const setEggDate = (p: Pair, eggId: string, key: 'laidDate' | 'hatchDate' | 'weanDate', value: string) => withEgg(p, eggId, async (e) => {
  e[key] = value;
  if (key === 'hatchDate' && e.chickId) { const chick = getBird(e.chickId); if (chick) await db.saveBird({ ...chick, hatchDate: value }, { allowWarnings: true }); }   // a hatch-date change corrects the chick's record
});
/** Delete with undo (spec: eggs and rounds too — the undo re-inserts at the same index). */
export async function deletePair(p: Pair) { const snap = await Pairs.remove(p.id); undoToast(t('toast.deleted'), t('act.undo'), async () => { await Pairs.restore(snap); toast(t('toast.undone'), { kind: 'success' }); }); }
export async function deleteRound(p: Pair, roundId: string) {
  const c = clone(p); const i = (c.rounds || []).findIndex((r) => r.id === roundId); const [r] = c.rounds!.splice(i, 1); await Pairs.save(c);
  undoToast(t('toast.deleted'), t('act.undo'), async () => { const cur = clone(db.state.pairs.get(p.id) as Pair); cur.rounds = cur.rounds || []; cur.rounds.splice(Math.min(i, cur.rounds.length), 0, r); await Pairs.save(cur); toast(t('toast.undone'), { kind: 'success' }); });
}
export async function deleteEgg(p: Pair, roundId: string, eggId: string) {
  const c = clone(p); const r = (c.rounds || []).find((x) => x.id === roundId)!; const i = (r.eggs || []).findIndex((e) => e.id === eggId); const [e] = r.eggs!.splice(i, 1); await Pairs.save(c);
  undoToast(t('toast.deleted'), t('act.undo'), async () => { const cur = clone(db.state.pairs.get(p.id) as Pair); const rr = (cur.rounds || []).find((x) => x.id === roundId); if (!rr) return; rr.eggs = rr.eggs || []; rr.eggs.splice(Math.min(i, rr.eggs.length), 0, e); await Pairs.save(cur); toast(t('toast.undone'), { kind: 'success' }); });
}

// ── the sheet (spec .scrim/.modal): bottom sheet on the phone, centred at ≥1100; Escape closes ──
export function Sheet({ title, onClose, children, wide, hint, testid }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean; hint?: ReactNode; testid: string }) {
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k); }, [onClose]);
  return (
    <div className={s.scrim} data-testid="scrim">
      <div className={`${s.modal} ${wide ? s.wide : ''}`} role="dialog" aria-modal="true" aria-label={title} data-testid={testid}>
        <div className={s.mhead}><h2>{title}</h2><button type="button" className={s['icon-btn']} aria-label={t('act.close')} onClick={onClose} data-testid="sheet-close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button></div>
        {hint && <p className={s.hintline}>{hint}</p>}
        {children}
      </div>
    </div>
  );
}
const Alert = ({ kind, title, items, testid }: { kind?: 'warn' | 'blocked'; title?: string; items: string[]; testid: string }) => (
  <div className={`${s.alert} ${kind ? s[kind] : ''}`} role="alert" data-testid={testid}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l10 18H2z" /><path d="M12 10v4M12 17.5h.01" /></svg>
    <div>{title && <div>{title}</div>}<ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div></div>
);

/** A spec .field with a .pick button; open = vanilla's picker rules under it (search by name / strain / ring, blocked-match note, inline create). */
export function BirdPick({ label, value, filter, placeholder, onPick, testid, err, allowCreate, sexIcon }: { label: string; value: string | null; filter: (b: Bird) => boolean; placeholder: string; onPick: (id: string | null) => void; testid: string; err?: boolean; allowCreate?: 'cock' | 'hen'; sexIcon?: string }) {
  const [open, setOpen] = useState(false); const [q, setQ] = useState('');
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!open) return; const f = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); }; document.addEventListener('mousedown', f); return () => document.removeEventListener('mousedown', f); }, [open]);
  const all = [...(db.state.birds.values() as Iterable<Bird>)]; const pool = all.filter(filter);
  const needle = q.trim().toLowerCase(); const rk = ringKey(q);
  const match = (list: Bird[]) => list.find((b) => (rk && (b.rings || []).some((r) => ringKey(r as never) === rk)) || (b.name || '').trim().toLowerCase() === needle || birdLabelText(b).trim().toLowerCase() === needle) || null;
  const cands = (needle ? pool.filter((b) => (b.name || '').toLowerCase().includes(needle) || (b.strain || '').toLowerCase().includes(needle) || (rk && (b.rings || []).some((r) => ringKey(r as never).includes(rk)))) : pool).slice(0, 30);
  const clash = needle ? match(all) : null; const blocked = clash && !match(pool) ? clash : null;
  const canCreate = !!(allowCreate && needle && !clash);
  const pick = (id: string) => { onPick(id); setOpen(false); setQ(''); };
  const chosen = getBird(value);
  return (
    <div className={`${s.field} ${err ? s.err : ''}`} ref={box} data-testid={testid}>
      <label>{label}{sexIcon && <> <span className={s.opt}>{sexIcon}</span></>}</label>
      <button type="button" className={`${s.pick} ${chosen ? '' : s.ph}`} onClick={() => setOpen(!open)} data-testid={`${testid}-btn`}>
        {chosen ? <span className={s.val}><bdi>{nameOf(chosen)}</bdi><Plate b={chosen} /></span> : <span className={s.ph}>{placeholder}</span>}
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <div className={s.picklist} data-testid={`${testid}-list`}>
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('act.search')} aria-label={label} data-testid={`${testid}-input`} />
          {blocked && <div className={s.note} data-testid="picker-note">{t('picker.existsButFiltered', { name: birdLabelText(blocked), sex: t('sex.' + (blocked.sex || 'unknown')) })}</div>}
          <div className={s.items}>{cands.map((b) => <button key={b.id} type="button" onClick={() => pick(b.id)} data-testid={`${testid}-item`}><span><bdi>{nameOf(b)}</bdi> <Plate b={b} /></span><SexChip sex={b.sex} /></button>)}</div>
          {canCreate && <button type="button" className={s.create} onClick={async () => { const hasDigit = /[0-9٠-٩]/.test(q); const stub = db.newBird({ external: true, sex: allowCreate, name: hasDigit ? '' : q.trim(), rings: hasDigit ? [parseRing(q.trim())] : [] }) as Bird; await db.saveBird(stub); pick(stub.id); }} data-testid={`${testid}-create`}>+ {t('picker.createNew', { q: q.trim() })}</button>}
        </div>
      )}
    </div>
  );
}

/** «زوج جديد» — breeding.js:54 newPairDialog in the spec's sheet, with the kin box and the spec's inline error list. */
export function NewPairSheet({ season, seasons, onClose, onSaved }: { season: string; seasons: string[]; onClose: () => void; onSaved: (id: string) => void }) {
  const [sireId, setSire] = useState<string | null>(null); const [damId, setDam] = useState<string | null>(null);
  const [nest, setNest] = useState(''); const [ssn, setSsn] = useState(season); const [mated, setMated] = useState(todayISO()); const [source, setSource] = useState(''); const [bought, setBought] = useState('');
  const [errs, setErrs] = useState<string[]>([]); const [bad, setBad] = useState<Record<string, boolean>>({});
  const depth = +((db.state.settings as Record<string, unknown>).coiDepth || 10);
  const rel = sireId && damId ? (describeRelationship(getBird, sireId, damId, depth) as { key: string; params: Record<string, unknown>; hypotheticalCOI: number }) : null;
  const level = rel ? (pairingWarningLevel(rel.hypotheticalCOI) as string) : null;
  async function save() {
    const e: string[] = []; const b: Record<string, boolean> = {};
    if (!sireId) { e.push(t('br.err.sire')); b.sire = true; }
    if (!damId) { e.push(t('br.err.dam')); b.dam = true; }
    const n = nest.trim();
    if (!n) { e.push(t('br.err.nest')); b.nest = true; }
    else if ([...(db.state.pairs.values() as Iterable<Pair>)].some((p) => p.season === ssn && p.status === 'active' && String(p.nestBox) === n)) { e.push(t('br.err.nestBusy', { n })); b.nest = true; }   // spec rule (raised): one active pair per nest and season
    for (const p of validatePairSexes(getBird(sireId), getBird(damId)) as Problem[]) e.push(t(p.key, p.params));
    setErrs(e); setBad(b); if (e.length) return;
    const pair: Pair = { id: db.uuid() as string, sireId: sireId!, damId: damId!, season: ssn || season, nestBox: n, status: 'active', startDate: mated || todayISO(), acquiredFrom: source.trim(), acquiredDate: bought, rounds: [] };
    await Pairs.save(pair); toast(t('toast.saved'), { kind: 'success' }); onSaved(pair.id);
  }
  return (
    <Sheet title={t('br.newPair')} onClose={onClose} wide testid="sheet-new">
      <div data-testid="kin">
        {!rel || !level ? <div className={`${s.kin} ${s.wait}`}>{t('br.kinWait')}</div> : (
          <div className={`${s.kin} ${level === 'severe' || level === 'high' ? s.hi : ''}`} data-testid="kin-box" data-level={level}>
            <div className={s.tile}><div className={s.n}><COIValue coi={rel.hypotheticalCOI} mono={false} /></div><div className={s.l}>{t('tile.coi')}</div></div>
            <div><div className={s.k}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l10 18H2z" /><path d="M12 10v4M12 17.5h.01" /></svg>{t('br.pairCOIWarning')}</div><div className={s.t} data-testid="kin-title">{t(rel.key, rel.params)}</div><div className={s.s}>{t('rel.warn.' + level, { coi: fmtPercent(rel.hypotheticalCOI, 2) })}</div></div>
          </div>
        )}
      </div>
      {errs.length > 0 && <Alert title={t('br.notSaved')} items={errs} testid="new-errs" />}
      <div className={s.fields}>
        <div className={s.two}>
          <BirdPick label={t('bird.sire')} sexIcon="♂" value={sireId} filter={(b) => b.sex !== 'hen'} placeholder={t('br.pickSire')} onPick={(v) => { setSire(v); setBad({ ...bad, sire: false }); }} testid="f-sire" err={bad.sire} allowCreate="cock" />
          <BirdPick label={t('bird.dam')} sexIcon="♀" value={damId} filter={(b) => b.sex !== 'cock'} placeholder={t('br.pickDam')} onPick={(v) => { setDam(v); setBad({ ...bad, dam: false }); }} testid="f-dam" err={bad.dam} allowCreate="hen" />
        </div>
        <div className={s.two}>
          <div className={`${s.field} ${bad.nest ? s.err : ''}`}><label>{t('br.nestBox')}</label><input className={s.ltr} value={nest} onChange={(e) => setNest(e.target.value)} placeholder={t('br.nest.placeholder')} data-testid="f-nest" /></div>
          <div className={s.field}><label>{t('br.season')}</label><div className={s.fsel}><select className={s.ltr} value={ssn} onChange={(e) => setSsn(e.target.value)} data-testid="f-season">{seasons.map((y) => <option key={y} value={y}>{y}</option>)}</select></div></div>
        </div>
        <div className={s.field}><label>{t('br.startDate')}</label><input className={s.ltr} type="date" value={mated} onChange={(e) => setMated(e.target.value)} data-testid="f-mated" /></div>
        <div className={s.two}>
          <div className={s.field}><label>{t('br.acquiredFrom')}</label><input value={source} onChange={(e) => setSource(e.target.value)} placeholder={t('br.source.placeholder')} data-testid="f-source" /></div>
          <div className={s.field}><label>{t('br.acquiredDate')} <span className={s.opt}>{t('common.optional')}</span></label><input className={s.ltr} type="date" value={bought} onChange={(e) => setBought(e.target.value)} data-testid="f-bought" /></div>
        </div>
        <p className={s.hintline}>{t('br.boughtHint')}</p>
      </div>
      <div className={s.mact}><button type="button" className={s.cancel} onClick={onClose} data-testid="sheet-cancel">{t('act.cancel')}</button><button type="button" className={s.save} onClick={save} data-testid="sheet-save">{t('act.save')}</button></div>
    </Sheet>
  );
}

/** «ربط طير مسجَّل» — breeding.js:269 linkExistingDialog: the final record is composed and validated first. */
export function LinkSheet({ pair, egg, onClose, onDone }: { pair: Pair; egg: Egg; onClose: () => void; onDone: () => void }) {
  const [birdId, setBirdId] = useState<string | null>(null);
  const bird = getBird(birdId);
  let why: string | null = null;
  if (bird) {
    if (bird.id === pair.sireId || bird.id === pair.damId) why = t('br.blk.parent');
    else if ([...(db.state.pairs.values() as Iterable<Pair>)].some((p) => p.season === pair.season && (p.rounds || []).some((r) => (r.eggs || []).some((e) => e.chickId === bird.id && e.id !== egg.id)))) why = t('br.blk.linked');   // spec rule (raised)
    else {
      const candidate = { ...bird, sireId: pair.sireId, damId: pair.damId, hatchDate: egg.hatchDate && !bird.hatchDate ? egg.hatchDate : bird.hatchDate };
      const { errors } = db.checkBird(candidate, { allowWarnings: true }) as { errors: Problem[] };
      if (errors.length) why = errors.map((e) => t(e.key, e.params)).join(' · ');
    }
  }
  async function confirm() {
    if (!bird || why) return;
    const candidate = { ...bird, sireId: pair.sireId, damId: pair.damId }; if (egg.hatchDate && !bird.hatchDate) candidate.hatchDate = egg.hatchDate;
    await db.saveBird(candidate, { allowWarnings: true });
    await withEgg(pair, egg.id, (e) => { e.chickId = bird.id; e.ringed = (bird.rings || []).length > 0; });
    toast(t('br.linked'), { kind: 'success' }); onDone();
  }
  return (
    <Sheet title={t('br.linkExisting')} onClose={onClose} hint={t('br.linkExistingHint')} testid="sheet-link">
      <div className={s.fields}>
        <BirdPick label={t('bird.one')} value={birdId} filter={(b) => b.id !== pair.sireId && b.id !== pair.damId} placeholder={t('br.pickBird')} onPick={setBirdId} testid="f-link" />
        {why && <Alert kind="blocked" items={[t('br.linkBlocked', { reason: why })]} testid="link-blocked" />}
      </div>
      <div className={s.mact}><button type="button" className={s.cancel} onClick={onClose} data-testid="sheet-cancel">{t('act.cancel')}</button><button type="button" className={s.save} disabled={!bird || !!why} onClick={confirm} data-testid="sheet-save">{t('act.confirm')}</button></div>
    </Sheet>
  );
}

/** «تركيب الحلقة» — breeding.js:312 ringChickDialog: the chick is a real bird record, validated like any other. */
export function RingSheet({ pair, roundIndex, egg, onClose, onDone }: { pair: Pair; roundIndex: number; egg: Egg; onClose: () => void; onDone: () => void }) {
  const [ring, setRing] = useState(''); const [name, setName] = useState(''); const [sex, setSex] = useState<'unknown' | 'cock' | 'hen'>('unknown'); const [errs, setErrs] = useState<string[]>([]);
  const sire = getBird(pair.sireId), dam = getBird(pair.damId);
  const build = () => { const chick = db.newBird({ name: name.trim(), sex, hatchDate: egg.hatchDate || '', status: 'young bird', sireId: pair.sireId, damId: pair.damId, rings: ring.trim() ? [parseRing(ring.trim())] : [] }) as Bird; if (sire && sire.strain) chick.strain = sire.strain; return chick; };
  const warns: string[] = [];
  if (ring.trim()) {
    for (const w of (db.checkBird(build()) as { warnings: Problem[] }).warnings) { const p = { ...(w.params || {}) } as Record<string, unknown>; if (p.otherId && !p.otherName) { const ob = getBird(p.otherId as string); p.otherName = ob ? ob.name || '' : ''; } warns.push(t(w.key, p)); }
    const ry = (parseRing(ring.trim()) as { year?: number | null }).year; const hy = egg.hatchDate ? +egg.hatchDate.slice(0, 4) : null;
    if (ry && hy && ry !== hy) warns.push(t('br.warn.ringYear', { y: String(ry), h: String(hy) }));   // spec's ring-year check
  }
  async function save() {
    const chick = build(); const v = db.checkBird(chick) as { errors: Problem[] };
    if (v.errors.length) { setErrs(v.errors.map((e) => t(e.key, e.params))); return; }
    try {
      await db.saveBird(chick, { allowWarnings: true });
      await withEgg(pair, egg.id, (e) => { e.chickId = chick.id; e.ringed = !!ring.trim(); });
      toast(t('br.chickCreated'), { kind: 'success' }); onDone();
    } catch (err) { const ve = err as { errors?: Problem[] }; setErrs((ve.errors || [{ key: 'toast.saveFailed', params: {} }]).map((e) => t(e.key, e.params))); }
  }
  return (
    <Sheet title={t('br.ringChick')} onClose={onClose} hint={t('br.ringCtx', { s: nameOf(sire), d: nameOf(dam), n: fmtNum(roundIndex + 1, { group: false }), date: fmtDate(egg.hatchDate) })} testid="sheet-ring">
      {errs.length > 0 && <Alert title={t('val.fixErrors')} items={errs} testid="ring-errs" />}
      {warns.length > 0 && <Alert kind="warn" title={t('val.warningsTitle')} items={warns} testid="ring-warn" />}
      <div className={s.fields}>
        <div className={s.field}><label>{t('bird.ring')}</label><input className={s.ltr} value={ring} onChange={(e) => setRing(e.target.value)} placeholder="JO-2026-12345" dir="ltr" lang="en" autoCapitalize="characters" autoCorrect="off" spellCheck={false} data-testid="f-ring" /></div>
        <div className={s.field}><label>{t('bird.name')}</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('br.name.placeholder')} data-testid="f-name" /></div>
        <div className={s.field}><label>{t('bird.sex')}</label><div className={s.seg} role="group">{(['unknown', 'cock', 'hen'] as const).map((sx) => <button key={sx} type="button" aria-pressed={sex === sx} onClick={() => setSex(sx)} data-testid="f-sex" data-sex={sx}>{t('sex.' + sx)}</button>)}</div></div>
      </div>
      <div className={s.mact}><button type="button" className={s.cancel} onClick={onClose} data-testid="sheet-cancel">{t('act.cancel')}</button><button type="button" className={`${s.save} ${warns.length ? s.warn : ''}`} disabled={!ring.trim()} onClick={save} data-testid="sheet-save">{warns.length ? t('act.saveAnyway') : t('br.saveAndLink')}</button></div>
    </Sheet>
  );
}

/** The seasons a select offers: the current year plus every season on record (breeding.js:24). */
export const seasonOptions = (pairs: Pair[], current: string) => [...new Set([current, ...pairs.map((p) => p.season || '')])].filter(Boolean).sort().reverse();
export const currentYear = () => String(new Date().getFullYear());
export { Link };
