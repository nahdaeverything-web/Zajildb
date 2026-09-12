'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { useZajilStore, selectBirds } from '@/src/db/react';
import { t, fmtDate, fmtNum } from '@/src/i18n.ext.js';
import { findDuplicateRings } from '@/src/engine/rings.js';
import { todayISO } from '@/src/dates.js';
import { SyncRow, Loading, toast, confirmDialog, downloadJSON, primaryRing, saveSetting, initDB } from '@/src/components';
import { useAppVersion } from '@/src/components/version';
import s from './tools.module.css';

// Tools & settings — design/approved/tools-v1.html, behaviour from js/views/tools.js.
// Nine cards in the spec's three groups, with its sticky index. Two rulings from
// the Phase 4 order are built in:
//   RULING 1 — the sync card's signed-out state is the explanation line plus a
//     «تسجيل الدخول» button that navigates to /sign-in. The inline email/password
//     form the spec draws inside this card is SUPERSEDED by that screen; the
//     not-configured state is unchanged, and carries no button (there is nothing
//     to sign into on this device).
//   RULING 2 — the loft card gains breeder name, phone, website and a logo, saved
//     through Lofts.save, so the certificate's branding block has real fields to
//     read. The logo is device-local media like a photo: its bytes go to the media
//     store and never to the op log, and only its id lives on the loft record.
// Vanilla wins on wiring: every setting through setSetting, exportAll / importAll /
// listBackups, findDuplicateRings, deleteBird, and the dev panel runs the COPIED
// engine suite through its own harness.
type Loft = { id: string; name?: string; location?: string; breederName?: string; phone?: string; website?: string; logoMediaId?: string | null };
type Bird = { id: string; name?: string; rings?: Array<{ raw?: string }>; sireId?: string | null; damId?: string | null };
type Backup = { id: string; payload?: { birds?: unknown[] } };
const Lofts = db.Lofts as { save: (l: Loft) => Promise<Loft> };
const GROUPS = [
  { id: 'g-settings', title: 'tools.group.settings', sub: 'tools.group.settingsSub', n: 3 },
  { id: 'g-data', title: 'tools.group.data', sub: 'tools.group.dataSub', n: 3 },
  { id: 'g-adv', title: 'tools.group.advanced', sub: 'tools.group.advancedSub', n: 3 },
];

export default function ToolsView() {
  const [booted, setBooted] = useState(false);
  const [group, setGroup] = useState('g-settings');
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const st = useZajilStore((x) => x);
  const birds = useZajilStore(selectBirds) as Bird[];
  const version = useAppVersion();
  if (!booted) return <section className={s.screen}><Loading /></section>;

  const settings = st.settings as Record<string, unknown>;
  const loft = db.currentLoft() as Loft | null;
  return (
    <section className={s.screen}>
      <header className={s.lofthead}><div className={s.in}>
        <div className={s.season} data-testid="crumb">{loft?.name || t('loft.unnamed')} · {t('about.version', { v: version || t('about.unknown') })}</div>
        <h1>{t('tools.title')}</h1>
        <nav className={s.index} aria-label={t('tools.index')} data-testid="index">
          {GROUPS.map((g) => (
            <a key={g.id} href={`#${g.id}`} className={group === g.id ? s.on : ''} onClick={() => setGroup(g.id)} data-testid="index-link" data-group={g.id}>
              {t(g.title)}<span className={s.c}>{fmtNum(g.n)}</span>
            </a>
          ))}
        </nav>
      </div></header>
      <SyncRow />
      <main className={s.panel}>
        {GROUPS.map((g) => (
          <section key={g.id} className={s.group} id={g.id} data-testid="group">
            <div className={s.gh}><h2>{t(g.title)}</h2><span className={s.c}>{t(g.sub)}</span></div>
            <div className={s.cards}>
              {g.id === 'g-settings' && <><SettingsCard settings={settings} /><SyncCard settings={settings} /><LoftCard loft={loft} /></>}
              {g.id === 'g-data' && <><DuplicatesCard birds={birds} /><ExamplesCard /><BackupCard settings={settings} /></>}
              {g.id === 'g-adv' && <><ScannerCard settings={settings} /><AboutCard version={version} /><DevCard /></>}
            </div>
          </section>
        ))}
      </main>
    </section>
  );
}

