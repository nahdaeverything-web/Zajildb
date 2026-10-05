'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { useZajilStore, selectBirds, useMediaForBird } from '@/src/db/react';
import { t, fmtDate, fmtNum } from '@/src/i18n.ext.js';
import { findDuplicateRings } from '@/src/engine/rings.js';
import { SyncRow, Loading, toast, confirmDialog, downscaleImage, saveSetting, initDB } from '@/src/components';
import { useAppVersion } from '@/src/components/version';
import { Section, Row, Seg, StatusLine, ExportDetail, ExamplesDetail, IntegrityDetail, ScannerDetail, DevDetail, syncRowCopy, Lofts } from './parts';
import type { Loft, Bird, Backup, SyncStatus, Anomaly } from './parts';
import s from './tools.module.css';

// Tools & settings — design/approved/tools-v2.html, behaviour from the tools-v1 port (js/views/tools.js).
// A grouped settings list in the spec's six sections — حسابي · اللوفت · البيانات · الفحوصات · الإعدادات · متقدّم —
// each row a disclosure, one open per section. What the rulings of 2026-10-03 add to the spec, all recorded in
// design/README.md:
//   HYBRID SHAPE — four rows NAVIGATE to a real route instead of opening inline, for the controls the list has no
//     room for: المزامنة (/tools/sync/: the status line, the error line, the rejected-records list, the actions),
//     استيراد (/tools/import/: the mode and the file picker), استرجاع نسخة (/tools/restore/: the snapshot list),
//     البحث عن تكرار (/tools/duplicates/: the groups with their per-copy deletes). Everything else is inline.
//   DEV PANEL — kept inside متقدّم, collapsed, exactly as tools-v1 had it.
//   TWO STRINGS KEPT — «آخر فحص» (the duplicates row's help and the integrity row) and «آخر نسخة تلقائية» (restore).
//   THE TEACHING DATA — tools-v1's row, which the spec dropped, kept as the fourth row of البيانات.
//   NOT BUILT — the spec's three NEW rows (الخطة الحالية, معرفة مزايا Pro, الإشعارات والتذكير) are omitted by order.
// Still built in from the Phase 4 order: RULING 1 (signed out, the account row offers a button that navigates to
// /sign-in; the inline form is superseded) and RULING 2 (the loft rows carry the certificate's branding fields).

