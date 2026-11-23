'use client';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { useZajilStore, selectBirds } from '@/src/db/react';
import { t, fmtDate, fmtNum } from '@/src/i18n.ext.js';
import { findDuplicateRings } from '@/src/engine/rings.js';
import { todayISO } from '@/src/dates.js';
import { toast, confirmDialog, downloadBlob, primaryRing, saveSetting, asset } from '@/src/components';
import { Icon, type IconName } from './icons';
import s from './tools.module.css';

/**
 * The pieces of الأدوات — design/approved/tools-v2.html, behaviour from the tools-v1 port
 * (which took it from js/views/tools.js). The list (view.tsx) and the four sub-screens
 * (screens.tsx) are assembled from what is here; nothing here decides WHERE a control sits.
 *
 * Every testid a tools-v1 control carried is carried by the same control here, and
 * tests/e2e/screens/tools.py walks that list: it passing is the proof that the restructure
 * lost no control. One rename, recorded there: tools-v1's snapshot <select> (snap-select)
 * became the spec's snapshot LIST (snap-row), each row with its own «استرجاع».
 */
export type Loft = { id: string; name?: string; location?: string; breederName?: string; phone?: string; website?: string; logoMediaId?: string | null };
export type Bird = { id: string; name?: string; rings?: Array<{ raw?: string }>; sireId?: string | null; damId?: string | null };
export type Backup = { id: string; payload?: { birds?: unknown[] } };
export type SyncStatus = { photosWaiting?: number; storageFull?: boolean; pending: number; pendingSince?: string | null; state: string; error?: { key: string; status?: number | null; at?: string } | null };
export type Anomaly = { store?: string; recordId?: string; reason?: string; at?: string };
export const Lofts = db.Lofts as { save: (l: Loft) => Promise<Loft> };

// V8's maximum string length, measured as the exact boundary: at this size File.text()
// still returns the whole file; one byte more and it returns "" with no error.
export const MAX_IMPORT_BYTES = 536870888;

// ── the grouped list's primitives ────────────────────────────────────────────────────
const OpenCtx = createContext<{ open: string | null; toggle: (id: string) => void }>({ open: null, toggle: () => {} });

/** A section of the list. Only ONE row is open at a time inside it — the spec's toggle handler (tools-v2.html:649-656). */
export function Section({ id, title, note, foot, defaultOpen = null, children }: { id: string; title: string; note?: string; foot?: string; defaultOpen?: string | null; children: React.ReactNode }) {
  const [open, setOpen] = useState<string | null>(defaultOpen);
  const toggle = (rowId: string) => setOpen((cur) => (cur === rowId ? null : rowId));
  return (
    <section className={s.section} id={id} data-testid="section" data-section={id}>
      <div className={s.sectionHead}><h2>{title}</h2>{note && <span className={s.note}>{note}</span>}</div>
      <OpenCtx.Provider value={{ open, toggle }}><div className={s.groupList}>{children}</div></OpenCtx.Provider>
      {foot && <p className={s.groupFoot}>{foot}</p>}
    </section>
  );
}

type RowProps = {
  id: string; icon: IconName; label: string; help?: string;
  value?: React.ReactNode | ((open: boolean) => React.ReactNode); valueKind?: 'brand' | 'gold' | 'data' | 'num';
  testid?: string; href?: string; children?: React.ReactNode;
};

/**
 * A settings row. Inline, it is the spec's <details> — summary grid of icon · label/help · value · chevron, and the
 * detail below. With `href` it NAVIGATES instead (HYBRID SHAPE, RULED 2026-10-03): the same grid as an <a> to a real
 * route, for the four controls the list has no room for.
 */
export function Row({ id, icon, label, help, value, valueKind, testid, href, children }: RowProps) {
  const { open, toggle } = useContext(OpenCtx);
  const isOpen = !href && open === id;
  const v = typeof value === 'function' ? value(isOpen) : value;
  const summary = (
    <>
      <span className={s.rowIcon} aria-hidden="true"><Icon name={icon} /></span>
      <span className={s.rowCopy}><span className={s.rowLabel}>{label}</span>{help && <span className={s.rowHelp} data-testid="row-help">{help}</span>}</span>
      <span className={`${s.rowValue} ${valueKind ? s[valueKind] : ''}`} data-testid="row-value">{v}</span>
      <Icon name="chevron" className={s.chev} />
    </>
  );
  if (href) return <Link href={href} className={`${s.row} ${s.link}`} data-testid={testid || `row-${id}`} data-row={id}>{summary}</Link>;
  return (
    <details className={s.details} open={isOpen} data-testid={testid || `row-${id}`} data-row={id}>
      {/* controlled: the native toggle is prevented and the section decides which row is open */}
      <summary className={s.row} onClick={(e) => { e.preventDefault(); toggle(id); }}>{summary}</summary>
      <div className={s.detail}><div className={s.detailInner}>{children}</div></div>
    </details>
  );
}

/** The spec's status line: a glyph, a title, an optional text and an optional code line. Gold colours the ICON only. */
export function StatusLine({ icon, title, text, code, gold, testid, state }: { icon: IconName; title: React.ReactNode; text?: React.ReactNode; code?: string; gold?: boolean; testid?: string; state?: string }) {
  return (
    <div className={`${s.status} ${gold ? s.gold : ''}`} data-testid={testid} data-state={state}>
      <Icon name={icon} small className={s.statusIcon} />
      <div className={s.statusMain}>
        <div className={s.statusTitle}>{title}</div>
        {text && <div className={s.statusText}>{text}</div>}
        {code && <div className={`${s.statusCode} ${s.data}`}>{code}</div>}
      </div>
    </div>
  );
}

