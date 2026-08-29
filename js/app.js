// app.js — boot, router, shell. Local-first: nothing here touches the network
// except the (optional) service worker registration.

import {
  initDB, state, setSetting, onChange, autoBackup, takeSyncDuplicateNotice,
  syncStatus, refreshSyncStatus, startSyncLoop,
} from './db.js';
import { configure, t, getLang, fmtDate } from './i18n.js';
import { h, clear, toast, runViewTeardowns, isModalOpen, onModalsClosed } from './ui.js';
import { renderBirds } from './views/birds.js';
import { renderBirdDetail } from './views/bird-detail.js';
import { renderBirdForm } from './views/bird-form.js';
import { renderPedigree } from './views/pedigree.js';
import { renderBreeding } from './views/breeding.js';
import { renderRaces } from './views/races.js';
import { renderHealth } from './views/health.js';
import { renderStats } from './views/stats.js';
import { renderTools } from './views/tools.js';
import { renderCertificate } from './views/cert.js';

const routes = [
  [/^#\/birds$/, () => renderBirds()],
  [/^#\/bird\/new(?:\?(.*))?$/, (m) => renderBirdForm(null, new URLSearchParams(m[1] || ''))],
  [/^#\/bird\/([\w-]+)\/edit$/, (m) => renderBirdForm(m[1])],
  [/^#\/bird\/([\w-]+)$/, (m) => renderBirdDetail(m[1])],
  [/^#\/pedigree\/([\w-]+)$/, (m) => renderPedigree(m[1])],
  [/^#\/cert\/([\w-]+)$/, (m) => renderCertificate(m[1])],
  [/^#\/breeding$/, () => renderBreeding()],
  [/^#\/races$/, () => renderRaces()],
  [/^#\/health$/, () => renderHealth()],
  [/^#\/stats$/, () => renderStats()],
  [/^#\/tools$/, () => renderTools()],
];

const NAV = [
  ['#/birds', 'nav.birds', '🕊'],
  ['#/breeding', 'nav.breeding', '🥚'],
  ['#/races', 'nav.races', '🏁'],
  ['#/health', 'nav.health', '💊'],
  ['#/stats', 'nav.stats', '📊'],
  ['#/tools', 'nav.tools', '⚙'],
];

export function navigate(hash) { location.hash = hash; }
/** Navigation that REPLACES the history entry — use after saves and on
    missing-record guards so the phone back gesture never lands on a stale
    form or bounces forever on a deleted-bird URL. */
export function navigateReplace(hash) { location.replace(hash); }

function applySettings() {
  configure({
    lang: state.settings.lang || 'ar',
    numerals: state.settings.numerals || 'western',
    dates: state.settings.dates || (state.settings.lang === 'en' ? 'gregorian' : 'both'),
  });
  document.documentElement.classList.toggle('high-contrast', !!state.settings.highContrast);
  document.title = t('app.name') + ' — ' + t('app.tagline');
}

function renderShell() {
  const app = document.getElementById('app');
  clear(app);
  const header = h('header', { class: 'app-header' },
    h('a', { class: 'brand', href: '#/birds' },
      h('span', { class: 'brand-mark' }, '🕊'),
      h('span', { class: 'brand-name' }, t('app.name'))),
    h('nav', { class: 'app-nav', role: 'navigation' },
      NAV.map(([href, key, icon]) => h('a', {
        class: 'nav-link', href, 'data-href': href,
      }, h('span', { class: 'nav-icon', 'aria-hidden': 'true' }, icon),
         h('span', { class: 'nav-label' }, t(key)))),
    ),
  );
  const banner = h('div', { id: 'banner' });
  const syncRow = h('div', { id: 'sync-row', class: 'sync-row' });
  const main = h('main', { id: 'view', class: 'app-main' });
  app.append(header, syncRow, banner, main);
  renderSyncRow();
  return main;
}

/**
 * One row, and usually nothing at all.
 *
 * Sync is infrastructure and should be almost invisible when it works (§10),
 * so the row is EMPTY in the healthy case rather than displaying a reassuring
 * tick nobody needs. It appears when there is something true to say: a cycle
 * running, work queued, no signal, or a failure that has outlived the rounds
 * which usually clear it.
 */
function renderSyncRow() {
  const el = document.getElementById('sync-row');
  if (!el) return;
  clear(el);
  const s = syncStatus();
  if (s.state === 'hidden' || s.state === 'synced') {
    el.className = 'sync-row';
    return;                       // nothing to say, so say nothing
  }
  // OFFLINE IS NOT AN ERROR and is never styled as one. It is the normal
  // condition this product was built for, and a red banner every time a
  // fancier walks into a loft would train them to ignore warnings.
  const TONE = { syncing: 'muted', pending: 'muted', offline: 'calm', off: 'muted', error: 'warn' };
  el.className = 'sync-row sync-' + s.state + ' ' + (TONE[s.state] || 'muted');
  const ICON = { syncing: '⟳', pending: '⌁', offline: '⚡', error: '⚠', off: '⏸' };
  const label = s.state === 'pending' ? t('sync.pending', { n: s.pending }) : t('sync.' + s.state);
  el.append(h('span', { class: 'sync-icon', 'aria-hidden': 'true' }, ICON[s.state] || ''),
            h('span', { class: 'sync-label' }, label));
  if (s.state === 'error') {
    el.append(h('a', { class: 'sync-details', href: '#/tools' }, t('sync.details')));
  }
}

function markActiveNav() {
  const hash = location.hash || '#/birds';
  document.querySelectorAll('.nav-link').forEach((a) => {
    const href = a.getAttribute('data-href');
    a.classList.toggle('active', hash === href ||
      (href === '#/birds' && (hash.startsWith('#/bird') || hash.startsWith('#/pedigree') || hash.startsWith('#/cert'))));
  });
}

function renderBackupBanner() {
  const el = document.getElementById('banner');
  if (!el) return;
  clear(el);
  const last = state.settings.lastExport;
  const stale = !last || (Date.now() - new Date(last).getTime()) > 30 * 24 * 3600 * 1000;
  if (stale && state.birds.size > 0) {
    el.append(h('div', { class: 'banner-warn' },
      h('span', {}, t('backup.warn30')),
      h('a', { class: 'btn btn-small', href: '#/tools' }, t('act.export'))));
  }
}

async function route() {
  const hash = location.hash || '#/birds';
  const main = document.getElementById('view');
  if (!main) return;
  markActiveNav();
  renderBackupBanner();
  runViewTeardowns();   // release object URLs/observers held by the outgoing view
  clear(main);
  document.body.classList.toggle('print-route', hash.startsWith('#/cert/'));
  for (const [re, handler] of routes) {
    const m = hash.match(re);
    if (m) {
      const node = await handler(m);
      if (node) main.append(node);
      return;
    }
  }
  navigateReplace('#/birds');
}

// --- auto-refresh on data change --------------------------------------------
// A write from outside the current view (an undo toast, a dialog on another
// screen) must show up in what the user is looking at. Three things make this
// safe rather than a source of new bugs:
//
//   1. While a DIALOG is open we defer. Re-rendering underneath an open dialog
//      is how the v1.5 "page jumps to the top" bug would come back, and the
//      user is mid-interaction anyway. The refresh runs when the last dialog
//      closes.
//   2. On a FORM route we skip entirely. Re-rendering a form would discard
//      whatever the user has typed — the form owns its own state and navigates
//      away when it saves.
//   3. Refreshes are COALESCED and preserve scroll position, so a write loop
//      (deleteBird detaching several offspring) causes one re-route, not many,
//      and the user keeps their place.
const FORM_ROUTES = /^#\/bird\/(new|[\w-]+\/edit)/;
let _refreshQueued = false;
let _refreshPending = false;

function refreshCurrentView() {
  const y = window.scrollY;
  Promise.resolve(route()).then(() => {
    requestAnimationFrame(() => {
      const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      window.scrollTo(0, Math.min(y, max));
    });
  });
}

function queueRefresh() {
  if (_refreshQueued) return;
  _refreshQueued = true;
  setTimeout(() => {
    _refreshQueued = false;
    if (isModalOpen()) { _refreshPending = true; return; }
    refreshCurrentView();
  }, 0);
}

function wireAutoRefresh() {
  onChange((ev) => {
    if (!ev) return;
    if (ev.type === 'sync-status') { renderSyncRow(); return; }
    if (ev.type === 'sync-interrupt') {
      // §11: only two things ever interrupt — a session that needs a password,
      // and a rejection that needs us. Everything else lives in الأدوات for
      // whoever is curious.
      renderSyncRow();
      toast(t(ev.key), { timeout: 10000 });
      return;
    }
    if (ev.type === 'sync-complete') {
      // Said ONCE, after the first sync on a device that had local data. Two
      // devices that never synced generated different ids for the same
      // physical bird, so both records now exist and both are valid. Only the
      // fancier can say whether two records are one bird — the duplicate
      // finder in الأدوات already groups them; this is what points at it.
      takeSyncDuplicateNotice().then((n) => {
        if (n) toast(t('sync.duplicates', { n }), { timeout: 8000 });
      });
      return;
    }
    if (ev.type === 'import') { rerender(); return; }   // structural: rebuild the shell
    if (FORM_ROUTES.test(location.hash || '')) return;   // never clobber unsaved input
    if (isModalOpen()) { _refreshPending = true; return; }
    queueRefresh();
  });
  onModalsClosed(() => {
    if (!_refreshPending) return;
    _refreshPending = false;
    if (!FORM_ROUTES.test(location.hash || '')) queueRefresh();
  });
}

export function rerender() {
  applySettings();
  renderShell();
  route();
}

// ------------------------------------------------------------------- boot

const AUTO_BACKUP_HOURS = 12;

async function boot() {
  await initDB();
  applySettings();
  renderShell();
  window.addEventListener('hashchange', route);
  wireAutoRefresh();
  await route();

  // Sync, if this device has it set up. Deliberately AFTER the first route:
  // nothing about starting the app may wait on the network, and a device with
  // no session or no configuration never reaches the loop at all.
  refreshSyncStatus().catch(() => {});
  startSyncLoop();

  // Interval auto-backup (internal snapshot; distinct from user exports).
  const last = state.settings.lastAutoBackup;
  const due = !last || (Date.now() - new Date(last).getTime()) > AUTO_BACKUP_HOURS * 3600 * 1000;
  if (due && state.birds.size > 0) {
    autoBackup().catch(() => {});
  }
  setInterval(() => {
    if (state.birds.size > 0) autoBackup().catch(() => {});
  }, AUTO_BACKUP_HOURS * 3600 * 1000);

  // Service worker — optional; the app is fully functional without it.
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    try {
      const reg = await navigator.serviceWorker.register('./sw.js');
      reg.addEventListener('updatefound', () => {
        const w = reg.installing;
        if (!w) return;
        w.addEventListener('statechange', () => {
          if (w.state === 'installed') {
            toast(navigator.serviceWorker.controller ? t('toast.updated') : t('toast.installed'));
          }
        });
      });
    } catch { /* offline-first: never block on this */ }
  }
}

boot();
