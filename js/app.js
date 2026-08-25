// app.js — boot, router, shell. Local-first: nothing here touches the network
// except the (optional) service worker registration.

import { initDB, state, setSetting, onChange, autoBackup } from './db.js';
import { configure, t, getLang, fmtDate } from './i18n.js';
import { h, clear, toast, runViewTeardowns } from './ui.js';
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
  const main = h('main', { id: 'view', class: 'app-main' });
  app.append(header, banner, main);
  return main;
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
  onChange((ev) => { if (ev && ev.type === 'import') rerender(); });
  await route();

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
