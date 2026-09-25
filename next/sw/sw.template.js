// sw.template.js — the source of the port's service worker.
//
// This file is a TEMPLATE, not the shipped worker. `scripts/build-sw.mjs` reads it after
// the export finishes, fills the two placeholders from the real build output, and writes
// out/sw.js. Two reasons it cannot be shipped as-is from public/:
//
//   · the precache list cannot be written by hand. Vanilla's SHELL is 43 plain paths
//     (sw.js:6-47) because nothing in that tree is hashed. This export's chunk names are
//     bare 13-character content hashes that change every build, plus a per-build id
//     directory, plus one RSC payload per route — so the list has to be generated from
//     the finished export or it is wrong the moment anything changes.
//   · the version literal. version_display #5 greps the worker's source for a top-level
//     VERSION constant, and the no-hardcoded-version guard forbids that literal anywhere
//     in next/ source. Both hold at once only if the worker is a build product: the guard
//     skips out/, the version comes from package.json, and no source file carries it.
//     Nothing in this file's prose may spell that assignment out, or the grep matches the
//     comment instead of the constant — which is exactly what happened the first time.
//
// THE STRATEGY IS VANILLA'S, carried rule for rule from sw.js:
//   · cache-first, ignoreSearch, never blocking on the network;
//   · non-GET and cross-origin requests are not answered at all, so Supabase sync
//     traffic passes through untouched;
//   · install is one atomic addAll of Requests with cache:'reload', then skipWaiting;
//   · activate deletes only keys starting with the app's own prefix, then clients.claim;
//   · one message type in, one shape out: GET_VERSION -> {type:'VERSION', version}.
//
// THREE DEPARTURES, each forced by the export's shape and each recorded in README.md:
//   1. The navigation fallback. Vanilla answers every navigation miss with the one
//      cached './index.html' because it is a single-document hash-routed SPA. This export
//      has 16 documents and index.html is a client-side redirect to /birds, so answering
//      a /tools navigation with index.html would land the fancier somewhere else. The
//      navigation branch therefore resolves the request's own document first — the flat
//      export means /tools is the file tools.html — and only falls back to index.html for
//      a path it has never heard of.
//   2. A network failure returns a 504 Response instead of rejecting. A rejected
//      respondWith surfaces as a request error in the page, and both intent suites assert
//      ZERO page errors across their offline sections. Vanilla has the same hole and gets
//      away with it because it precaches everything it ever asks for; so does this, but a
//      worker that can only fail loudly is not worth the risk.
//   3. Install is split into a CRITICAL list and a best-effort tail. Vanilla's addAll is
//      one atomic call over 41 hand-checked paths; this list is 131 build-named ones, of
//      which about 60 are RSC payloads that only affect client-side navigation. Keeping
//      the whole thing atomic means one 404 on one payload costs the app its entire
//      offline mode — and on GitHub Pages that is not hypothetical, since every /_next/
//      path needs .nojekyll to be served at all. So the documents, chunks, stylesheets,
//      fonts, datasets, manifest and icons install atomically, exactly as vanilla does,
//      and the payloads are added one by one with their failures reported rather than
//      fatal. A shell that must work still must; a payload that cannot be had degrades
//      one navigation instead of everything.

const VERSION = '__VERSION__';
const PREFIX = 'zajil-';

// The prefix the SHELL below was GENERATED with. Every entry is qualified with it, so a
// build deployed under a different prefix would 404 all of them, install would reject, and
// the app would report a registered worker with no cache at all — indistinguishable from
// "not activated yet". Baked here so the worker can say so instead.
const BUILT_FOR = '__BASE__';

// generated from the finished export by scripts/build-sw.mjs
const SHELL = __SHELL__;

// what this worker actually controls, e.g. '/' or '/zajil/'
const SCOPE = new URL(self.registration ? self.registration.scope : './', self.location.href).pathname;

// Documents, code, type and data — the shell that must work or there is no offline mode.
// The rest (RSC navigation payloads) is best-effort; see departure 3.
const CRITICAL = new RegExp(
  '(/$|\\.html$|\\.css$|\\.js$|\\.woff2?$|\\.json$|\\.webmanifest$|\\.png$|\\.ico$|\\.svg$)');

// `cache: 'reload'` bypasses the browser HTTP cache: hosts such as GitHub Pages send
// max-age, so a plain addAll can bake stale copies of the PREVIOUS deploy into the new
// version cache — permanently, since a version cache is only ever written once.
const fresh = (u) => new Request(u, { cache: 'reload' });

