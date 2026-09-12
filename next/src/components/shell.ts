'use client';
// shell.ts — toasts and confirm dialogs with the SAME call shape as vanilla
// js/ui.js (toast / undoToast / confirmDialog → Promise<boolean>), so a view's
// wiring ports one-to-one. Timings follow shared-states-v1, which wins over
// vanilla's: success/info 4 s, error 6 s, undo 6 s.
//
// This is UI state, not data: a tiny external store of its own, rendered by
// <ShellHost/>. It is not a second data-change mechanism — the data layer's
// onChange stays the only one of those.
import { useSyncExternalStore } from 'react';

export type ToastKind = 'plain' | 'success' | 'error' | 'info';
export type Toast = { id: number; msg: string; kind: ToastKind; actionLabel?: string; onAction?: () => void };
export type Dialog = {
  id: number; title: string; body?: string; who?: { label: string; plate?: string };
  kinds?: string[]; list?: { kind: 'errs' | 'warns'; items: Array<{ field: string; text: string }> };
  cancelLabel: string; confirmLabel: string | null; confirmKind: 'danger' | 'primary' | 'ink';
  resolve: (ok: boolean) => void;
};
type State = { toasts: Toast[]; dialog: Dialog | null; version: number };
let state: State = { toasts: [], dialog: null, version: 0 };
const listeners = new Set<() => void>();
const set = (patch: Partial<State>) => { state = { ...state, ...patch, version: state.version + 1 }; for (const l of listeners) l(); };
let seq = 0;

/**
 * At most two toasts are visible; a third drops the oldest (ruling 6, 4C
 * acceptance). The spec's stack is a column and vanilla appends without a cap,
 * but the measured clearance under ruling C holds at two, and three Arabic
 * toasts at once is not a scenario a fancier meets — the third would reach into
 * the last row of a short list. The dropped toast's timer is harmless: it fires
 * on an id that is already gone.
 */
export const MAX_TOASTS = 2;

export function toast(msg: string, opts: { timeout?: number; actionLabel?: string; onAction?: () => void; kind?: ToastKind } = {}) {
  const kind = opts.kind ?? 'plain';
  const id = ++seq;
  const timeout = opts.timeout ?? (kind === 'error' ? 6000 : 4000);
  const next = [...state.toasts, { id, msg, kind, actionLabel: opts.actionLabel, onAction: opts.onAction }];
  set({ toasts: next.slice(-MAX_TOASTS) });
  if (timeout) setTimeout(() => dismissToast(id), timeout);
  return id;
}
export function dismissToast(id: number) { if (state.toasts.some((t) => t.id === id)) set({ toasts: state.toasts.filter((t) => t.id !== id) }); }
/** Follows every delete. 6 s, per the spec. `actionLabel` is act.undo, supplied by the caller through i18n. */
export function undoToast(msg: string, undoLabel: string, onUndo: () => void) {
  return toast(msg, { timeout: 6000, actionLabel: undoLabel, onAction: onUndo });
}
/** Resolves true on confirm, false on cancel / close / Escape — vanilla confirmDialog's contract. */
export function confirmDialog(d: Omit<Dialog, 'id' | 'resolve'>): Promise<boolean> {
  return new Promise((resolve) => set({ dialog: { ...d, id: ++seq, resolve } }));
}
export function closeDialog(ok: boolean) { const d = state.dialog; if (!d) return; set({ dialog: null }); d.resolve(ok); }
export function useShell() { return useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, () => state, () => state); }
