'use client';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import * as db from '@/src/db.js';
import { useZajilStore, selectBirds } from '@/src/db/react';
import { t, statusLabel } from '@/src/i18n.ext.js';
import { parseRing, RING_TYPES } from '@/src/engine/rings.js';
import { Loading, toast, confirmDialog, primaryRing, birdLabelText, seasonLabel, SexChip, pickerModel, createFromQuery, initDB } from '@/src/components';
import s from './form.module.css';

// Add / edit bird — design/approved/add-edit-bird-v2.html, behaviour from
// js/views/bird-form.js. Spec wins on presentation: one column of cards, the
// sex segment and status chips, the two parent-slot states (set / empty), the
// external toggle card, the fixed action bar (no tab bar — a modal flow).
// Vanilla wins on wiring: newBird/checkBird/saveBird through the facade, the
// ?sire=&dam= and ?siblingOf= intents (placeholders minted only on a
// successful save), the picker's search / blocked-match / inline-create rules
// (ui.js:205), pending media saved after the bird, save-and-new's carry-over,
// Enter advancing focus. Capabilities the spec is silent on are carried
// (rulings at 4A acceptance): several rings with types, the hatch-from-ring-
// year hint, the remaining vanilla fields, documents, save-and-new, clear
// parent. Errors use shared-states' error dialog; warnings its warnings
// dialog; the duplicate ring shows live in the spec's warnbox.
type Ring = { raw?: string; type?: string; year?: number | string | null; country?: string };
type Note = { id?: string; at?: string; text?: string };
type Bird = { id: string; name?: string; sex?: string; status?: string; hatchDate?: string; colour?: string; strain?: string; eyeSign?: string; breeder?: string; owner?: string; acquiredFrom?: string; acquiredDate?: string; external?: boolean; sireId?: string | null; damId?: string | null; rings?: Ring[]; notes?: Note[] };
type Problem = { key: string; params?: Record<string, unknown> };
type Role = 'sire' | 'dam';
type Picker = { role: Role; mode: 'pick' | 'create'; q: string } | null;
type Pending = { kind: 'photo' | 'document'; subtype: string; file: File };
const getBird = (id: string) => db.getBird(id) as Bird | undefined;
const REFERENCE_STATUS = db.REFERENCE_STATUS as string;

/** bird-form.js:162 — an engine problem rendered in words. */
function problemText(p: Problem): string {
  const params: Record<string, unknown> = { ...(p.params || {}) };
  if (typeof params.role === 'string') params.role = t('bird.' + params.role);
  if (Array.isArray(params.path)) params.path = (params.path as string[]).map((id) => { const b = getBird(id); return b ? (b.name || (b.rings && b.rings[0] && b.rings[0].raw) || id.slice(0, 6)) : id.slice(0, 6); }).join(' ← ');
  if (params.otherId && !params.otherName) { const ob = getBird(params.otherId as string); params.otherName = ob ? (ob.name || '') : ''; }
  return t(p.key, params);
}
/** Which field an engine problem belongs to — for the .err state and the dialog's field column. */
const fieldOf = (p: Problem): 'ring' | 'sire' | 'dam' | 'form' => {
  if (/dupRing/.test(p.key)) return 'ring';
  const role = p.params && (p.params as { role?: string }).role;
  if (role === 'sire' || role === 'dam') return role;
  if (/sireIsHen/.test(p.key)) return 'sire';
  if (/damIsCock/.test(p.key)) return 'dam';
  if (/selfParent|cycle|sameSireDam|parentSameDay/.test(p.key)) return 'sire';
  return 'form';
};
const fieldLabel = { ring: 'bird.ring', sire: 'bird.sire', dam: 'bird.dam', form: 'bird.one' } as const;
const Dot = ({ sex }: { sex?: string }) => <span className={s.dot}><svg viewBox="0 0 100 100" fill={sex === 'hen' ? '#C9971F' : '#128C6E'} aria-hidden="true"><path d="M18 78c14 4 34 4 46-4 10-7 16-18 17-30 0-4-2-6-5-6-2 0-4 1-5 3l-4 8c-6 10-16 16-28 18-8 1-15 5-21 11z" /><path d="M62 34c3-6 9-9 15-8 3 0 5 2 5 5 0 2-1 3-3 4l-6 2c-4 2-8 1-11-3z" /></svg></span>;
const Plate = ({ b }: { b: Bird }) => { const r = (b.rings || []).find((x) => x.type === 'FCI') || (b.rings || [])[0]; const raw = primaryRing(b); return raw ? <span className={s.plate}><span className={s.yr}>{r && r.year ? String(r.year).slice(-2) : ''}</span><span className={s.no}>{raw}</span></span> : null; };