async function precache() {
  if (SCOPE !== BUILT_FOR) {
    // Say it once, loudly. Every SHELL entry is qualified with BUILT_FOR, so none of them
    // can be fetched from here and there is nothing this worker can usefully cache.
    console.error(`[zajil] this service worker was built for ${BUILT_FOR} but is installed `
      + `at ${SCOPE}; its precache list cannot be fetched. Rebuild with `
      + `NEXT_PUBLIC_BASE_PATH set to the path it is deployed under.`);
    return;
  }
  const c = await caches.open(VERSION);
  const critical = SHELL.filter((u) => CRITICAL.test(u));
  const optional = SHELL.filter((u) => !CRITICAL.test(u));
  // atomic, as vanilla is: if the shell cannot be had, there is no offline mode to report
  await c.addAll(critical.map(fresh));
  // best-effort: one missing navigation payload costs one navigation, not everything
  const missed = [];
  await Promise.all(optional.map((u) => c.add(fresh(u)).catch(() => missed.push(u))));
  if (missed.length) console.warn(`[zajil] ${missed.length} of ${optional.length} navigation `
    + `payloads could not be precached; those routes will need the network once.`, missed.slice(0, 5));
}

self.addEventListener('install', (e) => {
  e.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      // CacheStorage is per-ORIGIN, not per-scope: on <user>.github.io every project site
      // shares it. Only ever delete our own caches, or we wipe the offline data of sibling
      // apps on the same account.
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith(PREFIX) && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// The page asks the CONTROLLING worker what it is, so the About row reports what is
// actually installed rather than a constant compiled into the bundle — those two disagree
// exactly when it matters, i.e. when an update has not activated yet. Replies down the
// MessageChannel port when given one, otherwise to the requesting client.
self.addEventListener('message', (e) => {
  if (!e.data || e.data.type !== 'GET_VERSION') return;
  const reply = { type: 'VERSION', version: VERSION };
  if (e.ports && e.ports[0]) e.ports[0].postMessage(reply);
  else if (e.source && e.source.postMessage) e.source.postMessage(reply);
});

/**
 * [departure 1] Which document answers this navigation.
 *
 * The export is flat and trailingSlash-false: the route /tools is the file tools.html, and
 * /tools/ holds only RSC payloads. A host with clean URLs asks for /tools; a plain file
 * server asks for /tools.html. Both must find the same cached document, and a record view
 * carries its id in the query (/bird?id=…), which is not part of the document's identity.
 */
function documentCandidates(url) {
  const path = url.pathname;
  // `path` itself is not a candidate: the read above already tried the request, and with
  // ignoreSearch that is the same lookup
  const out = [];
  if (!/\.[a-z0-9]+$/i.test(path)) {
    // BOTH export shapes, because a worker outlives the config that built it. `trailingSlash:
    // true` (RULED 2026-09-25) writes stats/index.html; before it, stats.html. The directory
    // index is tried FIRST because it is what this build produces.
    //
    // The bare, slash-less form is the one that matters here. ONLINE the host redirects
    // /stats to /stats/ and the question never arises; OFFLINE there is no host, so a
    // bookmark, a typed URL or a link someone trimmed the slash off is answered by this
    // worker alone — and without this candidate it fell through to SCOPE + index.html and
    // rendered the SHELL, which redirects to /birds. The user asks for stats offline and
    // silently gets the loft: a wrong document, not an error. Caught by the gate, not by
    // reading.
    out.push(path.replace(/\/$/, '') + '/index.html');
    out.push(path.replace(/\/$/, '') + '.html');
    if (path.endsWith('/')) out.push(path + 'index.html');
  }
  out.push(SCOPE + 'index.html');
  return out;
}

// ignoreSearch because a record view carries its id in the query and the export's own
// asset links carry a hash there; ignoreVary because a host that sends Vary on a precached
// response would otherwise turn every cache-first hit into a miss and take offline with it.
const MATCH = { ignoreSearch: true, ignoreVary: true };

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    // read from OUR cache only, for the same origin-sharing reason
    caches.open(VERSION).then(async (c) => {
      const hit = await c.match(e.request, MATCH);
      if (hit) return hit;

      if (e.request.mode === 'navigate') {
        for (const candidate of documentCandidates(url)) {
          const doc = await c.match(candidate, MATCH);
          if (doc) return doc;
        }
      }

      // everything else tries the network and back-fills the cache for next time
      try {
        const res = await fetch(e.request);
        if (res.ok) c.put(e.request, res.clone());
        return res;
      } catch {
        // [departure 2] answer, do not reject: a rejected respondWith is a page error, and
        // being offline is the condition this app is built for, not a fault
        return new Response('', { status: 504, statusText: 'Offline' });
      }
    }),
  );
});
