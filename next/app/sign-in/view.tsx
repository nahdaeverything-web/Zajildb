'use client';
import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import * as db from '@/src/db.js';
import { t, fmtNum } from '@/src/i18n.ext.js';
import { todayISO } from '@/src/dates.js';
import { COUNTRIES_REGION, COUNTRIES_REST } from '@/src/countries.js';
import { Loading, initDB, toast, confirmDialog, choiceDialog, downloadBlob } from '@/src/components';
import { useAppVersion } from '@/src/components/version';
import s from './signin.module.css';

// Sign-in — design/approved/sign-in-v1.html. RULING 1 (Phase 4 order) made this
// standalone screen canonical, and NOT a launch wall. SUPERSEDED 2026-10-07: the
// same screen now stands as THE SIGN-IN GATE on a configured build (see `gate`
// below and src/components/Gate.tsx) — with no session the app shows it on every
// route. A signed-in device goes through, online or offline; a build with no
// sync configuration has nothing to sign into and does not gate.
//
// There is no vanilla view to port: the vanilla app signs in from inside the
// tools card (js/views/tools.js). Its WIRING is the reference — signIn() on the
// facade, and the three AuthError kinds are exactly the three states the spec
// draws: 'rejected' → the credentials message, 'network' → the offline message
// (and the button becomes «إعادة المحاولة»), 'config' → sync is not set up on
// this device. A raw status code is never surfaced, as the spec's own comment
// demands.
//
// A FOURTH KIND, port-only (RULED 2026-10-05, ROOT-FINDINGS RF-13): 'owner' — the credentials
// are good but belong to a different account from the one this device's data belongs to.
// signIn() stops before storing the session, so nothing has synced and nothing can. This
// screen then puts the decision the ruling orders, and there is no way past it without
// choosing: export what is here, or clear it and come in as the new account. Cancelling
// leaves the device exactly as it was — still signed out, every record in place.
type State = '' | 'loading' | 'cred' | 'net' | 'cfg' | 'owner';
const Mark = ({ className }: { className: string }) => (
  <div className={className}><svg viewBox="0 0 100 100" fill="#fff" aria-hidden="true">
    <path d="M18 78c14 4 34 4 46-4 10-7 16-18 17-30 0-4-2-6-5-6-2 0-4 1-5 3l-4 8c-6 10-16 16-28 18-8 1-15 5-21 11z" />
    <path d="M62 34c3-6 9-9 15-8 3 0 5 2 5 5 0 2-1 3-3 4l-6 2c-4 2-8 1-11-3z" />
    <path d="M80 36l8 2-8 2z" /></svg></div>
);
const Warn = () => <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v6M12 16.5h.01" /></svg>;

/**
 * `gate` — the screen is standing as THE SIGN-IN GATE (src/components/Gate.tsx) in front of
 * whatever route the person opened. With data on the device it shows the loft — its name and
 * the breeder's name, never an account — and offers export right here; a successful sign-in
 * then stays on the route that was opened instead of leaving for الأدوات.
 */
export type GateInfo = { empty: true } | { loft: string; breeder: string };