export default function BirdForm() {
  const pathname = usePathname() ?? ''; const params = useSearchParams(); const router = useRouter();
  const isNew = /\/bird\/new(\.html)?\/?$/.test(pathname);   // a plain file server serves the export as /bird/new.html; a static host as /bird/new
  const editId = isNew ? null : (params.get('id') || '');
  const siblingOfId = isNew ? params.get('siblingOf') : null;
  const [booted, setBooted] = useState(false);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const birds = useZajilStore(selectBirds) as Bird[];

  const [draft, setDraft] = useState<Bird | null>(null);
  const [rings, setRings] = useState<Ring[]>([{}]);
  const [notes, setNotes] = useState('');
  const [pending, setPending] = useState<Pending[]>([]);
  const [picker, setPicker] = useState<Picker>(null);
  const [errs, setErrs] = useState<Partial<Record<'ring' | 'sire' | 'dam', string>>>({});
  const [busy, setBusy] = useState(false);
  const firstRing = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);
  const photoIn = useRef<HTMLInputElement>(null); const docIn = useRef<HTMLInputElement>(null);

  // bird-form.js:13-26 — the draft: a clone to edit, or a fresh record with the entry-point intents applied
  useEffect(() => {
    if (!booted || draft) return;
    const existing = editId ? getBird(editId) : null;
    if (editId && !existing) { router.replace('/birds'); return; }
    const d: Bird = existing ? JSON.parse(JSON.stringify(existing)) : (db.newBird({}) as Bird);
    if (!existing) {
      const qs = params.get('sire'), qd = params.get('dam');
      if (qs && getBird(qs)) d.sireId = qs;
      if (qd && getBird(qd)) d.damId = qd;
    }
    setDraft(d); setRings(d.rings && d.rings.length ? d.rings.map((r) => ({ ...r })) : [{}]);
  }, [booted, draft, editId, params, router]);

  // the picker closes on an outside click (ui.js:352) — abandoning a search never touches the committed parent
  useEffect(() => {
    if (!picker) return;
    const onDoc = (e: MouseEvent) => { if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) setPicker(null); };
    document.addEventListener('mousedown', onDoc); return () => document.removeEventListener('mousedown', onDoc);
  }, [picker]);

  const siblingOf = siblingOfId ? getBird(siblingOfId) : null;
  const statuses = useMemo(() => (booted ? (db.loftStatuses() as string[]) : []), [booted]);   // eslint-disable-line react-hooks/exhaustive-deps

  /** bird-form.js:140 collect — the record as it would be saved. */
  const collect = (d: Bird = draft!): Bird => {
    const rs = rings.map((r) => { const parsed = parseRing(r.raw || '', r.type || 'national') as Ring; parsed.type = (r.type || 'national') === 'national' && parsed.type === 'FCI' ? 'FCI' : (r.type || 'national'); return parsed; }).filter((r) => r.raw);
    return { ...d, name: (d.name || '').trim(), colour: (d.colour || '').trim(), strain: (d.strain || '').trim(), eyeSign: (d.eyeSign || '').trim(), breeder: (d.breeder || '').trim(), owner: (d.owner || '').trim(), acquiredFrom: (d.acquiredFrom || '').trim(),
      external: !!d.external, status: d.external ? REFERENCE_STATUS : (d.status === REFERENCE_STATUS ? 'stock' : (d.status || 'stock')), rings: rs };
  };
  // live duplicate-ring warning (spec's warnbox): the engine's own rule, re-run as the rings change
  const dup = useMemo(() => {
    if (!draft) return null;
    const { warnings } = db.checkBird(collect()) as { warnings: Problem[] };
    const w = warnings.find((p) => p.key === 'val.dupRing');
    if (!w) return null;
    const other = w.params && getBird((w.params as { otherId?: string }).otherId || '');
    return other ? { id: other.id, name: other.name || primaryRing(other) || other.id.slice(0, 8) } : null;
  }, [draft, rings, birds]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!booted || !draft) return <section className={s.screen}><Loading /></section>;
  const set = (patch: Partial<Bird>) => setDraft({ ...draft, ...patch });
  const loft = db.currentLoft() as { name?: string } | null;
  const sire = draft.sireId ? getBird(draft.sireId) : null; const dam = draft.damId ? getBird(draft.damId) : null;
  const ringYear = rings.map((r) => (parseRing(r.raw || '', r.type || 'national') as Ring).year).find(Boolean);

  // ── save (bird-form.js:178-246) ──
  async function doSave(bird: Bird, andNew: boolean, opts: { allowWarnings?: boolean } = {}) {
    setBusy(true);
    try {
      if (siblingOf && !bird.sireId && !bird.damId) {
        // deferred sibling intent: mint the placeholders now, attach them to BOTH birds, only then persist
        const ps = await db.saveBird(db.newBird({ name: t('bird.unknownSire'), sex: 'cock', external: true })) as Bird;
        const pd = await db.saveBird(db.newBird({ name: t('bird.unknownDam'), sex: 'hen', external: true })) as Bird;
        bird.sireId = ps.id; bird.damId = pd.id;
        await db.saveBird({ ...siblingOf, sireId: ps.id, damId: pd.id }, { allowWarnings: true });
      }
      if (notes.trim()) bird.notes = [...(bird.notes || []), { id: db.uuid(), at: db.nowISO(), text: notes.trim() }];
      await db.saveBird(bird, opts);
      for (const m of pending) await db.addMedia(bird.id, m.kind, m.subtype, m.file.name, m.file);
      if (andNew) {
        // stay in the entry rhythm: a fresh form carrying the batch-constant fields and the ring prefix
        toast(t('toast.savedNext', { name: bird.name || (bird.rings && bird.rings[0] && bird.rings[0].raw) || '' }), { kind: 'success' });
        const r0 = bird.rings && bird.rings[0];
        setDraft(db.newBird({ strain: bird.strain, colour: bird.colour, status: bird.status, breeder: bird.breeder, owner: bird.owner, external: bird.external }) as Bird);
        setRings([{ raw: r0 && r0.country && r0.year ? `${r0.country}-${r0.year}-` : '', type: r0 ? r0.type : 'national' }]);
        setNotes(''); setPending([]); setErrs({}); setPicker(null);
        setTimeout(() => { const el = firstRing.current; if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }, 0);
        return;
      }
      toast(t('toast.saved'), { kind: 'success' });
      router.replace(`/bird?id=${bird.id}`);   // replace, not push: the phone back gesture returns to the list
    } finally { setBusy(false); }
  }
  async function submit(andNew: boolean) {
    const bird = collect();
    const { errors, warnings } = db.checkBird(bird) as { errors: Problem[]; warnings: Problem[] };
    const fe: typeof errs = {};
    for (const p of errors) { const f = fieldOf(p); if (f !== 'form' && !fe[f]) fe[f] = problemText(p); }
    setErrs(fe);
    if (errors.length) {
      await confirmDialog({ title: t('val.cannotSave'), body: t('val.fieldsNeedFix', { n: errors.length }), list: { kind: 'errs', items: errors.map((p) => ({ field: t(fieldLabel[fieldOf(p)]), text: problemText(p) })) }, cancelLabel: t('val.backToForm'), confirmLabel: null, confirmKind: 'primary' });
      return;
    }
    if (warnings.length) {
      const ok = await confirmDialog({ title: t('val.warningsTitle'), list: { kind: 'warns', items: warnings.map((p) => ({ field: t(fieldLabel[fieldOf(p)]), text: problemText(p) })) }, cancelLabel: t('act.cancel'), confirmLabel: t('act.saveAnyway'), confirmKind: 'primary' });
      if (!ok) return;
      await doSave(bird, andNew, { allowWarnings: true }); return;
    }
    await doSave(bird, andNew);
  }
  const cancel = () => { if (window.history.length > 1) router.back(); else router.push('/birds'); };
  // Enter must never save a half-entered bird — advance focus instead (bird-form.js:249)
  const onKeyDown = (e: React.KeyboardEvent<HTMLFormElement>) => {
    if (e.key === 'Enter' && e.target instanceof HTMLInputElement) {
      e.preventDefault();
      const els = [...e.currentTarget.querySelectorAll<HTMLElement>('input, select, textarea')].filter((x) => !(x as HTMLInputElement).disabled && x.offsetParent !== null);
      const i = els.indexOf(e.target); if (i >= 0 && i < els.length - 1) els[i + 1].focus();
    }
  };

  // ── the parent picker (ui.js:205 birdPicker, in the spec's slot grammar) ──
  // the picker's rules live once, in src/components/picker.ts (ui.js:205)
  const pool = (role: Role) => birds.filter((b) => b.id !== draft.id && b.sex !== (role === 'sire' ? 'hen' : 'cock'));
  const pick = (role: Role, id: string) => { set(role === 'sire' ? { sireId: id } : { damId: id }); setErrs({ ...errs, [role]: undefined }); setPicker(null); };
  async function quickCreate(role: Role, q: string) {
    const b = await createFromQuery(q, role === 'sire' ? 'cock' : 'hen');   // re-checks for an exact match first, so a second tap cannot mint a duplicate
    pick(role, b.id);
  }
  const Slot = ({ role, b }: { role: Role; b: Bird | null | undefined }) => {
    const open = picker && picker.role === role ? picker : null;
    const q = open ? open.q : '';
    const model = pickerModel({ all: birds, pool: pool(role), q, allowCreate: open?.mode === 'create', selected: b ? b.id : null });
    const blocked = open && open.mode === 'pick' ? model.blocked : null;
    const cands = open && open.mode === 'pick' ? model.cands : [];
    return (
      <div ref={open ? pickerRef : undefined} data-testid={`slot-${role}`}>
        {b ? (
          <div className={s.prow} data-testid={`parent-${role}`}>
            <Dot sex={b.sex} />
            <span className={s.mid}><span className={s.role}>{t('bird.' + role)}</span><span className={s.nm} data-testid={`parent-${role}-name`}><bdi>{b.name || primaryRing(b) || b.id.slice(0, 8)}</bdi></span><Plate b={b} /></span>
            <button type="button" className={s.act} onClick={() => setPicker({ role, mode: 'pick', q: '' })} data-testid={`parent-${role}-change`}>{t('act.change')}</button>
            <button type="button" className={s.act} onClick={() => { set(role === 'sire' ? { sireId: null } : { damId: null }); setPicker(null); }} data-testid={`parent-${role}-clear`}>{t('bird.clearParent')}</button>
          </div>
        ) : null}
        {b && errs[role] && <div className={s['err-msg']} role="alert" style={{ marginTop: -4, marginBottom: 10 }}>{errs[role]}</div>}
        {!b && (
          <div className={s.pempty} data-testid={`parent-${role}-empty`}>
            <div className={s.head}><span className={`${s.dot}`}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg></span>
              <div><div className={s.role}>{t('bird.' + role)}</div><div className={s.nm}>{t('form.parent.none')}</div></div></div>
            {errs[role] && <div className={s['err-msg']} role="alert">{errs[role]}</div>}
            <div className={s.btns}>
              <button type="button" className={`${s.primary} ${open && open.mode === 'pick' ? s.on : ''}`} onClick={() => setPicker({ role, mode: 'pick', q: '' })} data-testid={`parent-${role}-pick`}>{t('form.parent.pick')}</button>
              <button type="button" className={`${s.ghost} ${open && open.mode === 'create' ? s.on : ''}`} onClick={() => setPicker({ role, mode: 'create', q: '' })} data-testid={`parent-${role}-create`}>{t('form.parent.quick')}</button>
            </div>
          </div>
        )}
        {open && (
          <div className={s.picker} data-testid={`picker-${role}`}>
            <div className={s.field}>
              <input autoFocus value={q} onChange={(e) => setPicker({ ...open, q: e.target.value })} placeholder={open.mode === 'pick' ? t('bird.chooseBird') : t('bird.ring') + ' / ' + t('bird.name')} aria-label={open.mode === 'pick' ? t('form.parent.pick') : t('form.parent.quick')} data-testid="picker-input" />
            </div>
            {open.mode === 'pick' ? (
              <>
                {blocked && <div className={s.note} data-testid="picker-note">{t('picker.existsButFiltered', { name: birdLabelText(blocked), sex: t('sex.' + (blocked.sex || 'unknown')) })}</div>}
                <div className={s.list}>
                  {cands.map((c) => (
                    <button key={c.id} type="button" className={s.prow} onClick={() => pick(role, c.id)} data-testid="picker-item">
                      <Dot sex={c.sex} /><span className={s.mid}><span className={s.nm}><bdi>{c.name || primaryRing(c) || c.id.slice(0, 8)}</bdi></span><Plate b={c} /></span><SexChip sex={c.sex} />
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                {/* ui.js:278 — a query that already resolves to a real bird is never an offer to create a
                    second record for it, even when THIS slot could not select that bird. The action guards
                    itself too (createFromQuery re-checks), but the offer must not be there in the first place. */}
                {model.clash && <div className={s.note} data-testid="picker-note">{model.blocked
                  ? t('picker.existsButFiltered', { name: birdLabelText(model.clash), sex: t('sex.' + (model.clash.sex || 'unknown')) })
                  : t('warn.dupRing.body', { name: birdLabelText(model.clash) })}</div>}
                <button type="button" className={s.create} disabled={!model.canCreate} onClick={() => quickCreate(role, q.trim())} data-testid="picker-create">
                  + {t('picker.createNew', { q: q.trim() })}<small>{t('picker.createHint')}</small>
                </button>
              </>
            )}
          </div>
        )}
      </div>
    );
  };
  const Field = ({ label, children, hint, testid }: { label: string; children: ReactNode; hint?: ReactNode; testid?: string }) => (
    <div className={s.field} data-testid={testid}><label>{label}</label>{children}{hint}</div>
  );

  return (
    <section className={s.screen}>
      <div className={s.col}>
        <div className={s.top}><div className={s.bar}>
          <button type="button" className={s['icon-btn']} aria-label={t('act.back')} onClick={cancel} data-testid="back-btn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg></button>
          <span className={s.crumb}>{t('nav.birds')}</span><span className={s.spacer} />
        </div></div>
        <header className={s.formhead}>
          <h1 data-testid="form-title">{isNew ? t('act.newBird') : t('act.edit')}</h1>
          <p>{loft?.name || t('loft.unnamed')} · {seasonLabel()}</p>
        </header>
        <form className={s.body} noValidate onSubmit={(e) => { e.preventDefault(); submit(false); }} onKeyDown={onKeyDown} data-testid="bird-form">
          {siblingOf && <div className={s.warnbox} data-testid="sibling-notice"><div className={s.t}>{t('bird.siblingOfNotice', { name: siblingOf.name || primaryRing(siblingOf) || '' })}</div></div>}
          <div className={s.seclbl}>{t('form.sec.basics')}</div>
          <div className={s.card}>
            <div className={s.photo}>
              <button type="button" aria-label={t('bird.addPhoto')} onClick={() => photoIn.current?.click()} data-testid="photo-btn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg></button>
              <div><div className={s.t}>{t('bird.addPhoto')}</div><p>{t('form.photo.hint')}</p>
                {/* not a <button>: the spec's .photo button rule is the 92px photo tile */}
                <span role="button" tabIndex={0} className={s.linkbtn} onClick={() => docIn.current?.click()} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); docIn.current?.click(); } }} data-testid="doc-btn">{t('bird.addDocument')}</span>
                {pending.length > 0 && <div className={s.filelist} data-testid="pending-media">{pending.map((m) => m.file.name).join(' · ')}</div>}
                <input ref={photoIn} type="file" accept="image/*" multiple hidden onChange={(e) => { const fs = [...(e.target.files || [])]; setPending([...pending, ...fs.map((f) => ({ kind: 'photo' as const, subtype: 'body', file: f }))]); e.target.value = ''; }} />
                <input ref={docIn} type="file" accept="image/*,.pdf" multiple hidden onChange={(e) => { const fs = [...(e.target.files || [])]; setPending([...pending, ...fs.map((f) => ({ kind: 'document' as const, subtype: 'other', file: f }))]); e.target.value = ''; }} />
              </div>
            </div>
            <Field label={t('bird.name')}><input value={draft.name || ''} onChange={(e) => set({ name: e.target.value })} placeholder={t('form.name.placeholder')} data-testid="f-name" /></Field>
            <Field label={t('bird.ring')} testid="f-ring-field">
              {rings.map((r, i) => (
                <div key={i} className={i === 0 ? undefined : s.ringrow} data-testid="ring-row">
                  <input ref={i === 0 ? firstRing : undefined} className={`${s.data} ${i === 0 && dup ? s.warn : ''} ${i === 0 && errs.ring ? s.err : ''}`} dir="ltr" lang="en" autoCapitalize="characters" autoCorrect="off" spellCheck={false} placeholder="JO-2026-12345"
                    value={r.raw || ''} onChange={(e) => { const next = rings.slice(); next[i] = { ...r, raw: e.target.value }; setRings(next); }} data-testid="ring-input" />
                  {i > 0 && <>
                    <select value={r.type || 'national'} onChange={(e) => { const next = rings.slice(); next[i] = { ...r, type: e.target.value }; setRings(next); }} aria-label={t('bird.rings')} data-testid="ring-type">{(RING_TYPES as string[]).map((rt) => <option key={rt} value={rt}>{t('ringType.' + rt)}</option>)}</select>
                    <button type="button" className={s.x} aria-label={t('act.delete')} onClick={() => setRings(rings.filter((_, j) => j !== i))} data-testid="ring-remove">✕</button>
                  </>}
                </div>
              ))}
              {errs.ring && <div className={s['err-msg']} role="alert" data-testid="ring-error">{errs.ring}</div>}
              {dup && (
                <div className={s.warnbox} data-testid="dup-warn">
                  <div className={s.t}>{t('warn.dupRing.title')}</div>
                  <p>{t('warn.dupRing.body', { name: dup.name })}</p>
                  <Link href={`/bird?id=${dup.id}`} data-testid="dup-view">{t('warn.dupRing.view')}</Link>
                </div>
              )}
              <button type="button" className={s.linkbtn} onClick={() => setRings([...rings, { type: 'national' }])} data-testid="ring-add">+ {t('bird.ring')}</button>
            </Field>
            <Field label={t('bird.sex')}>
              <div className={s.seg} role="group" data-testid="sex-seg">
                {(['cock', 'hen', 'unknown'] as const).map((sx) => <button key={sx} type="button" aria-pressed={(draft.sex || 'unknown') === sx} onClick={() => set({ sex: sx })} data-testid="sex-btn" data-sex={sx}>{t('sex.' + sx)}</button>)}
              </div>
            </Field>
            {!draft.external && (
              <Field label={t('bird.status')} testid="f-status">
                <div className={s.chips} role="group">
                  {statuses.map((st) => <button key={st} type="button" aria-pressed={(draft.status === REFERENCE_STATUS ? 'stock' : draft.status) === st} onClick={() => set({ status: st })} data-testid="status-chip" data-status={st}>{statusLabel(st)}</button>)}
                </div>
              </Field>
            )}
            <Field label={t('bird.colour')}><input value={draft.colour || ''} onChange={(e) => set({ colour: e.target.value })} placeholder={t('form.colour.placeholder')} list="dl-colours" data-testid="f-colour" /></Field>
            <Field label={t('bird.hatchDate')} hint={!draft.hatchDate && ringYear ? <><button type="button" className={s.linkbtn} onClick={() => set({ hatchDate: ringYear + '-01-01' })} data-testid="hatch-hint">{t('bird.useRingYear', { year: String(ringYear) })}</button><div className={s.hintline}>{t('bird.approxFromRing')}</div></> : null}>
              <input type="date" className={s.data} value={draft.hatchDate || ''} onChange={(e) => set({ hatchDate: e.target.value })} data-testid="f-hatch" />
            </Field>
          </div>
          {/* vanilla's remaining fields (bird-form.js:280-285), in the spec's field grammar */}
          <div className={s.card} style={{ marginTop: 14 }} data-testid="more-fields">
            <div className={s.field} style={{ marginTop: 0 }}><label>{t('bird.strain')}</label><input value={draft.strain || ''} onChange={(e) => set({ strain: e.target.value })} list="dl-strains" data-testid="f-strain" /></div>
            <Field label={t('bird.eyeSign')}><input value={draft.eyeSign || ''} onChange={(e) => set({ eyeSign: e.target.value })} data-testid="f-eye" /></Field>
            <Field label={t('bird.breeder')}><input value={draft.breeder || ''} onChange={(e) => set({ breeder: e.target.value })} list="dl-breeders" data-testid="f-breeder" /></Field>
            <Field label={t('bird.owner')}><input value={draft.owner || ''} onChange={(e) => set({ owner: e.target.value })} data-testid="f-owner" /></Field>
            <Field label={t('bird.acquiredFrom')}><input value={draft.acquiredFrom || ''} onChange={(e) => set({ acquiredFrom: e.target.value })} data-testid="f-acq" /></Field>
            <Field label={t('bird.acquiredDate')}><input type="date" className={s.data} value={draft.acquiredDate || ''} onChange={(e) => set({ acquiredDate: e.target.value })} data-testid="f-acq-date" /></Field>
            <datalist id="dl-strains">{[...new Set(birds.map((b) => b.strain).filter(Boolean))].sort().map((v) => <option key={v} value={v} />)}</datalist>
            <datalist id="dl-colours">{[...new Set(birds.map((b) => b.colour).filter(Boolean))].sort().map((v) => <option key={v} value={v} />)}</datalist>
            <datalist id="dl-breeders">{[...new Set(birds.map((b) => b.breeder).filter(Boolean))].sort().map((v) => <option key={v} value={v} />)}</datalist>
          </div>

          <div className={s.seclbl}>{t('tab.pedigree')}</div>
          <Slot role="sire" b={sire} />
          <Slot role="dam" b={dam} />
          <div className={s['toggle-card']} data-testid="external-card">
            <div className={s.mid}><div className={s.t}>{t('form.external.title')}</div><p>{t('form.external.body')}</p></div>
            <button type="button" className={s.switch} role="switch" aria-checked={!!draft.external} aria-label={t('form.external.title')} onClick={() => set({ external: !draft.external })} data-testid="external-switch"><span /></button>
          </div>

          <div className={s.seclbl}>{t('common.notes')}</div>
          <textarea className={s.notes} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t('form.notes.placeholder')} aria-label={t('bird.addNote')} data-testid="f-notes" />

          <div className={s.actions} data-bottom-chrome="actions"><div className={s.inner}>
            <button type="button" className={s.cancel} onClick={cancel} data-testid="cancel-btn">{t('act.cancel')}</button>
            {isNew && <button type="button" className={s.alt} disabled={busy} onClick={() => submit(true)} data-testid="save-new-btn">{t('act.saveAndNew')}</button>}
            <button type="submit" className={s.save} disabled={busy} data-testid="save-btn">{t('act.save')}</button>
          </div></div>
        </form>
      </div>
    </section>
  );
}