/** Segmented control. Declared at module scope (a render-body component remounts on every render and drops the caret). */
export function Seg({ k, options, current, set, label }: { k: string; options: Array<[string, React.ReactNode]>; current: string; set: (k: string, v: unknown) => void; label: string }) {
  return (
    <div className={s.seg} role="group" aria-label={label} data-testid={`set-${k}`}>
      {options.map(([v, node]) => <button key={v} type="button" aria-pressed={current === v} onClick={() => set(k, v)} data-testid="seg-btn" data-value={v}>{node}</button>)}
    </div>
  );
}

/** The sub-screen chrome: a real route with a back link, so it survives a back gesture and a reload. */
export function SubScreen({ title, help, children, testid }: { title: string; help?: string; children: React.ReactNode; testid: string }) {
  return (
    <section className={s.screen} data-testid={testid}>
      <header className={s.head}><div className={s.headIn}>
        <Link href="/tools" className={s.back} aria-label={t('act.back')} data-testid="back-link"><svg viewBox="0 0 24 24" className={s.icon} aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg><span>{t('nav.tools')}</span></Link>
        <h1>{title}</h1>
        {help && <div className={s.sub}>{help}</div>}
      </div></header>
      <main className={s.content}><div className={s.detailInner}>{children}</div></main>
    </section>
  );
}

// ── sync ─────────────────────────────────────────────────────────────────────────────
/**
 * The sync row's value and help for every state — the spec's apply() map (tools-v2.html:605-630), keyed by the
 * layer's own vocabulary (syncStatus().state: synced · offline · syncing · pending · error · off) plus the two
 * account states and the rejected-records case the spec draws as its own state.
 */
export function syncRowCopy(settings: Record<string, unknown>, cfg: { configured: boolean }, auth: { signedIn: boolean }, status: SyncStatus, anomalies: Anomaly[]): { value: string; help: string; kind?: 'brand' | 'gold' } {
  if (!cfg.configured) return { value: t('tools.sync.notSetUpShort'), help: t('tools.sync.helpOff') };
  if (!auth.signedIn) return { value: t('tools.sync.stopped'), help: t('tools.sync.helpOut') };
  if (settings.syncEnabled === false || status.state === 'off') return { value: t('tools.sync.stopped'), help: t('sync.off') };
  if (status.state === 'error' && status.error) return { value: t('tools.sync.errorShort'), help: t(status.error.key), kind: 'gold' };
  if (anomalies.length) return { value: t('tools.sync.rejectedShort', { n: fmtNum(anomalies.length) }), help: t('tools.sync.helpRejected'), kind: 'gold' };
  if (status.state === 'pending') return { value: t('tools.sync.pendingShort'), help: t('tools.sync.helpPending'), kind: 'gold' };
  if (status.state === 'syncing') return { value: t('tools.sync.syncingShort'), help: t('tools.sync.helpSyncing'), kind: 'brand' };
  if (status.state === 'offline') return { value: t('tools.sync.offlineShort'), help: t('tools.sync.helpOffline') };
  // HONEST STATUS (RF-19): 'unknown' — the op log not yet counted after a load, or a failure still inside its quiet window — claims nothing
  if (status.state === 'unknown') return { value: '', help: `${t('sync.lastSync')} ${settings.lastSyncAt ? fmtDate(settings.lastSyncAt as string, { withTime: true }) : t('sync.never')}` };
  return { value: t('sync.synced'), help: settings.lastSyncAt ? t('tools.sync.syncedSince', { d: fmtDate(settings.lastSyncAt as string, { withTime: true }) }) : `${t('sync.lastSync')} ${t('sync.never')}`, kind: 'brand' };
}

type Line = { icon: IconName; title: string; text?: string; code?: string; gold?: boolean; testid?: string };

