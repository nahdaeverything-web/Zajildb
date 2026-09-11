import type { ReactNode } from 'react';
import s from './shared.module.css';

// A labelled field with the spec's two non-blocking/blocking states — §04:
// red (`error`) under the field blocks save; amber (`warn`) explains and lets
// the user continue. The input is passed in so forms keep control of it.
export default function Field({ label, children, error, warn, hint, testid }:
  { label: string; children: ReactNode; error?: string | null; warn?: { title: string; body?: ReactNode } | null; hint?: ReactNode; testid?: string }) {
  return (
    <div className={`${s.field} ${error ? s.err : ''} ${warn ? s.warn : ''}`} data-testid={testid}>
      <label>{label}</label>
      {children}
      {error && <div className={s['err-msg']} role="alert" data-testid="field-error">{error}</div>}
      {warn && <div className={s.warnbox} data-testid="field-warn"><div className={s.t}>{warn.title}</div>{warn.body && <p>{warn.body}</p>}</div>}
      {!error && !warn && hint}
    </div>
  );
}
