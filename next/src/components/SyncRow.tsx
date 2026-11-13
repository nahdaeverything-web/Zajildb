'use client';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { useZajilStore } from '@/src/db/react';
import { t, fmtDate } from '@/src/i18n.ext.js';
import s from './shared.module.css';

// The sync status row — shared-states §01. Sits above list content. `synced`
// renders NOTHING (the healthy state is silence); offline is calm, never
// error-styled; error is rare, gold, and links to الأدوات. State comes from
// the layer's syncStatus(), re-read on every data change through the bridge.
//
// HONEST STATUS (RULED 2026-11-13, RF-19). Silence now MEANS synced: the layer answers 'unknown' until it has counted the
// op log after a load, and the row says nothing for 'unknown' exactly as it says nothing for 'hidden' — it never had a
// "synced" label to show. Unsent work is said in a fancier's words, with since-when; the count of operations that used
// to stand here («{n} تغييرًا بانتظار المزامنة») is gone, everywhere: it read as a count of birds and misled for weeks.
const ICON: Record<string, string> = { syncing: '⟳', pending: '⌁', offline: '⚡', error: '⚠', off: '⏸' };
type Status = { state: string; pendingSince?: string | null; error?: { key?: string } | null };
export default function SyncRow() {
  const st = useZajilStore(() => db.syncStatus()) as Status;
  if (st.state === 'hidden' || st.state === 'synced' || st.state === 'unknown') return null;
  const text = st.state === 'pending' ? (st.pendingSince ? t('sync.pendingSince', { d: fmtDate(st.pendingSince, { withTime: true }) }) : t('sync.pending'))
    : st.state === 'error' ? t(st.error && st.error.key === 'sync.err.session' ? 'sync.err.session' : 'sync.error')
    : t('sync.' + st.state);
  return (
    <div className={`${s.sync} ${s[st.state]}`} data-testid="sync-row" data-state={st.state} role="status">
      <i aria-hidden="true">{ICON[st.state] ?? ''}</i>
      <span>{text}</span>
      {st.state === 'error' && <Link href="/tools" data-testid="sync-row-link">{t('nav.tools')}</Link>}
    </div>
  );
}
