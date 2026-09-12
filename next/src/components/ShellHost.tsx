'use client';
import { useEffect, useLayoutEffect, useRef } from 'react';
import { useShell, dismissToast, closeDialog } from './shell';
import s from './shared.module.css';

// Renders the toast stack and the one modal dialog. Mounted once in the root
// layout. Dialog: Escape closes as cancel; Tab is trapped; the overlay click
// is NOT a cancel (the spec's dialogs are decisions, not popovers).
//
// Toast placement (ruling C, 4B addendum). The spec's rule is «12px above the
// bottom chrome», and shared-states drew that against the tab bar alone
// because its gallery had nothing else fixed. Real screens add their own
// fixed bottom chrome — the profile and pedigree certificate CTAs, the loft
// and breeding FABs, the bird form's action bar — and a stack pinned to
// 71+12 covered every one of them. So the stack measures the live chrome
// instead: each such element carries data-bottom-chrome, and the toast sits
// 12px above the highest one on screen (12px from the edge when there is
// none, e.g. the desktop rail). Measured, not hard-coded, so it stays right
// across breakpoints and across a navigation that happens while a toast is up.
const CHROME_BAND = 240;   // only chrome anchored to the bottom of the viewport can cover a toast

export default function ShellHost() {
  const { toasts, dialog } = useShell();
  const box = useRef<HTMLDivElement>(null);
  const stack = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = stack.current;
    if (!el) return;
    if (!toasts.length) { el.style.bottom = ''; return; }
    let raf = 0;
    const place = () => {
      raf = 0;
      let top = window.innerHeight;
      for (const c of document.querySelectorAll<HTMLElement>('[data-bottom-chrome]')) {
        const cs = getComputedStyle(c);
        if (cs.position !== 'fixed' || cs.display === 'none' || cs.visibility === 'hidden') continue;
        const r = c.getBoundingClientRect();
        if (r.height < 1 || r.bottom < window.innerHeight - CHROME_BAND) continue;
        top = Math.min(top, r.top);
      }
      el.style.bottom = `${Math.round(window.innerHeight - top) + 12}px`;
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(place); };
    place();
    window.addEventListener('resize', schedule);
    // a toast can outlive the screen that raised it (delete → navigate → undo), so follow the DOM too
    const mo = new MutationObserver(schedule);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => { window.removeEventListener('resize', schedule); mo.disconnect(); if (raf) cancelAnimationFrame(raf); };
  }, [toasts]);
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
      <div className={s.toaststack} ref={stack} data-testid="toast-stack" aria-live="polite">
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