export default function SignInView({ gate }: { gate?: GateInfo } = {}) {
  const router = useRouter();
  const atSignIn = (usePathname() ?? '').replace(/\.html$/, '').replace(/\/$/, '') === '/sign-in';
  const [booted, setBooted] = useState(false);
  const [pane, setPane] = useState<'signin' | 'early'>('signin');
  const [state, setState] = useState<State>('');
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const version = useAppVersion();
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  if (!booted) return <section className={s.screen}><Loading /></section>;

  const auth = db.authState() as { signedIn: boolean; email: string | null };
  const loading = state === 'loading';

  // `replaceLocalData` is passed ONLY by decide(), after a person has chosen it twice.
  async function attempt(replaceLocalData: boolean) {
    setState('loading');
    try {
      await db.signIn(email.trim(), password, replaceLocalData ? { replaceLocalData: true } : undefined);
      setPassword('');                                // never leave it in the DOM (js/views/tools.js:266)
      // The existing first-login flow, unchanged: syncNow() runs the same cycle the
      // background loop runs, which takes §6's first-login branch on its own. There is
      // no second code path for "just signed in" (js/views/tools.js:267-270).
      await db.syncNow();
      if (!gate || atSignIn) router.replace('/tools');   // the sync card is where a signed-in session is managed; a gate on any other route lifts in place
    } catch (err) {
      const e = err as { kind?: string; previous?: string | null };   // AuthError: 'rejected' | 'network' | 'config' | 'owner'
      if (e.kind === 'owner') { setState('owner'); await decide(e.previous || null); return; }
      setState(e.kind === 'network' ? 'net' : e.kind === 'config' ? 'cfg' : 'cred');
    }
  }
  function submit(e: React.FormEvent) { e.preventDefault(); attempt(false); }

  // THE DECISION. Nothing has been stored, merged, pushed or cleared when this opens. Export
  // returns here — a copy in hand does not settle whose device this is — and clearing asks a
  // second time, naming what goes, because it cannot be undone.
  async function decide(previous: string | null) {
    for (;;) {
      const choice = await choiceDialog({
        title: t('signin.owner.title'),
        who: { label: previous ? t('signin.owner.who', { hint: previous }) : t('signin.owner.whoUnknown') },
        body: t('signin.owner.body'),
        cancelLabel: t('act.cancel'),
        altLabel: t('signin.owner.export'), altKind: 'primary',
        confirmLabel: t('signin.owner.clear'), confirmKind: 'danger',
      });
      if (choice === 'alt') { await exportExisting(); continue; }
      if (choice !== 'confirm') return;
      const sure = await confirmDialog({
        title: t('signin.owner.confirmTitle'),
        body: t('signin.owner.confirmBody', { n: fmtNum(db.allBirds().length) }),
        cancelLabel: t('act.cancel'), confirmLabel: t('signin.owner.confirmGo'), confirmKind: 'danger',
      });
      if (sure) { await attempt(true); return; }
    }
  }
  async function exportExisting() {
    try {
      downloadBlob(await db.exportAllBlob({}), `zajil-export-${todayISO()}.json`);
      toast(t('toast.exported'), { kind: 'success' });
    } catch (e) {
      toast(t('toast.exportFailed'), { kind: 'error' });
      console.error('export failed', e);
    }
  }

  return (
    <section className={s.screen} data-testid="signin-screen" data-gate={gate ? ('empty' in gate ? 'empty' : 'records') : undefined}>
      {pane === 'signin' ? (
        <main className={s.auth} data-testid="pane-signin">
          <div className={s.brand}>
            <Mark className={s.mark} />
            <h1>{t('app.name')}</h1>
            <p className={s.sub}>{t('signin.tagline')}</p>
          </div>
          {gate && !('empty' in gate) && (
            // THE LOFT, NOT THE ACCOUNT. A fancier recognising his own loft knows he is in the right
            // place and needs the right address — not locked out by a screen that tells him nothing.
            <div className={s.gate} data-testid="gate">
              <div className={s.gateLoft} data-testid="gate-loft">{t('gate.holds', { loft: gate.loft || t('loft.unnamed') })}</div>
              {gate.breeder && <div className={s.gateBreeder} data-testid="gate-breeder">{t('cert.breederLine', { n: gate.breeder })}</div>}
              <p className={s.gateNote}>{t('gate.signInToReach')}</p>
              {/* export, on the gate itself — the escape hatch, never a bypass */}
              <button type="button" className={s.gateExport} onClick={exportExisting} data-testid="gate-export">{t('signin.owner.export')}</button>
            </div>
          )}
          {gate && 'empty' in gate && <div data-testid="gate" hidden />}
          {auth.signedIn ? (
            <div className={`${s.msg} ${s.net}`} role="status" data-testid="already-signed-in">
              <Warn /><span>{`${t('sync.account')}: ${auth.email || ''}`}<small>{t('signin.alreadyBody')}</small></span>
            </div>
          ) : null}
          <form onSubmit={submit} data-state={state} data-testid="signin-form">
            <div className={s.field}>
              <label htmlFor="email">{t('sync.email')}</label>
              <input id="email" type="email" autoComplete="username" placeholder="name@example.com" className={state === 'cred' ? s.err : ''}
                aria-invalid={state === 'cred'} disabled={loading} value={email} onChange={(e) => { setEmail(e.target.value); setState(''); }} data-testid="f-email" />
            </div>
            <div className={s.field}>
              <label htmlFor="password">{t('sync.password')}</label>
              <input id="password" type="password" autoComplete="current-password" placeholder="••••••••" className={state === 'cred' ? s.err : ''}
                aria-invalid={state === 'cred'} disabled={loading} value={password} onChange={(e) => { setPassword(e.target.value); setState(''); }} data-testid="f-password" />
            </div>
            {state === 'cred' && <div className={`${s.msg} ${s.cred}`} role="alert" data-testid="msg-cred"><Warn /><span>{t('signin.badCredentials')}</span></div>}
            {state === 'net' && <div className={`${s.msg} ${s.net}`} role="status" data-testid="msg-net"><Warn /><span>{t('signin.offline')}<small>{t('signin.offlineBody')}</small></span></div>}
            {state === 'cfg' && <div className={`${s.msg} ${s.cfg}`} role="status" data-testid="msg-cfg"><Warn /><span>{t('sync.notSetUp')}<small>{t('signin.notConfiguredBody')}</small></span></div>}
            {state === 'owner' && <div className={`${s.msg} ${s.cfg}`} role="alert" data-testid="msg-owner"><Warn /><span>{t('signin.owner.inline')}<small>{t('signin.owner.inlineBody')}</small></span></div>}
            <button type="submit" className={`${s.cta} ${loading ? s.busy : ''}`} disabled={loading} aria-live="polite" data-testid="signin-submit">
              {loading && <span className={s.spin} />}
              <span className={s.lbl}>{loading ? t('signin.signingIn') : state === 'net' ? t('signin.retry') : t('sync.signIn')}</span>
            </button>
            <p className={s.alt}>{t('signin.noAccount')} <button type="button" className={s.linkbtn} onClick={() => { setPane('early'); window.scrollTo(0, 0); }} data-testid="go-early">{t('signin.earlyAccess')}</button></p>
            <p className={s.forgot} data-testid="signin-help"><span>{t('signin.forgot')}</span> <span>{t('signin.forgotHelp')}</span></p>
            <p className={s.invite}>{t('signin.inviteOnly')}</p>
          </form>
          {/* the installed version, as the service worker reports it — never a constant in the source (version_display.py) */}
          {/* the label is Arabic, the version token is LTR data — only the token gets mono,
              or the Arabic falls back per character and reads as letter-spaced */}
          <div className={s.foot} data-testid="version">{t('about.version', { v: '' }).trim()} <code>{version || t('about.unknown')}</code></div>
        </main>
      ) : (
        <EarlyAccess onBack={() => { setPane('signin'); window.scrollTo(0, 0); }} />
      )}
    </section>
  );
}