/** The signed-in sync detail: the status line, last sync, pending, rejected records, and the two actions. */
export function SyncDetail({ settings }: { settings: Record<string, unknown> }) {
  const [busy, setBusy] = useState(false);
  useZajilStore((x) => x);   // re-render on every layer change; the status is read fresh below, as tools-v1 did
  const status = db.syncStatus() as SyncStatus;
  const anomalies = (db.listSyncAnomalies ? db.listSyncAnomalies() : []) as Anomaly[];
  const enabled = settings.syncEnabled !== false;
  // «مزامنة الآن» (RULED 2026-11-17): a cycle does not throw — it RETURNS its failure — and the button said «تم الحفظ»
  // whatever came back. A cycle that did not complete is now said, with the layer's own reason.
  async function pressSync() {
    setBusy(true);
    try {
      await destructive(async () => {
        const r = await db.syncNow() as { ok?: boolean; reason?: string } | undefined;
        if (r && r.ok === false) {
          const err = (db.syncStatus() as SyncStatus).error;
          toast(t('tools.failed.action', { what: t('sync.now'), reason: err ? t(err.key) : t('tools.failed.unknown', { what: r.reason || '' }) }), { kind: 'error', timeout: 12000 });
        } else toast(t('toast.saved'), { kind: 'success' });
      }, failedAction(t('sync.now')));
    } finally { setBusy(false); }
  }
  // 2 the toggle
  const toggle = () => destructive(async () => { await db.setSyncEnabled(!enabled); await db.refreshSyncStatus(); }, failedAction(t(enabled ? 'sync.toggleOff' : 'sync.toggleOn')));
  const line: Line = status.state === 'error' && status.error
    ? { icon: 'alert', gold: true, testid: 'sync-error',
        title: `${t('sync.lastError')}: ${t(status.error.key)}`,
        // the spec's hint is written for the session case; it is wrong advice for a network or server failure
        text: status.error.key === 'sync.err.session' ? t('tools.sync.errorHint') : undefined,
        code: [status.error.status ? `HTTP ${status.error.status}` : '', status.error.at ? fmtDate(status.error.at, { withTime: true }) : ''].filter(Boolean).join(' · ') || undefined }
    : status.state === 'pending' ? { icon: 'clock', title: status.pendingSince ? t('sync.pendingSince', { d: fmtDate(status.pendingSince, { withTime: true }) }) : t('sync.pending'), text: t('tools.sync.st.pendingText') }
    : status.state === 'unknown' ? { icon: 'clock', title: `${t('sync.lastSync')}: ${settings.lastSyncAt ? fmtDate(settings.lastSyncAt as string, { withTime: true }) : t('sync.never')}` }
    : status.state === 'syncing' ? { icon: 'sync', title: t('sync.syncing'), text: t('tools.sync.st.syncingText') }
    : status.state === 'offline' ? { icon: 'offline', title: t('sync.offline'), text: t('tools.sync.st.offlineText') }
    : status.state === 'off' || !enabled ? { icon: 'off', title: t('sync.off') }
    : { icon: 'check', title: t('tools.sync.st.synced'), text: t('tools.sync.st.syncedText') };
  return (
    <div data-testid="sync-detail" data-state={status.state}>
      <StatusLine icon={line.icon} gold={line.gold} testid={line.testid || 'sync-status'} state={status.state} title={line.title} text={line.text} code={line.code} />
      {anomalies.length > 0 && <StatusLine icon="list" gold title={t('sync.anomalies', { n: fmtNum(anomalies.length) })} text={t('tools.sync.rejectedText')} />}
      {/* PHOTO SYNC, STAGE 2 (RULED 2026-11-19): photos waiting, and storage that is full, beside the record state */}
      {status.state !== 'hidden' && (status.photosWaiting || 0) > 0 && <StatusLine icon="clock" testid="photos-waiting" title={t('sync.photosWaiting', { n: fmtNum(status.photosWaiting || 0) })} />}
      {status.storageFull && <StatusLine icon="alert" gold testid="storage-full" title={t('media.storageFull')} />}
      <div className={s.kv}>
        <div className={s.kvRow}><span className={s.kvK}>{t('sync.lastSync')}</span><span className={s.kvV}>{settings.lastSyncAt ? fmtDate(settings.lastSyncAt as string, { withTime: true }) : t('sync.never')}</span></div>
      </div>
      {anomalies.length > 0 && (
        <ul className={s.list} data-testid="sync-anomalies">
          {anomalies.slice(0, 10).map((a, i) => <li key={i} className={s.item}><div className={s.t}>{a.reason || a.store}</div><div className={`${s.m} ${s.data}`}>{a.store}{a.at ? ' · ' + a.at.slice(0, 10) : ''}</div></li>)}
        </ul>
      )}
      <div className={s.actions}>
        <button type="button" className={`${s.btn} ${s.primary}`} disabled={busy} onClick={pressSync} data-testid="sync-now">{t('sync.now')}</button>
        <button type="button" className={s.btn} onClick={toggle} data-testid="sync-toggle">{enabled ? t('sync.toggleOff') : t('sync.toggleOn')}</button>
      </div>
    </div>
  );
}

