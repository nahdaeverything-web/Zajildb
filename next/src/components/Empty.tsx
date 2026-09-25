import Link from 'next/link';
import s from './shared.module.css';

// Empty states — shared-states §06. One fixed shape: mark · short line · one
// primary action (`.cta`); the quiet no-results variant carries an outline
// action (`.alt`). Actions are buttons with handlers, or links via `href`.
//
// `href` actions MUST go through next/link. This was a plain <a href={a.href}>, and a raw
// anchor is emitted verbatim: no basePath, no trailing slash. On the deployment that means
// the first-run CTA «أضف أول طائر» pointed at `/bird/new` instead of `/zajilv2/bird/new/`,
// which is not a route of this app at all — GitHub's 404 page, from the one control an empty
// loft offers. A HUMAN found it by clicking; every suite was green, because every suite
// serves the app at the ROOT, where the wrong URL and the right one are the same string.
type Act = { label: string; onClick?: () => void; href?: string; testid?: string };
export default function Empty({ title, body, cta, alt, quiet = false, testid = 'empty-state', hint }:
  { title: string; body?: string; cta?: Act; alt?: Act; quiet?: boolean; testid?: string; hint?: string }) {
  const btn = (a: Act, cls: string) => a.href
    ? <Link className={cls} href={a.href} data-testid={a.testid}>{a.label}</Link>
    : <button type="button" className={cls} onClick={a.onClick} data-testid={a.testid}>{a.label}</button>;
  return (
    <div className={`${s.empty} ${quiet ? s.quiet : ''}`} data-testid={testid}>
      <div className={s.mark} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3c-3 4-5 6-5 9a5 5 0 0 0 10 0c0-3-2-5-5-9z"/></svg></div>
      <h2>{title}</h2>
      {body && <p>{body}</p>}
      {cta && btn(cta, s.cta)}
      {alt && btn(alt, s.alt)}
      {hint && <div className={s.hint}>{hint}</div>}
    </div>
  );
}
