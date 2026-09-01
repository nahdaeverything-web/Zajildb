// sw.js — service worker: precache the entire app shell so Zajil launches
// and works fully offline. Cache-first; the app never blocks on the network.

const VERSION = 'zajil-v1.9.1';

const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './css/app.css',
  './js/app.js',
  './js/db.js',
  './js/db/storage.js',
  './js/db/oplog.js',
  './js/db/records.js',
  './js/db/io.js',
  './js/db/sync.js',
  './js/dates.js',
  './js/sync-config.js',
  './js/i18n.js',
  './js/ui.js',
  './js/engine/pedigree.js',
  './js/engine/coi.js',
  './js/engine/integrity.js',
  './js/engine/relationship.js',
  './js/engine/rings.js',
  './js/engine/fci.js',
  './js/engine/velocity.js',
  './js/engine/validate.js',
  './js/views/birds.js',
  './js/views/bird-form.js',
  './js/views/bird-detail.js',
  './js/views/pedigree.js',
  './js/views/breeding.js',
  './js/views/races.js',
  './js/views/health.js',
  './js/views/stats.js',
  './js/views/tools.js',
  './js/views/cert.js',
  './tests/harness.js',
  './tests/engine.test.js',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png',
  './sample-data.json',
  './example-loft-large.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    // `cache: 'reload'` bypasses the browser HTTP cache: hosts such as GitHub
    // Pages send max-age, so a plain addAll can bake stale copies of the
    // PREVIOUS deploy into the new version cache — permanently, since a
    // version cache is only ever written once.
    caches.open(VERSION)
      .then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      // CacheStorage is per-ORIGIN, not per-scope: on <user>.github.io every
      // project site shares it. Only ever delete our own caches, or we wipe
      // the offline data of sibling apps on the same account.
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith('zajil-') && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// The page asks the CONTROLLING worker what it is, so the About row reports
// what is actually installed rather than a constant compiled into js/ — those
// two disagree exactly when it matters, i.e. when an update has not activated
// yet. Replies down the MessageChannel port when given one, otherwise to the
// requesting client.
self.addEventListener('message', (e) => {
  if (!e.data || e.data.type !== 'GET_VERSION') return;
  const reply = { type: 'VERSION', version: VERSION };
  if (e.ports && e.ports[0]) e.ports[0].postMessage(reply);
  else if (e.source && e.source.postMessage) e.source.postMessage(reply);
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    // read from OUR cache only, for the same origin-sharing reason
    caches.open(VERSION).then((c) => c.match(e.request, { ignoreSearch: true })).then((hit) => {
      if (hit) return hit;
      // Navigations fall back to the shell (SPA); everything else tries the
      // network and back-fills the cache for next time.
      if (e.request.mode === 'navigate') {
        return caches.open(VERSION).then((c) => c.match('./index.html'))
          .then((shell) => shell || fetch(e.request));
      }
      return fetch(e.request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(e.request, copy));
        }
        return res;
      });
    }),
  );
});
