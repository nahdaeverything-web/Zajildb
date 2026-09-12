'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as db from '@/src/db.js';
import { t } from '@/src/i18n.ext.js';
import { COUNTRIES_REGION, COUNTRIES_REST } from '@/src/countries.js';
import { Loading, initDB } from '@/src/components';
import { useAppVersion } from '@/src/components/version';
import s from './signin.module.css';

// Sign-in — design/approved/sign-in-v1.html. RULING 1 (Phase 4 order): this
// standalone screen is canonical and is NEVER a launch wall — the app opens
// usable and offline without an account, and nothing routes here on its own.
// The tools sync card sends you here; everything else works signed out.
//
// There is no vanilla view to port: the vanilla app signs in from inside the
// tools card (js/views/tools.js). Its WIRING is the reference — signIn() on the
// facade, and the three AuthError kinds are exactly the three states the spec
// draws: 'rejected' → the credentials message, 'network' → the offline message
// (and the button becomes «إعادة المحاولة»), 'config' → sync is not set up on
// this device. A raw status code is never surfaced, as the spec's own comment
// demands.
type State = '' | 'loading' | 'cred' | 'net' | 'cfg';
const Mark = ({ className }: { className: string }) => (
  <div className={className}><svg viewBox="0 0 100 100" fill="#fff" aria-hidden="true">
    <path d="M18 78c14 4 34 4 46-4 10-7 16-18 17-30 0-4-2-6-5-6-2 0-4 1-5 3l-4 8c-6 10-16 16-28 18-8 1-15 5-21 11z" />
    <path d="M62 34c3-6 9-9 15-8 3 0 5 2 5 5 0 2-1 3-3 4l-6 2c-4 2-8 1-11-3z" />
    <path d="M80 36l8 2-8 2z" /></svg></div>
);
const Warn = () => <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v6M12 16.5h.01" /></svg>;

export default function SignInView() {
  const router = useRouter();
  const [booted, setBooted] = useState(false);
  const [pane, setPane] = useState<'signin' | 'early'>('signin');
  const [state, setState] = useState<State>('');
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const version = useAppVersion();
  useEffect(() => { initDB().then(() => setBooted(true)); }, []);
  if (!booted) return <section className={s.screen}><Loading /></section>;

  const auth = db.authState() as { signedIn: boolean; email: string | null };
  const loading = state === 'loading';

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState('loading');
    try {
      await db.signIn(email.trim(), password);
      setPassword('');                                // never leave it in the DOM (js/views/tools.js:266)
      // The existing first-login flow, unchanged: syncNow() runs the same cycle the
      // background loop runs, which takes §6's first-login branch on its own. There is
      // no second code path for "just signed in" (js/views/tools.js:267-270).
      await db.syncNow();
      router.replace('/tools');                       // the sync card is where a signed-in session is managed
    } catch (err) {
      const kind = (err as { kind?: string }).kind;   // AuthError: 'rejected' | 'network' | 'config'
      setState(kind === 'network' ? 'net' : kind === 'config' ? 'cfg' : 'cred');
    }
  }

  return (
    <section className={s.screen} data-testid="signin-screen">
      {pane === 'signin' ? (
        <main className={s.auth} data-testid="pane-signin">
          <div className={s.brand}>
            <Mark className={s.mark} />
            <h1>{t('app.name')}</h1>
            <p className={s.sub}>{t('signin.tagline')}</p>
          </div>
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
            <button type="submit" className={`${s.cta} ${loading ? s.busy : ''}`} disabled={loading} aria-live="polite" data-testid="signin-submit">
              {loading && <span className={s.spin} />}
              <span className={s.lbl}>{loading ? t('signin.signingIn') : state === 'net' ? t('signin.retry') : t('sync.signIn')}</span>
            </button>
            <p className={s.alt}>{t('signin.noAccount')} <button type="button" className={s.linkbtn} onClick={() => { setPane('early'); window.scrollTo(0, 0); }} data-testid="go-early">{t('signin.earlyAccess')}</button></p>
            <p className={s.forgot}><span>{t('signin.forgot')}</span> <span>{t('signin.forgotHelp')}</span></p>
            <p className={s.invite}>{t('signin.inviteOnly')}</p>
          </form>
          {/* the installed version, as the service worker reports it — never a constant in the source (version_display.py) */}
          <div className={s.foot} data-testid="version">{t('about.version', { v: version || t('about.unknown') })}</div>
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