// Both of these are declared HERE, not inside the card that uses them: a component
// defined in a render body is a new type on every render, so React remounts its DOM
// and a text field loses the caret after one character.
function Seg({ label, k, options, current, hint, set }: { label: string; k: string; options: Array<[string, React.ReactNode]>; current: string; hint?: string; set: (k: string, v: unknown) => void }) {
  return (
    <div className={s.set} data-testid={`set-${k}`}>
      <span className={s.k}>{label}</span>
      <div className={s.seg} role="group" aria-label={label}>
        {options.map(([v, node]) => <button key={v} type="button" aria-pressed={current === v} onClick={() => set(k, v)} data-testid="seg-btn" data-value={v}>{node}</button>)}
      </div>
      {hint && <div className={s.hint}>{hint}</div>}
    </div>
  );
}

function F({ id, label, value, onChange, dir }: { id: string; label: string; value: string; onChange: (e: React.ChangeEvent<HTMLInputElement>) => void; dir?: 'ltr' }) {
  return <div className={s.field}><label htmlFor={id}>{label}</label><input id={id} type="text" dir={dir} className={dir ? s.data : ''} value={value} onChange={onChange} placeholder={id === 'ln' ? t('loft.unnamed') : undefined} data-testid={id} /></div>;
}

/** 1 — display settings. Every control writes through setSetting, as vanilla does. */
function SettingsCard({ settings }: { settings: Record<string, unknown> }) {
  const set = (k: string, v: unknown) => { saveSetting(k, v); };
  const depth = +(settings.coiDepth as number || 10);
  return (
    <article className={s.card} data-testid="card-settings">
      <h3>{t('tools.settings')}</h3>
      <Seg set={set} label={t('set.language')} k="lang" current={(settings.lang as string) || 'ar'} options={[['ar', t('lang.ar')], ['en', t('lang.en')]]} />
      <Seg set={set} label={t('set.numerals')} k="numerals" current={(settings.numerals as string) || 'western'} hint={t('set.numeralsHint')}
        options={[['western', <>{t('set.numerals.westernShort')}<span className={s.num}>0123456789</span></>], ['eastern', <>{t('set.numerals.easternShort')}<span className={s.num}>٠١٢٣٤٥٦٧٨٩</span></>]]} />
      <Seg set={set} label={t('set.dates')} k="dates" current={(settings.dates as string) || 'both'}
        options={[['gregorian', t('set.dates.gregorian')], ['hijri', t('set.dates.hijri')], ['both', t('set.dates.both')]]} />
      <div className={s.set} data-testid="set-coiDepth">
        <label htmlFor="coi">{t('set.coiDepth')}</label>
        <div className={s.stepper}>
          <span className={s.rng}>3 – 15</span>
          <button type="button" aria-label={t('act.less')} onClick={() => set('coiDepth', Math.max(3, depth - 1))} data-testid="coi-less">−</button>
          <input id="coi" type="number" min={3} max={15} value={depth} onChange={(e) => { const v = Math.min(15, Math.max(3, +e.target.value || 10)); set('coiDepth', v); }} data-testid="coi-input" />
          <button type="button" aria-label={t('act.increase')} onClick={() => set('coiDepth', Math.min(15, depth + 1))} data-testid="coi-more">+</button>
        </div>
      </div>
      <div className={s.set}>
        <label className={s.check}>
          <input type="checkbox" checked={!!settings.highContrast} onChange={(e) => set('highContrast', e.target.checked)} data-testid="hc-input" />
          <span className={s.box} aria-hidden="true">{settings.highContrast ? '✓' : ''}</span>
          <span>{t('set.highContrast')}</span>
        </label>
      </div>
    </article>
  );
}