// ── the duplicate-ring finder (picker_duplicates #8–10), with tools-v1's per-copy delete ──
export function DuplicatesDetail() {
  const st = useZajilStore((x) => x);
  const birds = useZajilStore(selectBirds) as Bird[];
  const groups = findDuplicateRings(birds) as Array<{ key: string; birds: Bird[] }>;
  const links = (b: Bird) => {
    const kids = birds.filter((x) => x.sireId === b.id || x.damId === b.id).length;
    const pairs = [...(st.pairs.values() as Iterable<{ sireId?: string; damId?: string }>)].filter((p) => p.sireId === b.id || p.damId === b.id).length;
    const races = [...(st.raceResults.values() as Iterable<{ birdId?: string }>)].filter((r) => r.birdId === b.id).length;
    const health = [...(st.healthEvents.values() as Iterable<{ birdId?: string }>)].filter((h) => h.birdId === b.id).length;
    const kinds = [kids && t('kind.pedigree'), pairs && t('kind.pairs'), races && t('kind.races'), health && t('kind.health')].filter(Boolean) as string[];
    return { n: kids + pairs + races + health, kinds: kinds.join('، ') };
  };
  async function del(b: Bird) {
    const ok = await confirmDialog({ title: t('confirm.deleteBird.title'), who: { label: b.name || primaryRing(b) }, cancelLabel: t('act.cancel'), confirmLabel: t('act.delete'), confirmKind: 'danger' });
    if (ok) await destructive(async () => { await db.deleteBird(b.id); }, failedAction(t('act.delete')));
  }
  if (groups.length === 0) return <StatusLine icon="check" testid="dup-clean" title={t('dup.noneShort')} text={t('tools.dup.scanned')} />;
  return (
    <div data-testid="dup-found">
      <StatusLine icon="alert" gold title={t('dup.foundShort', { n: fmtNum(groups.length) })} />
      {groups.map((g) => (
        <div key={g.key} className={s.list} data-testid="dup-group">
          <div className={`${s.item} ${s.dupHead}`}><span className={s.plate}>{primaryRing(g.birds[0])}</span><span className={s.m}>{t('dup.copies', { n: fmtNum(g.birds.length) })}</span></div>
          {g.birds.map((b) => {
            const { n, kinds } = links(b);
            return (
              <div key={b.id} className={`${s.item} ${s.dupCopy}`} data-testid="dup-copy">
                <div>
                  <div className={s.t}><bdi>{b.name || primaryRing(b) || b.id.slice(0, 8)}</bdi></div>
                  <div className={`${s.dupLinks} ${n ? '' : s.none}`} data-testid="dup-links">{n ? t('dup.linkedTo', { n: fmtNum(n), kinds }) : t('dup.noLinks')}</div>
                </div>
                <button type="button" className={s.del} onClick={() => del(b)} data-testid="dup-delete">{t('act.delete')}</button>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ── data ─────────────────────────────────────────────────────────────────────────────
/** Export — the migration path. It must survive a real loft and say so while it works. */
export function ExportDetail({ settings }: { settings: Record<string, unknown> }) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  async function exportAll() {
    if (busy) return;                                  // a second click must not start a second pass
    setBusy(true); setProgress(null);
    try {
      // RF-4: the file carries the photos whose bytes are on this device; the toast says how many are not, and so are not in it
      let missing = 0;
      const blob = await db.exportAllBlob({ onProgress: (done: number, total: number) => setProgress({ done, total }), onMissing: (n: number) => { missing = n; } });
      downloadBlob(blob, `zajil-export-${todayISO()}.json`);
      await saveSetting('lastExport', new Date().toISOString());
      toast(t('toast.exported') + (missing ? ' ' + t('backup.mediaNotHere', { n: fmtNum(missing) }) : ''), { kind: 'success', timeout: missing ? 7000 : undefined });
    } catch (e) {
      toast(t('toast.exportFailed'), { kind: 'error' });   // a failure that says nothing is the defect this replaced
      console.error('export failed', e);
    } finally { setBusy(false); setProgress(null); }
  }
  return (
    <div>
      <p className={s.detailText}>{t('backup.lastExportLabel')}: <span data-testid="last-export">{settings.lastExport ? fmtDate(settings.lastExport as string) : t('backup.never')}</span></p>
      <div className={s.actions}>
        <button type="button" className={`${s.btn} ${s.primary} ${s.wide}`} onClick={exportAll} disabled={busy} aria-busy={busy} data-testid="export-all"><Icon name="export" small />{busy ? t('backup.exporting') : t('backup.exportAll')}</button>
        {busy && progress && progress.total > 0 ? <span className={s.detailNote} data-testid="export-progress">{t('backup.exportProgress', { n: fmtNum(progress.done), total: fmtNum(progress.total) })}</span> : null}
      </div>
    </div>
  );
}

/** Import — the mode (the spec's segmented control), the file picker, the size guard, and every failure surfaced. */
export function ImportDetail() {
  const [mode, setMode] = useState<'merge' | 'replace'>('merge');
  const [file, setFile] = useState<File | null>(null);
  const fileIn = useRef<HTMLInputElement>(null);
  async function importFile() {
    if (!file) return;
    // THE SIZE GUARD: past V8's cap File.text() resolves with "" and JSON.parse blames an empty file (tools-v1 port)
    if (file.size > MAX_IMPORT_BYTES) {
      toast(t('backup.importTooLarge', { size: fmtNum(Math.ceil(file.size / 1048576)), limit: fmtNum(Math.floor(MAX_IMPORT_BYTES / 1048576)) }), { timeout: 12000, kind: 'error' });
      return;
    }
    try {
      const payload = JSON.parse(await file.text());
      // RF-15: the file is read BEFORE the question, because the question now states what the replace removes. A payload
      // that is not an export is not asked about at all — importAll refuses it below and the toast says why.
      if (mode === 'replace' && payload && payload.format === 'zajil-export') {
        const p = db.replacePreview(payload) as ReplacePreview;
        // P3 (RULED 2026-11-16): the question counts the photos that go with the dropped birds and says they cannot be
        // recovered; «لن يُحذف شيء» is said only when that is true of photos too
        const photos = await db.replaceMediaLoss(payload) as number;
        const body = [p.removed ? t('confirm.replace.removes', { birds: fmtNum(p.removedBirds), others: fmtNum(p.removedOthers) }) : (photos ? '' : t('confirm.replace.removesNone')),
          photos ? t('confirm.replace.photos', { n: fmtNum(photos) }) : '',
          travels() ? t('confirm.replace.devices') : '', await unsentNote(), t('confirm.replace.continue')].filter(Boolean).join(' ');
        const ok = await confirmDialog({ title: t('confirm.replace.title'), body, cancelLabel: t('act.cancel'), confirmLabel: t('act.replace'), confirmKind: 'danger' });
        if (!ok) return;
      }
      const counts = await db.importAll(payload, mode) as { birds: number; pairs: number; raceResults: number; mediaRejected: number };
      // RF-24: media rows the file carried without bytes were rejected — the import says how many
      toast(t('backup.imported', { birds: fmtNum(counts.birds), pairs: fmtNum(counts.pairs), races: fmtNum(counts.raceResults) })
        + (counts.mediaRejected ? ' ' + t('backup.mediaRejected', { n: fmtNum(counts.mediaRejected) }) : ''), { timeout: counts.mediaRejected ? 12000 : 7000, kind: 'info' });
      setFile(null);
    } catch (e) {
      toast(t('backup.importFailed', { why: (e as Error)?.message || '' }), { timeout: 12000, kind: 'error' });
      console.error('import failed', e);
    }
  }
  return (
    <div>
      <div className={s.field}>
        <label>{t('backup.importModeLabel')}</label>
        <div className={s.seg} role="group" aria-label={t('backup.importModeLabel')} data-testid="import-mode">
          <button type="button" aria-pressed={mode === 'merge'} onClick={() => setMode('merge')} data-value="merge">{t('backup.importMode.merge')}</button>
          <button type="button" aria-pressed={mode === 'replace'} onClick={() => setMode('replace')} data-value="replace">{t('backup.importMode.replace')}</button>
        </div>
      </div>
      <div className={s.filebox}>
        <button type="button" className={s.btn} onClick={() => fileIn.current?.click()} data-testid="file-pick">{t('backup.chooseFile')}</button>
        <span className={`${s.fileName} ${file ? s.has : ''}`} data-testid="file-name">{file ? file.name : t('backup.noFile')}</span>
        <input ref={fileIn} type="file" accept=".json,application/json" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="file-input" />
      </div>
      <div className={s.actions}><button type="button" className={`${s.btn} ${s.primary}`} disabled={!file} onClick={importFile} data-testid="import-file">{t('backup.importBtn')}</button></div>
    </div>
  );
}

const birdsCount = (n: number) => t('stats.countLine', { n: fmtNum(n), d: '' }).split('·')[0].trim();

type ReplacePreview = { removed: number; removedBirds: number; removedOthers: number; returning: Array<{ id: string; name: string; ring: string }> };
/** Does a change on this device reach the person's other devices? Only with a configured build and a session. */
const travels = () => (db.syncConfig() as { configured: boolean }).configured && (db.authState() as { signedIn: boolean }).signedIn;
const RETURNING_SHOWN = 5;
/** RF-19: every destructive question says so when this device holds changes that have not been sent. */
const unsentNote = async () => ((await db.unsentChanges()) as number) > 0 ? t('confirm.unsent') : '';

/** Restore an automatic snapshot — the spec's list, one «استرجاع» per snapshot; asks first; photos survive. */
export function RestoreDetail({ snapshots }: { snapshots: Backup[] }) {
  async function restore(b: Backup) {
    // RF-15: a restore is a replace, and it travels — the question names what it brings back and says so
    const p = db.replacePreview(b.payload) as ReplacePreview;
    // a pre-import snapshot's id is `pre-import-<ISO>`; the question shows the moment, not the key
    const body = [t('restore.confirm.lead', { d: fmtDate(b.id.replace(/^pre-import-/, ''), { withTime: true }) }),
      p.removed ? t('restore.confirm.removes', { n: fmtNum(p.removed) }) : '',
      travels() ? t('restore.confirm.devices') : '', await unsentNote(),
      p.returning.length ? t('restore.confirm.returns', { n: fmtNum(p.returning.length) }) : t('restore.confirm.returnsNone')].filter(Boolean).join(' ');
    const items = p.returning.slice(0, RETURNING_SHOWN).map((x) => ({ field: x.name || x.ring || '—', text: x.name ? x.ring : '' }));
    if (p.returning.length > RETURNING_SHOWN) items.push({ field: t('restore.confirm.more', { n: fmtNum(p.returning.length - RETURNING_SHOWN) }), text: '' });
    const ok = await confirmDialog({ title: t('backup.restoreAuto'), body, list: items.length ? { kind: 'warns', items } : undefined, cancelLabel: t('act.cancel'), confirmLabel: t('act.replace'), confirmKind: 'danger' });
    if (!ok) return;
    await destructive(async () => {
      const counts = await db.importAll(b.payload, 'replace') as { birds: number; pairs: number; raceResults: number };
      toast(t('backup.imported', { birds: fmtNum(counts.birds), pairs: fmtNum(counts.pairs), races: fmtNum(counts.raceResults) }), { timeout: 7000, kind: 'info' });
    }, failedAction(t('backup.restoreAuto')));
  }
  // RULED 2026-11-16: the list arrives newest first, and «آخر نسخة تلقائية» is the newest INTERVAL snapshot — a
  // snapshot taken before a replace or a restore is in the list at its moment, but it is not «تلقائية» in that line
  const lastAuto = snapshots.find((b) => !db.isPreImportBackup(b));
  return (
    <div>
      {/* RULING 3 (tools-v2): «آخر نسخة تلقائية» is a fact about the fancier's own data — kept */}
      <p className={s.detailText} data-testid="last-snapshot">{t('tools.restore.last', { d: lastAuto ? fmtDate(lastAuto.id, { withTime: true }) : t('backup.noSnapshots') })}</p>
      {snapshots.length > 0 && (
        <div className={s.list} data-testid="snap-list">
          {snapshots.map((b) => (
            <div key={b.id} className={`${s.item} ${s.snap}`} data-testid="snap-row" data-id={b.id}>
              <span><strong>{fmtDate(db.backupMoment(b) as string, { withTime: true })}</strong><div className={s.meta}>{birdsCount((b.payload?.birds || []).filter((x) => !db.isPlaceholder(x)).length)}</div></span>
              <button type="button" className={s.btn} onClick={() => restore(b)} data-testid="snap-restore">{t('tools.restore.btn')}</button>
            </div>
          ))}
        </div>
      )}
      <p className={s.detailNote}>{t('backup.auto', { h: fmtNum(db.AUTO_BACKUP_HOURS as number), n: fmtNum(db.BACKUP_KEEP as number), m: fmtNum(db.PRE_IMPORT_KEEP as number) })}</p>
    </div>
  );
}

/** The teaching data. Merges, never destroys (js/views/birds.js loadExample). Deviation 4: tools-v1's row, which the spec dropped. */
export function ExamplesDetail() {
  const [busy, setBusy] = useState(false);
  async function load(file: string) {
    setBusy(true);
    try {
      // asset(), not a relative URL: this screen is at `<base>/tools/` since trailingSlash was ruled (app/birds/view.tsx)
      await destructive(async () => {
        const counts = await db.loadExampleDataset(await (await fetch(asset(file))).json()) as { birds: number };   // RF-16
        toast(t('bird.exampleLoaded', { n: counts.birds }), { timeout: 7000, kind: 'info' });
      }, failedAction(t('example.title')));
    } finally { setBusy(false); }
  }
  return (
    <div className={s.ds}>
      <button type="button" disabled={busy} onClick={() => load('./sample-data.json')} data-testid="load-sample"><span className={s.t}>{t('example.small')}</span><span className={s.n}>{t('example.smallN', { n: fmtNum(20) })}</span></button>
      <button type="button" disabled={busy} onClick={() => load('./example-loft-large.json')} data-testid="load-large"><span className={s.t}>{t('example.large')}</span><span className={s.n}>{t('example.largeN', { n: fmtNum(38), g: fmtNum(5) })}</span></button>
    </div>
  );
}

/**
 * THE INVARIANT (RULED 2026-10-30, RF-18): no path through a destructive action in الأدوات returns having
 * changed nothing without telling the user. Every such handler runs its work through this; a caught failure
 * produces a toast naming the reason — never a silent return. The reason is the first validation issue in the
 * fancier's language when the failure is a ValidationError, the message otherwise.
 */
export async function destructive(work: () => Promise<void>, failed: (reason: string) => string): Promise<boolean> {
  try { await work(); return true; }
  catch (e) {
    const err = e as { name?: string; message?: string; errors?: Array<{ key: string; params?: Record<string, unknown> }>; warnings?: Array<{ key: string; params?: Record<string, unknown> }> };
    const issue = err?.name === 'ValidationError' ? ((err.errors || [])[0] || (err.warnings || [])[0]) : null;
    const reason = issue ? t('tools.failed.validation', { what: t(issue.key, issue.params as Record<string, string | number> | undefined) })
                         : t('tools.failed.unknown', { what: err?.message || String(e) });
    toast(failed(reason), { kind: 'error', timeout: 12000 });
    return false;
  }
}

/**
 * THE ELEVEN (RULED 2026-11-17): every mutating handler in الأدوات that could fail without a word now runs through
 * destructive() and names itself by the label of its own control. «لم يكتمل», not «لم يتغيّر شيء»: several of them
 * are more than one write, and a failure after the first has changed something.
 */
export const failedAction = (what: string) => (reason: string) => t('tools.failed.action', { what, reason });

/**
 * REMOVING THE EXAMPLE DATA (RULED 2026-10-14). Loaded in the row above, removed here — the symmetry is the point.
 * Rendered only while a dataset loft is present (identified by the datasets' own ids, derived in src/example-data.js),
 * so a device that never loaded one never sees it. Goes through deleteBird()/remove()/Lofts.remove(), so the removal
 * tombstones and syncs; confirms with the real counts; keeps example ancestors of the fancier's own birds as pedigree
 * references and says so. NOT general loft management (README). A deviation from the frozen tools-v2 spec, recorded.
 */
type Presence = { ids: string[]; lofts: Array<{ id: string; name: string; birds: number; pairs: number; races: number; health: number }>;
  birds: number; pairs: number; races: number; health: number; media: number; kept: number; own: number; ownBirds: number; current: boolean;
  elsewhere: number; outside: number; because: Array<{ id: string; name: string; ring: string }> };
export function ExampleRemoveRow() {
  const [p, setP] = useState<Presence | null>(null);
  const [busy, setBusy] = useState(false);
  // recomputed on EVERY layer change (loading, removing, a pulled tombstone): useZajilStore's selector hands back the
  // same mutated state object, so it cannot be an effect dependency — the layer's own change feed is subscribed instead
  useEffect(() => {
    let live = true; let latest = 0;
    // TF-12 (RULED 2026-11-15): a recompute that finishes after a newer one STARTED is dropped — it was put back over
    // the newer answer (measured: 38 → 37 → 38 for two seconds after one deletion)
    const recompute = () => { const mine = ++latest; (db.examplePresence() as Promise<Presence | null>).then((x) => { if (live && mine === latest) setP(x); }); };
    recompute();
    const off = db.onChange(recompute) as (() => void) | undefined;
    return () => { live = false; if (typeof off === 'function') off(); };
  }, []);
  if (!p) return null;
  const lofts = p.lofts.map((l) => `«${l.name || t('loft.unnamed')}»`).join('، ');
  async function remove() {
    if (busy || !p) return;
    // RF-22 (RULED 2026-11-01): the question NAMES the birds that cause a keep — the fancier's birds with an example
    // parent — up to BECAUSE_SHOWN, then «و{n} غيرها». With no dataset loft left on the device it names no loft.
    const shown = db.BECAUSE_SHOWN as number;
    const names = p.because.slice(0, shown).map((x) => x.name || x.ring || '—').join('، ')
      + (p.because.length > shown ? ' ' + t('restore.confirm.more', { n: fmtNum(p.because.length - shown) }) : '');
    const counts = { birds: fmtNum(p.birds), pairs: fmtNum(p.pairs), races: fmtNum(p.races), health: fmtNum(p.health) };
    // RULED 2026-11-17: with a record filed outside the named lofts the question names none — but a dataset loft that is present IS removed, and it says so
    const body = (p.lofts.length && !p.outside ? t('example.remove.body', { ...counts, lofts }) : p.lofts.length ? t('example.remove.bodyOutside', counts) : t('example.remove.bodyNoLoft', counts))
      + (p.kept ? ' ' + t('example.remove.kept', { k: fmtNum(p.kept) }) + (p.because.length ? ' ' + t('example.remove.because', { names }) : '') : '')
      + (p.own ? ' ' + t('example.remove.own', { m: fmtNum(p.own) }) : '')
      + ((await db.unsentChanges()) as number > 0 ? ' ' + t('confirm.unsent') : '');
    const ok = await confirmDialog({ title: t('example.remove.title'), body, cancelLabel: t('act.cancel'), confirmLabel: t('example.remove.go'), confirmKind: 'danger' });
    if (!ok) return;
    setBusy(true);
    try {
      await destructive(async () => {
        const r = await db.removeExampleData() as { birds: number; pairs: number; races: number; health: number; kept: number } | null;
        if (r) toast(t('example.remove.done', { birds: fmtNum(r.birds), pairs: fmtNum(r.pairs), races: fmtNum(r.races), health: fmtNum(r.health) }) + (r.kept ? t('example.remove.doneKept', { k: fmtNum(r.kept) }) : ''), { timeout: 9000, kind: 'success' });
      }, (reason) => t('example.remove.failed', { reason }));
    } finally { setBusy(false); }
  }
  return (
    <Row id="example-remove" icon="teaching" label={t('example.remove.label')} help={t('example.remove.help', { n: fmtNum(p.birds + p.kept) })} value={fmtNum(p.birds + p.kept)} valueKind="gold">
      <div className={s.ds} data-testid="example-remove-detail">
        {p.lofts.length > 0 && <p className={s.detailNote} data-testid="example-remove-lofts">{t('example.remove.lofts', { lofts })}</p>}
        <button type="button" disabled={busy} onClick={remove} data-testid="example-remove" aria-busy={busy}>
          <span className={s.t}>{busy ? t('example.remove.busy') : t('example.remove.button')}</span>
          <span className={s.n}>{[...p.lofts.map((l) => l.birds), ...(p.elsewhere ? [p.elsewhere] : [])].map((n) => fmtNum(n)).join(' + ')}</span>
        </button>
      </div>
    </Row>
  );
}

// ── checks ───────────────────────────────────────────────────────────────────────────
/** The integrity check as a user-facing row (the spec's فحص سلامة البيانات). Its «آخر فحص» survives a reload: time and count are settings, like lastExport. */
export function IntegrityDetail({ settings }: { settings: Record<string, unknown> }) {
  const st = useZajilStore((x) => x);
  const [problems, setProblems] = useState<Array<{ key: string; params: Record<string, unknown> }> | null>(null);
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try {
      await destructive(async () => {
        const { checkIntegrity } = await import('@/src/engine/integrity.js');
        // the checker reads only these maps (engine/integrity.js)
        const found = checkIntegrity({ birds: st.birds, pairs: st.pairs, raceResults: st.raceResults, healthEvents: st.healthEvents, lofts: st.lofts } as never) as Array<{ key: string; params: Record<string, unknown> }>;
        setProblems(found);
        await saveSetting('integrityCheckedAt', new Date().toISOString());
        await saveSetting('integrityProblems', found.length);
      }, failedAction(t('integrity.title')));
    } finally { setBusy(false); }
  }
  const at = settings.integrityCheckedAt as string | undefined;
  const n = problems ? problems.length : typeof settings.integrityProblems === 'number' ? (settings.integrityProblems as number) : null;
  return (
    <div data-testid="integrity-detail">
      {n === null
        ? <p className={s.detailText}>{t('tools.integrity.never')}</p>
        : <StatusLine icon={n ? 'alert' : 'check'} gold={n > 0} testid="integrity-status" title={n ? t('integrity.found', { n: fmtNum(n) }) : t('integrity.clean')} text={at ? t('tools.lastCheck', { d: fmtDate(at, { withTime: true }) }) : undefined} />}
      {problems && problems.length > 0 && <ul className={s.list} data-testid="integrity-out">{problems.map((p, i) => <li key={i} className={`${s.item} ${s.t}`}>{t(p.key, p.params)}</li>)}</ul>}
      <div className={s.actions}><button type="button" className={s.btn} disabled={busy} onClick={run} data-testid="integrity-run">{t('tools.integrity.run')}</button></div>
    </div>
  );
}

// ── advanced ─────────────────────────────────────────────────────────────────────────
/** The optional scanner. Off by default; the app is fully offline without it. Saves on blur (tools-v1) and on «حفظ» (the spec). */
export function ScannerDetail({ settings }: { settings: Record<string, unknown> }) {
  const [url, setUrl] = useState((settings.scanServerUrl as string) || '');
  const save = () => destructive(async () => { await saveSetting('scanServerUrl', url.trim()); }, failedAction(t('scan.title')));
  return (
    <div>
      <div className={s.field}>
        <label htmlFor="vis">{t('scan.serverUrl')}</label>
        <input id="vis" className={s.data} type="url" dir="ltr" placeholder="https://vision.example.org" value={url} onChange={(e) => setUrl(e.target.value)} onBlur={save} data-testid="scan-url" />
      </div>
      {!url.trim() && <StatusLine icon="off" testid="scan-off" title={t('tools.scan.offShort')} text={t('scan.notConfigured')} />}
      <div className={s.actions}><button type="button" className={`${s.btn} ${s.primary}`} onClick={async () => { if (await save()) toast(t('toast.saved'), { kind: 'success' }); }} data-testid="scan-save">{t('act.save')}</button></div>
    </div>
  );
}

/** The dev panel's body. It runs the COPIED engine suite through its own harness (tools-v1, unchanged). */
export function DevDetail() {
  const [out, setOut] = useState<string>('');
  const [failed, setFailed] = useState(false);
  const st = useZajilStore((x) => x);
  async function runTests() {
    setOut(t('common.loading')); setFailed(false);
    try {
      // the suite registers its tests on import; the harness runs them. Dynamic, so it is a chunk loaded only when a
      // developer opens this panel — as vanilla does.
      await import('@/tests/engine.test.js');
      const { runAll } = await import('@/tests/harness.js');
      const { passed, failed: f, results } = await runAll() as { passed: number; failed: number; results: Array<{ ok: boolean; name: string; error?: string }> };
      setOut(results.map((r) => `${r.ok ? '✔' : '✘'} ${r.name}${r.ok ? '' : '\n    ' + r.error}`).join('\n') + `\n${'─'.repeat(46)}\n${f ? 'FAIL' : 'PASS'}  ${t('dev.passed', { p: passed, f })}`);
      setFailed(f > 0);
    } catch (err) { setOut('✘ ' + (err as Error).message); setFailed(true); }
  }
  async function roundtrip() {
    setOut(t('common.loading')); setFailed(false);
    try {
      const before = await db.exportAll() as unknown as Record<string, unknown[]>;
      const parsed = JSON.parse(JSON.stringify(before));
      const norm = (p: Record<string, unknown[]>) => JSON.stringify({ birds: p.birds, pairs: p.pairs, raceResults: p.raceResults, healthEvents: p.healthEvents, lofts: p.lofts,
        media: ((p.media || []) as Array<Record<string, unknown>>).map((m) => ({ id: m.id, birdId: m.birdId, dataURL: m.dataURL })) });
      if (norm(before) !== norm(parsed)) throw new Error('serialisation not stable');
      setOut(`✔ ${t('dev.roundtripOK')}\n    birds=${before.birds.length} pairs=${before.pairs.length} races=${before.raceResults.length} media=${(before.media || []).length}`);
    } catch (err) { setOut('✘ ' + t('dev.roundtripFail', { msg: (err as Error).message })); setFailed(true); }
  }
  async function integrity() {
    const { checkIntegrity } = await import('@/src/engine/integrity.js');
    const problems = checkIntegrity({ birds: st.birds, pairs: st.pairs, raceResults: st.raceResults, healthEvents: st.healthEvents, lofts: st.lofts } as never) as Array<{ key: string; params: Record<string, unknown> }>;
    setOut(problems.length ? `${t('integrity.found', { n: fmtNum(problems.length) })}\n` + problems.map((p) => '  ✘ ' + t(p.key, p.params)).join('\n') : '✔ ' + t('integrity.clean'));
    setFailed(problems.length > 0);
  }
  return (
    <div>
      <div className={s.actions}>
        <button type="button" className={s.btn} onClick={runTests} data-testid="dev-run">{t('dev.run')}</button>
        <button type="button" className={s.btn} onClick={roundtrip} data-testid="dev-roundtrip">{t('dev.roundtrip')}</button>
        <button type="button" className={s.btn} onClick={integrity} data-testid="dev-integrity">{t('integrity.title')}</button>
      </div>
      {out && <pre className={`${s.devOut} ${failed ? s.fail : ''}`} dir="ltr" data-testid="dev-out">{out}</pre>}
    </div>
  );
}
