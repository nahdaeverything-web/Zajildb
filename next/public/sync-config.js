// THE CONFIG INJECTION POINT — CUTOVER.md §a.3, RULED 2026-09-25.
//
// COMMITTED EMPTY, ON PURPOSE. This repository is sync-inert: no project URL, no key of any
// kind, nothing for the no-sync-config-in-build guard to find. A deploy pipeline rewrites
// this ONE file with the real values AFTER the guards have run and BEFORE upload
// (scripts/inject-config.mjs). Nothing else in the tree changes between a dev build and a
// release, which is the property this shape exists to buy: the release artefact stays
// diffable against a dev one.
//
// Why a public asset and not a build-time constant:
//   · It lands in the precache list by URL like any other file in public/, so the worker
//     installs it with cache:'reload' and the config is AVAILABLE OFFLINE. A config fetched
//     at runtime would 404 offline and the app would quietly report sync unconfigured after
//     a reload — which breaks the product, not just the feature.
//   · src/sync-config.js stays byte-identical to js/sync-config.js, so both byte-identity
//     tests keep passing and no live URL ever enters the repository.
//   · A NEXT_PUBLIC_* environment variable would be inlined by Next into ~40 hashed chunks.
//     The guard would then need a release mode, and a release build could never be diffed
//     against a dev one. That alternative was considered and REJECTED (§a.3).
//
// Loaded from app/layout.tsx with next/script's beforeInteractive strategy, so it is in the
// initial HTML and runs before any Next module — therefore before any screen can call
// syncConfig(). globalThis.ZAJIL_SYNC_CONFIG already wins over the module constants
// (src/db/sync.js:77), so the data layer needs no change at all.
//
// THE SECRET KEY NEVER APPEARS HERE. The publishable key is designed to be public: it grants
// nothing on its own, the server denies `anon` outright, row-level security scopes every row
// to its owner, and public signups are disabled. A secret key in this file would be a leak,
// not a configuration, and guards/run.mjs no-secret-key fails the build on its shape.
//
// `|| globalThis.ZAJIL_SYNC_CONFIG` is not a nicety — it is what keeps this file from
// breaking every sync suite in the tree. Those inject a stub endpoint with Playwright's
// add_init_script, which runs BEFORE page scripts; a bare assignment here would run after it
// and silently overwrite the stub with blanks. So this file supplies a DEFAULT and an
// explicitly pre-set config always wins, which is also exactly what src/db/sync.js:69-71
// already promises: "a test can point at a stub and a self-hosted deployment can point at
// its own project without a rebuild".
globalThis.ZAJIL_SYNC_CONFIG = globalThis.ZAJIL_SYNC_CONFIG || { url: '', publishableKey: '' };