/** 2 — sync. RULING 1: signed out sends you to /sign-in; the inline form is superseded. */
function SyncCard({ settings }: { settings: Record<string, unknown> }) {
  const [busy, setBusy] = useState(false);
  const cfg = db.syncConfig() as { configured: boolean };
  const auth = db.authState() as { signedIn: boolean; email: string | null };
  const status = db.syncStatus() as { pending: number; state: string; error?: { key: string; status?: number | null; at?: string } | null };
  const anomalies = (db.listSyncAnomalies ? db.listSyncAnomalies() : []) as Array<{ store?: string; recordId?: string; reason?: string; at?: string }>;
  const enabled = settings.syncEnabled !== false;
  return (
    <article className={s.card} id="sync" data-testid="card-sync">
      <h3>{t('sync.card')}</h3>
      {!cfg.configured ? (
        <div className={`${s.msg} ${s.calm}`} data-testid="sync-unconfigured">{t('sync.notSetUp')}</div>
      ) : !auth.signedIn ? (
        <div data-testid="sync-signed-out">
          <div className={s.sub}>{t('sync.signInToSync')}</div>
          {/* RULING 1: a button that NAVIGATES — the spec's inline form here is superseded by /sign-in */}
          <div className={s.btns}><Link href="/sign-in" className={`${s.btn} ${s.primary}`} data-testid="go-signin">{t('sync.signIn')}</Link></div>
        </div>
      ) : (
        <div data-testid="sync-signed-in">
          <div className={s.kv}>
            <div><span className={s.k}>{t('sync.account')}</span><span className={`${s.v} ${s.num}`} data-testid="sync-account">{auth.email}</span></div>
            <div><span className={s.k}>{t('sync.lastSync')}</span><span className={s.v}>{settings.lastSyncAt ? fmtDate(settings.lastSyncAt as string, { withTime: true }) : t('sync.never')}</span></div>
            <div><span className={s.k}>{t('sync.pendingN')}</span><span className={s.v}><span className={`${s.big} ${status.pending ? '' : s.zero}`} data-testid="sync-pending">{fmtNum(status.pending)}</span></span></div>
          </div>
          {status.error ? (
            <div className={`${s.msg} ${s.amber}`} data-testid="sync-error">
              {t('sync.lastError')}: {t(status.error.key)}
              {status.error.status ? ` (${status.error.status})` : ''}
              {status.error.at ? ' — ' + fmtDate(status.error.at, { withTime: true }) : ''}
            </div>
          ) : null}
          {anomalies.length > 0 && (
            <div className={`${s.msg} ${s.amber}`} data-testid="sync-anomalies">
              <h4>{t('sync.anomalies', { n: fmtNum(anomalies.length) })}</h4>
              <ul>{anomalies.slice(0, 10).map((a, i) => <li key={i}><span>{a.reason || a.store}</span> <span className={s.num}>{a.store} · {a.at ? a.at.slice(0, 10) : ''}</span></li>)}</ul>
            </div>
          )}
          <div className={`${s.btns} ${s.desk3}`}>
            <button type="button" className={`${s.btn} ${s.primary}`} disabled={busy} onClick={async () => { setBusy(true); try { await db.syncNow(); toast(t('toast.saved'), { kind: 'success' }); } finally { setBusy(false); } }} data-testid="sync-now">{t('sync.now')}</button>
            <button type="button" className={`${s.btn} ${s.ghost}`} onClick={async () => { await db.setSyncEnabled(!enabled); await db.refreshSyncStatus(); }} data-testid="sync-toggle">{enabled ? t('sync.toggleOff') : t('sync.toggleOn')}</button>
            <button type="button" className={`${s.btn} ${s.ghost}`} onClick={async () => {
              const ok = await confirmDialog({ title: t('confirm.signOut.title'), body: t('sync.signOutKeepsData'), cancelLabel: t('act.cancel'), confirmLabel: t('sync.signOut'), confirmKind: 'ink' });
              // signOut() emits nothing (db/sync.js:199), so the card is told the way
              // vanilla's is — js/views/tools.js:221 calls refresh() right after it.
              if (ok) { await db.signOut(); await db.refreshSyncStatus(); }
            }} data-testid="sign-out">{t('sync.signOut')}</button>
          </div>
          <div className={s.hint}>{t('sync.signOutKeepsData')}</div>
        </div>
      )}
    </article>
  );
}