export default function ToolsView() {
  const [booted, setBooted] = useState(false);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  const st = useZajilStore((x) => x);
  const birds = useZajilStore(selectBirds) as Bird[];
  const version = useAppVersion();
  // the restore row's «{n} متاحة» — an async read, once, as the tools-v1 card read its snapshot list
  const [snapN, setSnapN] = useState<number | null>(null);
  useEffect(() => { if (booted) db.listBackups().then((b: Backup[]) => setSnapN(b.length)); }, [booted]);
  if (!booted) return <section className={s.screen}><Loading /></section>;

  const settings = st.settings as Record<string, unknown>;
  const loft = db.currentLoft() as Loft | null;
  const cfg = db.syncConfig() as { configured: boolean };
  const auth = db.authState() as { signedIn: boolean; email: string | null };
  const status = db.syncStatus() as SyncStatus;
  const anomalies = (db.listSyncAnomalies ? db.listSyncAnomalies() : []) as Anomaly[];
  const sync = syncRowCopy(settings, cfg, auth, status, anomalies);
  const dups = (findDuplicateRings(birds) as unknown[]).length;
  const set = (k: string, v: unknown) => { saveSetting(k, v); };
  const depth = +(settings.coiDepth as number || 10);
  const hc = !!settings.highContrast;
  const lang = (settings.lang as string) || 'ar';
  const numerals = (settings.numerals as string) || 'western';
  const dates = (settings.dates as string) || 'both';
  const integrityN = typeof settings.integrityProblems === 'number' ? (settings.integrityProblems as number) : null;
  const scanUrl = (settings.scanServerUrl as string) || '';
  async function signOut() {
    const ok = await confirmDialog({ title: t('confirm.signOut.title'), body: t('sync.signOutKeepsData'), cancelLabel: t('act.cancel'), confirmLabel: t('sync.signOut'), confirmKind: 'ink' });
    // signOut() emits nothing (db/sync.js:199), so the row is told the way vanilla's card is — js/views/tools.js:221
    if (ok) { await db.signOut(); await db.refreshSyncStatus(); }
  }

  return (
    <section className={s.screen}>
      <header className={s.head}><div className={s.headIn}>
        <h1>{t('nav.tools')}</h1>
        <div className={s.sub}>{t('tools.sub')}</div>
      </div></header>
      <SyncRow />
      <main className={s.content} data-testid="tools-list">

        {/* ═══ حسابي ═══ the spec opens the account row by default */}
        <Section id="account" title={t('tools.sec.account')} defaultOpen="account">
          <Row id="account" icon="account" label={t('sync.account')}
            help={!cfg.configured ? t('tools.account.helpOff') : !auth.signedIn ? t('tools.account.helpOut') : t('tools.account.helpIn')}
            value={!cfg.configured ? t('tools.account.off') : !auth.signedIn ? t('sync.signIn') : auth.email}
            valueKind={cfg.configured && auth.signedIn ? 'data' : undefined}>
            {!cfg.configured ? (
              // NOT CONFIGURED: explanation only, deliberately no sign-in form (the spec, and sync_ui #32)
              <div data-testid="sync-unconfigured"><StatusLine icon="plus" title={t('sync.notSetUp')} text={t('tools.account.offNote')} /></div>
            ) : !auth.signedIn ? (
              <div data-testid="sync-signed-out">
                <p className={s.detailText}>{t('sync.signInToSync')}</p>
                {/* RULING 1: a button that NAVIGATES — the spec's inline form here is superseded by /sign-in */}
                <div className={s.actions}><Link href="/sign-in" className={`${s.btn} ${s.primary}`} data-testid="go-signin">{t('sync.signIn')}</Link></div>
              </div>
            ) : (
              <div data-testid="sync-signed-in">
                <div className={s.kv}><div className={s.kvRow}><span className={s.kvK}>{t('sync.email')}</span><span className={`${s.kvV} ${s.data}`} data-testid="sync-account">{auth.email}</span></div></div>
                <div className={s.actions}><button type="button" className={s.btn} onClick={signOut} data-testid="sign-out">{t('sync.signOut')}</button></div>
                <p className={s.detailNote}>{t('sync.signOutKeepsData')}</p>
              </div>
            )}
          </Row>
          <Row id="sync" icon="sync" href="/tools/sync" label={t('sync.card')} help={sync.help} value={sync.value} valueKind={sync.kind} />
        </Section>

        {/* ═══ اللوفت ═══ RULING 2: the certificate's branding fields */}
        <Section id="loft" title={t('set.loft')}>
          <LoftRows key={loft?.id || 'none'} loft={loft} />
        </Section>

        {/* ═══ البيانات ═══ */}
        <Section id="data" title={t('tools.sec.data')} foot={t('backup.auto', { h: fmtNum(12), n: fmtNum(7) })}>
          <Row id="export" icon="export" label={t('tools.row.export')} help={t('tools.export.help')} value={settings.lastExport ? fmtDate(settings.lastExport as string) : t('backup.never')}>
            <ExportDetail settings={settings} />
          </Row>
          <Row id="import" icon="import" href="/tools/import" label={t('backup.import')} help={t('tools.import.help')} />
          <Row id="restore" icon="restore" href="/tools/restore" label={t('backup.restoreAuto')} help={t('tools.restore.help')} value={snapN === null ? '' : t('tools.restore.available', { n: fmtNum(snapN) })} />
          <Row id="teaching" icon="teaching" label={t('example.title')} help={t('example.hint')}>
            <ExamplesDetail />
          </Row>
        </Section>

        {/* ═══ الفحوصات ═══ */}
        <Section id="checks" title={t('tools.sec.checks')}>
          <Row id="duplicates" icon="duplicates" href="/tools/duplicates" label={t('tools.row.dup')}
            help={dups ? t('tools.dup.helpFound') : t('tools.dup.helpClean')}
            value={dups ? t('tools.dup.foundN', { n: fmtNum(dups) }) : t('tools.dup.clean')} valueKind={dups ? 'gold' : 'brand'} />
          <Row id="integrity" icon="integrity" label={t('integrity.title')} help={t('tools.integrity.help')}
            value={integrityN === null ? t('tools.integrity.never') : integrityN ? fmtNum(integrityN) : t('tools.integrity.ok')}
            valueKind={integrityN === null ? undefined : integrityN ? 'gold' : 'brand'}>
            <IntegrityDetail settings={settings} />
          </Row>
        </Section>

        {/* ═══ الإعدادات ═══ every control writes through setSetting, as vanilla does */}
        <Section id="settings" title={t('tools.settings')}>
          <Row id="lang" icon="language" label={t('set.language')} value={t(lang === 'en' ? 'lang.en' : 'lang.ar')}>
            <Seg set={set} label={t('set.language')} k="lang" current={lang} options={[['ar', t('lang.ar')], ['en', t('lang.en')]]} />
          </Row>
          <Row id="numerals" icon="numerals" label={t('set.numerals')} help={t('tools.numerals.help')}
            value={<span className={numerals === 'eastern' ? s.numAr : s.num}>{numerals === 'eastern' ? '٠١٢٣٤٥٦٧٨٩' : '0123456789'}</span>}>
            <Seg set={set} label={t('set.numerals')} k="numerals" current={numerals}
              options={[['western', <>{t('set.numerals.westernShort')}<span className={s.num}>0123456789</span></>], ['eastern', <>{t('set.numerals.easternShort')}<span className={s.numAr}>٠١٢٣٤٥٦٧٨٩</span></>]]} />
            <p className={s.detailNote}>{t('set.numeralsHint')}</p>
          </Row>
          <Row id="dates" icon="dates" label={t('set.dates')} value={t('set.dates.' + dates)}>
            <Seg set={set} label={t('set.dates')} k="dates" current={dates}
              options={[['gregorian', t('set.dates.gregorian')], ['hijri', t('set.dates.hijri')], ['both', t('set.dates.both')]]} />
          </Row>
          <Row id="coi" icon="coi" label={t('set.coiDepth')} help={t('tools.coi.help')} value={t(depth > 10 ? 'tools.coi.valueMany' : 'tools.coi.value', { n: fmtNum(depth) })}>
            <div className={s.detailTitle}>{t('set.coiDepth')}</div>
            <div className={s.stepper} data-testid="set-coiDepth">
              <button type="button" aria-label={t('act.less')} onClick={() => set('coiDepth', Math.max(3, depth - 1))} data-testid="coi-less">−</button>
              <input id="coi" type="number" min={3} max={15} value={depth} aria-label={t('set.coiDepth')} onChange={(e) => { const v = Math.min(15, Math.max(3, +e.target.value || 10)); set('coiDepth', v); }} data-testid="coi-input" />
              <button type="button" aria-label={t('act.increase')} onClick={() => set('coiDepth', Math.min(15, depth + 1))} data-testid="coi-more">+</button>
              <span className={`${s.range} ${s.num}`}>3–15</span>
            </div>
          </Row>
          <Row id="contrast" icon="contrast" label={t('set.highContrast')} help={t('tools.hc.help')} value={t(hc ? 'tools.hc.on' : 'tools.hc.off')}>
            <div className={s.toggleLine}>
              <div><div className={s.detailTitle}>{t('set.highContrast')}</div><p className={s.detailText}>{t('tools.hc.text')}</p></div>
              <button type="button" className={s.switch} aria-pressed={hc} aria-label={t('tools.hc.aria')} onClick={() => set('highContrast', !hc)} data-testid="hc-input" />
            </div>
          </Row>
        </Section>

        {/* ═══ متقدّم ═══ */}
        <Section id="advanced" title={t('tools.group.advanced')} note={t('tools.sec.advancedNote')}>
          <Row id="scanner" icon="scanner" label={t('scan.title')} help={t('tools.scan.help')} value={scanUrl || t('tools.scan.offShort')} valueKind={scanUrl ? 'data' : undefined}>
            <ScannerDetail settings={settings} />
          </Row>
          {/* the dev panel: collapsed, exactly as tools-v1 had it (RULED 2026-10-03) */}
          <Row id="dev" icon="dev" testid="card-dev" label={t('dev.cardTitle')} help={t('dev.cardSub')} value={(open) => (open ? '' : t('tools.dev.collapsed'))}>
            <DevDetail />
          </Row>
          <Row id="version" icon="version" label={t('about.versionLabel')} value={<span data-testid="about-version">{version || t('about.unknown')}</span>} valueKind="data">
            <p className={s.detailText}>{t('about.hint')}</p>
            <p className={s.detailNote}>{t('tools.about.note')}</p>
          </Row>
        </Section>
      </main>
    </section>
  );
}

