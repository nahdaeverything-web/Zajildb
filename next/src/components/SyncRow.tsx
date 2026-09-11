'use client';
import Link from 'next/link';
import * as db from '@/src/db.js';
import { useZajilStore } from '@/src/db/react';
import { t, fmtNum } from '@/src/i18n.ext.js';
import s from './shared.module.css';

// The sync status row — shared-states §01. Sits above list content. `synced`
// renders NOTHING (the healthy state is silence); offline is calm, never
// error-styled; error is rare, gold, and links to الأدوات. State comes from
// the layer's syncStatus(), re-read on every data change through the bridge.
const ICON: Record<string, string> = { syncing: '⟳', pending: '⌁', offline: '⚡', error: '⚠', off: '⏸' };
export default function SyncRow() {
  const st = useZajilStore(() => db.syncStatus());
  if (st.state === 'hidden' || st.state === 'synced') return null;
  const label = st.state === 'pending' ? t('sync.pending', { n: '\u0000' }).split('\u0000') : [t('sync.' + st.state)];
  return (
    <div className={`${s.sync} ${s[st.state]}`} data-testid="sync-row" data-state={st.state} role="status">
      <i aria-hidden="true">{ICON[st.state] ?? ''}</i>
      <span>{label.length === 2 ? <>{label[0]}<span className={s.n}>{fmtNum(st.pending)}</span>{label[1]}</> : label[0]}</span>
      {st.state === 'error' && <Link href="/tools" data-testid="sync-row-link">{t('nav.tools')}</Link>}
    </div>
  );
}