/** 3 — the loft. RULING 2 adds the branding fields the certificate reads. */
function LoftCard({ loft }: { loft: Loft | null }) {
  const [f, setF] = useState({ name: loft?.name || '', location: loft?.location || '', breederName: loft?.breederName || '', phone: loft?.phone || '', website: loft?.website || '' });
  const [logo, setLogo] = useState<string | null>(loft?.logoMediaId || null);
  const fileIn = useRef<HTMLInputElement>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  async function save() {
    if (!loft) return;
    await Lofts.save({ ...loft, name: f.name.trim(), location: f.location.trim(), breederName: f.breederName.trim(), phone: f.phone.trim(), website: f.website.trim(), logoMediaId: logo });
    toast(t('toast.saved'), { kind: 'success' });
  }
  async function pickLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file || !loft) return;
    // device-local, like a photo: the bytes go to the media store and never to the op log
    const m = await db.addMedia(loft.id, 'document', 'logo', file.name, file) as { id: string };
    setLogo(m.id); e.target.value = '';
  }
  return (
    <article className={s.card} data-testid="card-loft">
      <h3>{t('set.loft')}</h3>
      <F id="ln" label={t('set.loftName')} value={f.name} onChange={set('name')} />
      <F id="lc" label={t('set.loftLocation')} value={f.location} onChange={set('location')} />
      {/* RULING 2: the certificate's branding block reads these */}
      <F id="lb" label={t('set.breederName')} value={f.breederName} onChange={set('breederName')} />
      <F id="lp" label={t('set.phone')} value={f.phone} onChange={set('phone')} dir="ltr" />
      <F id="lw" label={t('set.website')} value={f.website} onChange={set('website')} dir="ltr" />
      <div className={s.field}>
        <label>{t('set.logo')}</label>
        <div className={s.file}>
          <button type="button" className={s.pick} onClick={() => fileIn.current?.click()} data-testid="logo-pick">{t('backup.chooseFile')}</button>
          <span className={`${s.fn} ${logo ? s.has : ''}`} data-testid="logo-state">{logo ? t('set.logoSet') : t('set.logoNone')}</span>
          <input ref={fileIn} type="file" accept="image/*" onChange={pickLogo} data-testid="logo-input" />
        </div>
        <div className={s.hint}>{t('set.logoHint')}</div>
      </div>
      <div className={s.btns}><button type="button" className={`${s.btn} ${s.ink}`} onClick={save} data-testid="loft-save">{t('act.save')}</button></div>
    </article>
  );
}

