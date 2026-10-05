'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { useZajilStore } from '@/src/db/react';
import { t } from '@/src/i18n.ext.js';
import { Loading, initDB } from '@/src/components';
import { SubScreen, StatusLine, SyncDetail, DuplicatesDetail, ImportDetail, RestoreDetail } from './parts';
import type { Backup } from './parts';
import s from './tools.module.css';

/**
 * The four sub-screens of الأدوات — RULED 2026-10-03 (tools-v2, shape (b), hybrid).
 *
 * Each is a REAL ROUTE (/tools/sync/, /tools/duplicates/, /tools/import/, /tools/restore/), not a modal: it survives
 * a back gesture and a reload, and the precache lists it by URL so it works offline. Nothing on them is further
 * than one tap from the list plus one tap on the screen — a fancier fixing a duplicate ring does not hunt.
 *
 * They exist for exactly the six controls the grouped list has no room for: the duplicate finder with its per-copy
 * deletes, import's mode and file picker, the snapshot list, and the sync detail with its error line and
 * rejected-records list.
 */
function useBooted() {
  const [booted, setBooted] = useState(false);
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  return booted;
}

export function SyncScreen() {
  const booted = useBooted();
  const st = useZajilStore((x) => x);
  if (!booted) return <section className={s.screen}><Loading /></section>;
  const settings = st.settings as Record<string, unknown>;
  const cfg = db.syncConfig() as { configured: boolean };
  const auth = db.authState() as { signedIn: boolean; email: string | null };
  return (
    <SubScreen title={t('sync.card')} testid="card-sync">
      {!cfg.configured ? (
        <div data-testid="sync-unconfigured"><StatusLine icon="plus" title={t('sync.notSetUp')} text={t('tools.account.offNote')} /></div>
      ) : !auth.signedIn ? (
        <div data-testid="sync-signed-out">
          <p className={s.detailText}>{t('tools.sync.outNote')}</p>
          <div className={s.actions}><Link href="/sign-in" className={`${s.btn} ${s.primary}`} data-testid="go-signin">{t('sync.signIn')}</Link></div>
        </div>
      ) : (
        <SyncDetail settings={settings} />
      )}
    </SubScreen>
  );
}

export function DuplicatesScreen() {
  const booted = useBooted();
  if (!booted) return <section className={s.screen}><Loading /></section>;
  return (
    <SubScreen title={t('tools.row.dup')} help={t('dup.title')} testid="card-duplicates">
      <DuplicatesDetail />
    </SubScreen>
  );
}

export function ImportScreen() {
  const booted = useBooted();
  if (!booted) return <section className={s.screen}><Loading /></section>;
  return (
    <SubScreen title={t('backup.import')} help={t('tools.import.help')} testid="card-import">
      <ImportDetail />
    </SubScreen>
  );
}

export function RestoreScreen() {
  const booted = useBooted();
  const [snapshots, setSnapshots] = useState<Backup[] | null>(null);
  // the snapshot list is read once, on arrival, as the tools-v1 card read it on mount
  useEffect(() => { if (booted) db.listBackups().then((b: Backup[]) => setSnapshots(b)); }, [booted]);
  if (!booted || snapshots === null) return <section className={s.screen}><Loading /></section>;
  return (
    <SubScreen title={t('backup.restoreAuto')} help={t('tools.restore.help')} testid="card-restore">
      <RestoreDetail snapshots={snapshots} />
    </SubScreen>
  );
}
