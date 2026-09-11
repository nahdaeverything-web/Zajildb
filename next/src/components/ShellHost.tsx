'use client';
import { useEffect, useRef } from 'react';
import { useShell, dismissToast, closeDialog } from './shell';
import s from './shared.module.css';

// Renders the toast stack and the one modal dialog. Mounted once in the root
// layout. Dialog: Escape closes as cancel; Tab is trapped; the overlay click
// is NOT a cancel (the spec's dialogs are decisions, not popovers).
export default function ShellHost() {
  const { toasts, dialog } = useShell();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!dialog) return;
    const prev = document.activeElement as HTMLElement | null;
    document.body.style.overflow = 'hidden';
    box.current?.querySelector<HTMLElement>('button')?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { closeDialog(false); return; }
      if (e.key !== 'Tab' || !box.current) return;
      const items = [...box.current.querySelectorAll<HTMLElement>('a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])')].filter((el) => !el.hasAttribute('disabled'));
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = ''; prev?.focus?.(); };
  }, [dialog]);
  return (
    <>
      <div className={s.toaststack} data-testid="toast-stack" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`${s.toast} ${t.kind !== 'plain' ? s[t.kind] : ''}`} role="status" data-testid="toast" data-kind={t.kind}>
            {t.kind !== 'plain' && <i />}
            <span className={s.msg}>{t.msg}</span>
            {t.actionLabel && <button type="button" onClick={() => { dismissToast(t.id); t.onAction?.(); }} className={s.act} data-testid="toast-action">{t.actionLabel}</button>}
          </div>
        ))}
      </div>
      {dialog && (
        <div className={`${s.overlay} ${s.modal}`} data-testid="dialog-overlay">
          <div className={s.dlg} role="dialog" aria-modal="true" aria-label={dialog.title} ref={box} data-testid="dialog">
            <h3>{dialog.title}</h3>
            {dialog.who && <div className={s.who}><span className={s.nm}>{dialog.who.label}</span>{dialog.who.plate && <span className={`${s.plate} ${s.sm}`}><span>{dialog.who.plate}</span></span>}</div>}
            {dialog.body && <p>{dialog.body}</p>}
            {dialog.list && (
              <ul className={dialog.list.kind === 'errs' ? s.errs : s.warns} data-testid={`dialog-${dialog.list.kind}`}>
                {dialog.list.items.map((it, i) => <li key={i}><b>{it.field}</b> {it.text}</li>)}
              </ul>
            )}
            <div className={s.btns}>
              <button type="button" className={s.cancel} onClick={() => closeDialog(false)} data-testid="dialog-cancel">{dialog.cancelLabel}</button>
              {dialog.confirmLabel && (
                <button type="button" className={dialog.confirmKind === 'danger' ? s.danger : dialog.confirmKind === 'ink' ? s.ink : s.brand} onClick={() => closeDialog(true)} data-testid="dialog-confirm">{dialog.confirmLabel}</button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