/**
 * The six loft rows share one draft: a field edited in one row is not lost when another row's «حفظ» is pressed,
 * because every «حفظ» writes the whole draft through Lofts.save — the one write tools-v1's single button made.
 * The logo is device-local media like a photo: its bytes go to the media store and never to the op log, and only
 * its id lives on the loft record (RULING 2).
 */
function LoftRows({ loft }: { loft: Loft | null }) {
  const [f, setF] = useState({ name: loft?.name || '', location: loft?.location || '', breederName: loft?.breederName || '', phone: loft?.phone || '', website: loft?.website || '' });
  const [logo, setLogo] = useState<string | null>(loft?.logoMediaId || null);
  const media = useMediaForBird(loft?.id || null);
  const logoName = (media.find((m) => m.id === logo)?.name as string | undefined) || null;
  const fileIn = useRef<HTMLInputElement>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  async function save(over: Partial<Loft> = {}) {
    if (!loft) return;
    await Lofts.save({ ...loft, name: f.name.trim(), location: f.location.trim(), breederName: f.breederName.trim(), phone: f.phone.trim(), website: f.website.trim(), logoMediaId: logo, ...over });
    toast(t('toast.saved'), { kind: 'success' });
  }
  async function pickLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file || !loft) return;
    const m = await db.addMedia(loft.id, 'document', 'logo', file.name, await downscaleImage(file)) as { id: string };
    setLogo(m.id); e.target.value = '';
  }
  async function removeLogo() {
    if (!logo) return;
    await db.deleteMedia(logo);        // the bytes go with it — a pointer to nothing is what this prevents
    setLogo(null);
    await save({ logoMediaId: null });
  }
  // a plain function returning JSX, not a component: a component declared in a render body remounts on every render
  const saveBtn = (field: string) => <div className={s.actions}><button type="button" className={`${s.btn} ${s.primary}`} onClick={() => save()} data-testid="loft-save" data-field={field}>{t('act.save')}</button></div>;
  const field = (id: string, k: keyof typeof f, label: string, dir?: 'ltr', type = 'text') => (
    <div className={s.field}>
      <label htmlFor={id}>{label}</label>
      <input id={id} type={type} dir={dir} className={dir ? s.data : ''} value={f[k]} onChange={set(k)} placeholder={k === 'name' ? t('loft.unnamed') : undefined} data-testid={id} />
    </div>
  );
  return (
    <>
      <Row id="loft-name" icon="loft" label={t('set.loftName')} value={loft?.name || t('loft.unnamed')}>{field('ln', 'name', t('set.loftName'))}{saveBtn('name')}</Row>
      <Row id="loft-location" icon="location" label={t('set.loftLocation')} value={loft?.location || ''}>{field('lc', 'location', t('set.loftLocation'))}{saveBtn('location')}</Row>
      <Row id="breeder" icon="account" label={t('set.breederName')} value={loft?.breederName || ''}>{field('lb', 'breederName', t('set.breederName'))}{saveBtn('breederName')}</Row>
      <Row id="phone" icon="phone" label={t('set.phone')} value={loft?.phone || ''} valueKind="data">{field('lp', 'phone', t('set.phone'), 'ltr', 'tel')}{saveBtn('phone')}</Row>
      <Row id="website" icon="website" label={t('set.website')} value={loft?.website || ''} valueKind="data">{field('lw', 'website', t('set.website'), 'ltr', 'url')}{saveBtn('website')}</Row>
      <Row id="logo" icon="logo" label={t('set.logo')} value={logo ? t('tools.logo.present') : t('set.logoNone')}>
        <p className={s.detailText} data-testid="logo-state">{logo ? t('tools.logo.current', { name: logoName || t('set.logoSet') }) : t('set.logoNone')}</p>
        <div className={s.filebox}>
          <button type="button" className={s.btn} onClick={() => fileIn.current?.click()} data-testid="logo-pick">{t('tools.logo.pick')}</button>
          <span className={s.fileName}>{t('tools.logo.types')}</span>
          <input ref={fileIn} type="file" accept="image/*" onChange={pickLogo} data-testid="logo-input" />
        </div>
        <p className={s.detailNote}>{t('set.logoHint')}</p>
        <div className={s.actions}>
          <button type="button" className={`${s.btn} ${s.primary}`} onClick={() => save()} data-testid="loft-save" data-field="logo">{t('act.save')}</button>
          {logo && <button type="button" className={s.btn} onClick={removeLogo} data-testid="logo-remove">{t('tools.logo.remove')}</button>}
        </div>
      </Row>
    </>
  );
}
