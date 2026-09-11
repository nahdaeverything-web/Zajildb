'use client';
import { useState, type ReactNode } from 'react';
import { t } from '@/src/i18n.ext.js';
import s from './shared.module.css';
// One-time notice — §05. Above content, below the sync row. Closed by its
// action or ✕ and does not return; persistence of "seen" is the caller's.
export default function Notice({ children, action, onDismiss, testid = 'notice' }:
  { children: ReactNode; action?: ReactNode; onDismiss?: () => void; testid?: string }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div className={s.notice} data-testid={testid} role="status">
      <span className={s.msg}>{children}{action}</span>
      <button type="button" className={s.x} aria-label={t('act.close')} onClick={() => { setOpen(false); onDismiss?.(); }} data-testid="notice-dismiss">✕</button>
    </div>
  );
}
