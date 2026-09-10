// sync-config.js — where this build points its sync at.
//
// DELIBERATELY EMPTY. Sync is inert until these are filled in, and every
// existing feature works exactly as before while they are blank — that is the
// offline-first rule (SYNC-DESIGN §5) holding at the level of configuration,
// not just at the level of the network.
//
// The publishable key is SAFE to ship in client code: that is what it is for.
// It grants nothing on its own — the server denies `anon` outright, row-level
// security scopes every row to its owner, and public signups are disabled
// (SPIKE §4f). The SECRET key never appears in this file, in this repo, or in
// any client build. If one ever does, it is a leak, not a configuration.
//
// The values are absent here because the design does not yet say which project
// a release points at, and writing a live project URL into a public repository
// is a decision that belongs to the release phase rather than to a refactor.
//
// Two ways to supply them without editing this file:
//   • `globalThis.ZAJIL_SYNC_CONFIG = { url, publishableKey }` before the app
//     loads — how the test suites inject a stub endpoint, and how a self-hosted
//     deployment can point at its own project.
//   • fill these constants in at release time.

export const SUPABASE_URL = '';
export const SUPABASE_PUBLISHABLE_KEY = '';