/** 4 — the duplicate-ring finder (picker_duplicates #8–10). */
function DuplicatesCard({ birds }: { birds: Bird[] }) {
  const st = useZajilStore((x) => x);
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
    if (ok) await db.deleteBird(b.id);
  }
  return (
    <article className={s.card} data-testid="card-duplicates">
      <h3>{t('dup.title')}</h3>
      {groups.length === 0 ? (
        <div className={`${s.msg} ${s.ok}`} data-testid="dup-clean">{t('dup.noneShort')}</div>
      ) : (
        <div data-testid="dup-found">
          <div className={s.sub}>{t('dup.foundShort', { n: fmtNum(groups.length) })}</div>
          {groups.map((g) => (
            <div key={g.key} className={s.dup} data-testid="dup-group">
              <div className={s.ring}><span className={s.plate}>{primaryRing(g.birds[0])}</span><span className={s.n}>{t('dup.copies', { n: fmtNum(g.birds.length) })}</span></div>
              {g.birds.map((b) => {
                const { n, kinds } = links(b);
                return (
                  <div key={b.id} className={s.copy} data-testid="dup-copy">
                    <div>
                      <div className={s.name}><bdi>{b.name || primaryRing(b) || b.id.slice(0, 8)}</bdi></div>
                      <div className={`${s.links} ${n ? '' : s.none}`} data-testid="dup-links">{n ? t('dup.linkedTo', { n: fmtNum(n), kinds }) : t('dup.noLinks')}</div>
                    </div>
                    <button type="button" className={s.del} onClick={() => del(b)} data-testid="dup-delete">{t('act.delete')}</button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

/** 5 — the teaching data. Merges, never destroys (js/views/birds.js loadExample). */
function ExamplesCard() {
  const [busy, setBusy] = useState(false);
  async function load(file: string) {
    setBusy(true);
    try {
      const counts = await db.importAll(await (await fetch(file)).json(), 'merge') as { birds: number };
      toast(t('bird.exampleLoaded', { n: counts.birds }), { timeout: 7000, kind: 'info' });
    } finally { setBusy(false); }
  }
  return (
    <article className={s.card} data-testid="card-examples">
      <h3>{t('example.title')}</h3>
      <div className={s.sub}>{t('example.hint')}</div>
      <div className={s.ds}>
        <button type="button" disabled={busy} onClick={() => load('./sample-data.json')} data-testid="load-sample"><span className={s.nm}>{t('example.small')}</span><span className={s.n}>{t('example.smallN', { n: fmtNum(20) })}</span></button>
        <button type="button" disabled={busy} onClick={() => load('./example-loft-large.json')} data-testid="load-large"><span className={s.nm}>{t('example.large')}</span><span className={s.n}>{t('example.largeN', { n: fmtNum(38), g: fmtNum(5) })}</span></button>
      </div>
    </article>
  );
}

/** 6 — backup, export, import, and restoring an automatic snapshot. */
function BackupCard({ settings }: { settings: Record<string, unknown> }) {
  const [snapshots, setSnapshots] = useState<Backup[]>([]);
  const [snap, setSnap] = useState('');
  const [mode, setMode] = useState<'merge' | 'replace'>('merge');
  const [file, setFile] = useState<File | null>(null);
  const fileIn = useRef<HTMLInputElement>(null);
  useEffect(() => { db.listBackups().then((b: Backup[]) => { setSnapshots(b); if (b[0]) setSnap(b[0].id); }); }, []);
  async function exportAll() {
    const payload = await db.exportAll();
    downloadJSON(payload, `zajil-export-${todayISO()}.json`);
    await saveSetting('lastExport', new Date().toISOString());
    toast(t('toast.exported'), { kind: 'success' });
  }
  async function importFile() {
    if (!file) return;
    if (mode === 'replace') {
      const ok = await confirmDialog({ title: t('confirm.replace.title'), body: t('confirm.replace.body'), cancelLabel: t('act.cancel'), confirmLabel: t('act.replace'), confirmKind: 'danger' });
      if (!ok) return;
    }
    const counts = await db.importAll(JSON.parse(await file.text()), mode) as { birds: number; pairs: number; raceResults: number };
    toast(t('backup.imported', { birds: fmtNum(counts.birds), pairs: fmtNum(counts.pairs), races: fmtNum(counts.raceResults) }), { timeout: 7000, kind: 'info' });
    setFile(null);
  }
  async function restore() {
    const b = snapshots.find((x) => x.id === snap); if (!b) return;
    const ok = await confirmDialog({ title: t('backup.restoreAuto'), body: t('backup.confirmSnapshot', { d: fmtDate(b.id, { withTime: true }) }), cancelLabel: t('act.cancel'), confirmLabel: t('act.replace'), confirmKind: 'danger' });
    if (!ok) return;
    const counts = await db.importAll(b.payload, 'replace') as { birds: number; pairs: number; raceResults: number };
    toast(t('backup.imported', { birds: fmtNum(counts.birds), pairs: fmtNum(counts.pairs), races: fmtNum(counts.raceResults) }), { timeout: 7000, kind: 'info' });
  }
  return (
    <article className={`${s.card} ${s.span}`} data-testid="card-backup">
      <h3>{t('backup.title')}</h3>
      <div className={s.two}>
        <div className={s.col}>
          <div className={s.stat}><span className={s.k}>{t('backup.lastExportLabel')}:</span> <span className={s.v} data-testid="last-export">{settings.lastExport ? fmtDate(settings.lastExport as string) : t('backup.never')}</span></div>
          <div className={s.hint}>{t('backup.auto', { h: fmtNum(12), n: fmtNum(7) })}</div>
          <div className={s.btns}><button type="button" className={`${s.btn} ${s.primary}`} onClick={exportAll} data-testid="export-all">{t('backup.exportAll')}</button></div>
          <div className={s.subsec}>
            <h4>{t('backup.restoreAuto')}</h4>
            <div className={s.inline}>
              <div className={s.field}>
                <label htmlFor="snap">{t('backup.snapshot')}</label>
                <select id="snap" className={s.num} value={snap} onChange={(e) => setSnap(e.target.value)} disabled={snapshots.length === 0} data-testid="snap-select">
                  {snapshots.length === 0 ? <option value="">{t('backup.noSnapshots')}</option>
                    : snapshots.map((b) => <option key={b.id} value={b.id}>{fmtDate(b.id, { withTime: true })} · {t('stats.countLine', { n: fmtNum((b.payload?.birds || []).length), d: '' }).split('·')[0].trim()}</option>)}
                </select>
              </div>
              <button type="button" className={`${s.btn} ${s.ink}`} disabled={snapshots.length === 0} onClick={restore} data-testid="snap-restore">{t('backup.importBtn')}</button>
            </div>
          </div>
        </div>
        <div className={s.col}>
          <div className={s.subsec}>
            <h4>{t('backup.import')}</h4>
            <div className={s.field}>
              <label htmlFor="mode">{t('backup.importModeLabel')}</label>
              <select id="mode" value={mode} onChange={(e) => setMode(e.target.value as 'merge' | 'replace')} data-testid="import-mode">
                <option value="merge">{t('backup.importMode.merge')}</option>
                <option value="replace">{t('backup.importMode.replace')}</option>
              </select>
            </div>
            <div className={s.field}>
              <label>{t('backup.file')}</label>
              <div className={s.file}>
                <button type="button" className={s.pick} onClick={() => fileIn.current?.click()} data-testid="file-pick">{t('backup.chooseFile')}</button>
                <span className={`${s.fn} ${file ? s.has : ''}`} data-testid="file-name">{file ? file.name : t('backup.noFile')}</span>
                <input ref={fileIn} type="file" accept=".json,application/json" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="file-input" />
              </div>
            </div>
            <div className={s.btns}><button type="button" className={`${s.btn} ${s.ghost}`} disabled={!file} onClick={importFile} data-testid="import-file">{t('backup.importBtn')}</button></div>
          </div>
        </div>
      </div>
    </article>
  );
}

/** 7 — the optional scanner. Off by default; the app is fully offline without it. */
function ScannerCard({ settings }: { settings: Record<string, unknown> }) {
  const [url, setUrl] = useState((settings.scanServerUrl as string) || '');
  return (
    <article className={s.card} data-testid="card-scanner">
      <h3>{t('scan.title')}</h3>
      <div className={s.sub}>{t('scan.hint')}</div>
      <div className={s.field}>
        <label htmlFor="vis">{t('scan.serverUrl')}</label>
        <input id="vis" className={s.data} type="url" dir="ltr" placeholder="https://vision.example.org" value={url}
          onChange={(e) => setUrl(e.target.value)} onBlur={() => saveSetting('scanServerUrl', url.trim())} data-testid="scan-url" />
      </div>
      {!url.trim() && <div className={`${s.msg} ${s.calm}`} data-testid="scan-off">{t('scan.notConfigured')}</div>}
    </article>
  );
}

/** 8 — about: the version the SERVICE WORKER reports, never a constant. */
function AboutCard({ version }: { version: string | null }) {
  return (
    <article className={s.card} data-testid="card-about">
      <h3>{t('about.title')}</h3>
      <div className={s.ver}><span className={s.k}>{t('about.versionLabel')}</span><span className={`${s.v} ${s.num}`} data-testid="about-version">{version || t('about.unknown')}</span></div>
      <div className={s.hint}>{t('about.hint')}</div>
    </article>
  );
}

/** 9 — the dev panel, collapsed. It runs the COPIED engine suite through its own harness. */
function DevCard() {
  const [out, setOut] = useState<string>('');
  const [failed, setFailed] = useState(false);
  const st = useZajilStore((x) => x);
  async function runTests() {
    setOut(t('common.loading')); setFailed(false);
    try {
      // the suite registers its tests on import; the harness runs them. Dynamic, so it is
      // a chunk loaded only when a developer opens this panel — as vanilla does.
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
    // the checker reads only these maps (engine/integrity.js)
    const problems = checkIntegrity({ birds: st.birds, pairs: st.pairs, raceResults: st.raceResults, healthEvents: st.healthEvents, lofts: st.lofts } as never) as Array<{ key: string; params: Record<string, unknown> }>;
    setOut(problems.length ? `${t('integrity.found', { n: fmtNum(problems.length) })}\n` + problems.map((p) => '  ✘ ' + t(p.key, p.params)).join('\n') : '✔ ' + t('integrity.clean'));
    setFailed(problems.length > 0);
  }
  return (
    <details className={`${s.dev} ${s.card} ${s.span}`} data-testid="card-dev">
      <summary>
        <div><h3>{t('dev.cardTitle')}</h3><div className={`${s.sub} ${s.mute}`}>{t('dev.cardSub')}</div></div>
        <span className={s.chev} aria-hidden="true">⌄</span>
      </summary>
      <div className={s.body}>
        <h4>{t('dev.title')}</h4>
        <div className={s.devbtns}>
          <button type="button" onClick={runTests} data-testid="dev-run">{t('dev.run')}</button>
          <button type="button" onClick={roundtrip} data-testid="dev-roundtrip">{t('dev.roundtrip')}</button>
          <button type="button" onClick={integrity} data-testid="dev-integrity">{t('integrity.title')}</button>
        </div>
        {out && <pre className={`${s.out} ${failed ? s.fail : ''}`} dir="ltr" data-testid="dev-out">{out}</pre>}
      </div>
    </details>
  );
}