/**
 * The early-access request. Its submit is DELIBERATELY UNWIRED: design/README.md
 * records that the form's submission target is a design placeholder until launch,
 * so this collects the fields, shows the spec's success pane, and sends nothing.
 * When a target exists, POST the object below from here — nothing else changes.
 */
function EarlyAccess({ onBack }: { onBack: () => void }) {
  const [done, setDone] = useState(false);
  const [f, setF] = useState({ name: '', email: '', country: '', city: '', loft: '', note: '' });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  function submit(e: React.FormEvent) {
    e.preventDefault();
    // const request = { ...f, at: nowISO() };   ← the payload, when there is somewhere to send it
    setDone(true); window.scrollTo(0, 0);
  }
  return (
    <main className={s.early} data-testid="pane-early">
      <button type="button" className={s.back} onClick={onBack} data-testid="early-back">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>{t('sync.signIn')}
      </button>
      {done ? (
        <div className={s.done} data-testid="early-done">
          <div className={s.ok}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l4 4L19 7" /></svg></div>
          <h1>{t('signin.early.doneTitle')}</h1>
          <p>{t('signin.early.doneBody')}</p>
          <div className={s.mail} data-testid="early-mail">{f.email || 'name@example.com'}</div>
          <button type="button" className={s.cta} onClick={onBack} data-testid="early-return">{t('signin.early.back')}</button>
        </div>
      ) : (
        <div data-testid="early-form">
          <Mark className={s.mark} />
          <h1>{t('signin.early.title')}</h1>
          <p className={s.lead}>{t('signin.early.lead')}</p>
          <form onSubmit={submit}>
            <div className={s.field}><label htmlFor="ea-name">{t('bird.name')}</label><input id="ea-name" type="text" required placeholder={t('signin.early.namePlaceholder')} value={f.name} onChange={set('name')} data-testid="ea-name" /></div>
            <div className={s.field}><label htmlFor="ea-email">{t('sync.email')}</label><input id="ea-email" type="email" required placeholder="name@example.com" value={f.email} onChange={set('email')} data-testid="ea-email" /></div>
            <div className={s.field}>
              <label htmlFor="ea-country">{t('race.country')}</label>
              <select id="ea-country" required value={f.country} onChange={set('country')} data-testid="ea-country">
                <option value="" disabled>{t('signin.early.chooseCountry')}</option>
                <optgroup label={t('signin.early.region')}>{COUNTRIES_REGION.map((c: string) => <option key={c} value={c}>{c}</option>)}</optgroup>
                <optgroup label={t('signin.early.allCountries')}>{COUNTRIES_REST.map((c: string) => <option key={c} value={c}>{c}</option>)}</optgroup>
              </select>
            </div>
            <div className={s.field}><label htmlFor="ea-city">{t('signin.early.city')}</label><input id="ea-city" type="text" placeholder={t('signin.early.cityPlaceholder')} value={f.city} onChange={set('city')} data-testid="ea-city" /></div>
            <div className={s.field}><label htmlFor="ea-loft">{t('set.loftName')} <span>{t('common.optional')}</span></label><input id="ea-loft" type="text" placeholder={t('signin.early.loftPlaceholder')} value={f.loft} onChange={set('loft')} data-testid="ea-loft" /></div>
            <div className={s.field}><label htmlFor="ea-note">{t('common.notes')} <span>{t('common.optional')}</span></label><textarea id="ea-note" placeholder={t('signin.early.notePlaceholder')} value={f.note} onChange={set('note')} data-testid="ea-note" /></div>
            <button type="submit" className={s.cta} data-testid="early-submit">{t('signin.early.send')}</button>
            <p className={s.fine}>{t('signin.early.fine')}</p>
          </form>
        </div>
      )}
    </main>
  );
}
