# Cutover plan — vanilla Zajil to the React port

**Status: A PLAN. Nothing in it has been executed.** Written at the end of Phase 6, when
the port passes 1747 assertions and the isolation contract has never been broken. Phase 7
is this document; Phase 8 would be carrying it out.

Every claim here is either cited to a file in this repo or marked as needing confirmation.
Where the plan recommends something, the alternatives that were rejected are named, because
a recommendation whose alternatives are invisible is just an assertion.

---

## 0. The three findings that shape everything below

These came out of writing the plan, not out of running it. Each one would have been found
in production, expensively.

### 0.1 Both service workers name the same cache — the port cannot ship as `zajil-v1.9.1`

`sw.js:4` in the vanilla tree is `const VERSION = 'zajil-v1.9.1'`, and the port composes
`'zajil-v' + next/package.json:version`, which is also `1.9.1`. The two are byte-identical
strings, so they are **the same CacheStorage key**.

That breaks the only cleanup either worker has. Both sweep on activate with
`keys.filter((k) => k.startsWith('zajil-') && k !== VERSION)` — a sweep that deletes
everything *except* the current version. With one version string:

- Deploying the port over vanilla opens the existing `zajil-v1.9.1` cache and adds 138
  entries to vanilla's 40. The sweep finds nothing to delete. Vanilla's `js/app.js`,
  `css/app.css` and the rest stay cached, served cache-first, forever.
- Rolling back does the same in reverse, and the port's 138 entries linger under a worker
  that knows nothing about them.
- Neither deploy ever evicts the other, because the signal that drives eviction is the
  version changing, and it never changes.

**The release must bump `next/package.json`'s version.** It is the only place the app
version lives (`scripts/build-sw.mjs` composes it), the About row reads it back from the
worker, and `version_display.py` proves that end to end. A bump makes both directions
clean: deploying the port deletes vanilla's cache, and rolling back deletes the port's.

> **Decision needed:** what the port's release version is. `2.0.0` is the honest answer —
> the data layer is byte-identical but every screen is new — and this plan assumes it.
> Note the root `package.json` says `1.4.1`, five releases stale; that is RF-5 and is not
> the version anything reads.

### 0.2 A configured release is currently impossible, by design, and the design is right

`next/src/sync-config.js` ships two empty constants and is **byte-identical to
`js/sync-config.js`** — `tests/sync/config_injection.py` asserts the port's copy is empty,
and the root's `tests/auth.test.js` asserts the same of vanilla's. So "fill in the
constants at release" breaks two tests and puts a live project URL in a public repository,
which SYNC-DESIGN §5a explicitly defers to the release phase for exactly that reason.

Meanwhile `guards/postbuild.mjs` fails any export that carries an endpoint or a key — and
since Phase 7 it also **deletes `out/`** when it fires, because `next build` has already
written the whole export by then and a pipeline that uploads regardless of exit code would
publish precisely what the guard exists to prevent.

So a configured release needs a deliberate mechanism that does not exist yet. §a.3
recommends one.

### 0.3 The guard that protects the release had two holes on the cutover's own path

Both are fixed, and both were found by asking what the *cutover* would do:

- The needles were the literal strings `supabase.co` and `sb_publishable_`. A project on a
  **custom domain** — which §e shows is mandatory before a Gulf pilot — or one using a
  **legacy JWT anon key** would have been configured completely and passed the scan. The
  guard now matches by shape: a Supabase host, a publishable key, a JWT, or a filled-in
  `SUPABASE_URL` / `publishableKey` constant. All four proved to fire.
- The guard failed the command but left the configured artefact on disk. It now removes it.

---

## a. What the release build is

### a.1 The base path

`basePath` comes only from `NEXT_PUBLIC_BASE_PATH` (`next.config.ts:29`) and is a
**build-time constant**: `output: 'export'` forbids the rewrites that could normalise a
prefix at request time, so one build serves exactly one prefix. The same variable is read
independently in four places that must agree — the config, `scripts/build-sw.mjs`,
`src/components/ServiceWorker.tsx` and `guards/postbuild.mjs`.

| target | `NEXT_PUBLIC_BASE_PATH` | worker scope |
|---|---|---|
| `nahdaeverything-web.github.io/Zajildb/` (today) | `/Zajildb` — case-sensitive | `/Zajildb/` |
| `zajildb.com` (apex, the plan's target) | **unset** | `/` |

**Recommendation: go straight to `zajildb.com` and never build a `/Zajildb` release of the
port.** A prefixed build is a second artefact with its own worker, its own precache list
and its own failure mode, and §0.1 shows how badly two workers on one origin interact. The
port has been proved under a prefix once (`tests/pwa/subpath_hosting.py`, 14 assertions at
`/zajil/`), so the capability is real; it just should not be what users get.

`base-path-consistent` (added at Phase 6 acceptance) makes a mismatch impossible to ship:
what was asked for, what the export carries, and what the worker baked must all agree.

### a.2 How the worker version is stamped

`next/package.json`'s `version` → `scripts/build-sw.mjs` composes `zajil-v<version>` →
`out/sw.js`. The literal exists in no source file, which is what lets `no-hardcoded-version`
and `version_display` #5 both hold. **Cutting a release is one edit, to one field, in one
file.** See §0.1 for why that edit is mandatory rather than cosmetic.

### a.3 The config injection point — RECOMMENDED, not built

The requirement: a production build must reach the production Supabase project, while the
repository stays sync-inert and the guards stay honest.

**Recommended mechanism**

1. Ship `next/public/sync-config.js` containing exactly
   `globalThis.ZAJIL_SYNC_CONFIG = { url: '', publishableKey: '' };` — empty, committed,
   and therefore still an unconfigured repository.
2. Load it from `app/layout.tsx` with `next/script`'s `beforeInteractive` strategy so it
   runs before any screen calls `syncConfig()`. `globalThis.ZAJIL_SYNC_CONFIG` already wins
   over the module constants (`src/db/sync.js:77`), so nothing in the data layer changes.
3. The **deploy pipeline** rewrites that one file with the real values *after* the guards
   have run and *before* upload.

Why this shape:

- The file is a normal public asset, so it lands in the precache list by URL. The worker
  installs with `cache: 'reload'`, fetches whatever the host is serving, and the config is
  therefore **available offline**. A config fetched at runtime instead would 404 offline and
  the app would silently report sync unconfigured after a reload.
- `src/sync-config.js` stays byte-identical to vanilla's, so both byte-identity tests keep
  passing and no live URL enters the repository.
- The guards keep their current meaning: they scan `out/` at postbuild, before the rewrite.

What it costs, stated plainly: **the guard no longer sees the artefact that is actually
published.** That has to be replaced by a check on the other side — §g makes
`live_deployment.py` the first gate after deploy, and it runs against the served origin.

**Alternatives rejected.** Filling the constants at release (breaks two tests, puts a live
URL in a public repo, and SYNC-DESIGN §5a defers it for that reason). A
`NEXT_PUBLIC_SUPABASE_*` environment variable inlined at build time (clean, but it bakes the
endpoint into 40 hashed chunks, so the guard must be taught a release mode and the release
artefact can never be diffed against a dev one). Runtime fetch of a config endpoint (breaks
offline, which is the product).

### a.4 What the pipeline must produce

`out/` is gitignored and destroyed at the start of every build (`scripts/clean-out.mjs`), so
it exists only on the machine that built it. `out/sw.js` is **not** produced by `next build`
— only by `scripts/build-sw.mjs`, from the postbuild lifecycle. `out/.nojekyll` must be
published or every `/_next/` path 404s on GitHub Pages, the atomic install rejects, and the
app has no offline mode at all.

A release therefore is, in order: bump the version → `npm run build` with the target's base
path → guards pass → rewrite `sync-config.js` → upload `out/` whole.

---

## b. The production Supabase project

Created **fresh**, from `docs/SYNC-DESIGN.md` §1's consolidated migration, which is the
complete current schema and not a base plus a patch trail. Two corrections found during
implementation are already folded into it and must not be re-derived.

### b.1 The order

1. **Create the project.** Settings that must be right at creation: *Automatically expose
   new tables* **disabled**, *Enable automatic RLS* **enabled**, public signups
   **disabled** (SPIKE §4f records the last as a required production setting).
2. **Run the consolidated migration in one go** — 13 statements: the sequence, the table,
   the `(owner, server_seq)` index, the `sync_assign_server_seq` function, the trigger, RLS
   enable, four policies, the grants, the sequence grant, and the revoke.
3. **Run the verification query** (§1, "Verification query — run after, paste the output").

### b.2 The five things most likely to go wrong

Each is invisible to the dashboard and each has already happened once:

| | What | How it presents |
|---|---|---|
| 1 | `grant usage on sequence public.sync_server_seq to authenticated` omitted | every insert 403 `42501`, the table accepts nothing, introspection all green |
| 2 | `record_id` typed as `uuid` instead of `text` | every push carrying a shipped-dataset id rejected whole, 400 `22P02`, the queue stalls permanently |
| 3 | the trigger created `AFTER INSERT`, or on insert only, or replaced by a default/identity column | an updated row keeps its original `server_seq` and is invisible to every cursor already past it |
| 4 | the `revoke truncate, trigger, references … from anon, authenticated` line omitted | Postgres grants those by default and RLS does not apply to `TRUNCATE`, so a client can empty the table despite four correct policies |
| 5 | `pg_advisory_xact_lock` dropped from the trigger body | invisible on one device; with two pushing concurrently a row can commit after a higher seq is already visible and is never delivered |

### b.3 Verification — objects, then paths

The four introspection queries prove **objects exist**: one trigger reading
`INSERT OR UPDATE`, four policies all to `{authenticated}`, grants showing exactly
`authenticated | INSERT, SELECT, UPDATE`, **no `anon` row at all**, `relrowsecurity = true`.

They do not prove a write lands, and this is not theoretical: **all four went green on a
project that accepted nothing**, because the SQL Editor runs as `postgres` and never
exercises the authenticated path. The verification query does not check the sequence grant
at all.

> **The only proof that the project works is an authenticated write from the client.**
> `next/tests/e2e/push_live.py` (24 assertions) and `pull_live.py` (12) are that proof, and
> they already exist. Run them against the production project before a single user touches
> it. `auth_live.py` (18, green against dev today) proves the sign-in path.

Note also that RLS **does not reject with a status**: a blocked write returns 200 with the
row simply absent, so the affected-row count is the only signal. A suite that checks status
codes alone would call a broken project healthy.

### b.4 Not needed at pre-pilot

No storage bucket. Blobs do not sync in v1.9 — only media metadata rows do (§7). Photos stay
on the device that took them, which §d has to account for.

---

## c. Invite-only, and the pilot account

### c.1 The posture

Accounts are created by us through the admin API; **public signups stay disabled**, which is
what makes invite-only true rather than aspirational. `POST /auth/v1/signup` must return
**422 `signup_disabled`** — that is the check, not a dashboard toggle's appearance.

The app matches the posture and is asserted to: `screens/tools.py` and `screens/sign_in.py`
both assert that no create-account control exists anywhere on the screen, in so many words,
because v1.9 shipped a card showing an email nobody could acquire.

### c.2 Creating the pilot account

```
POST {URL}/auth/v1/admin/users
  headers: { apikey: <SECRET key>, Content-Type: application/json }   ← no Authorization
  body:    { "email": "…", "password": "…", "email_confirm": true }
```

`email_confirm: true` is not optional — without it the password grant fails with
*email not confirmed* and the account looks broken. The secret key is used **here and
nowhere else**, from a terminal, never from anything the app bundles or serves.

### c.3 The early-access form

`/sign-in` has one, and its submit is **deliberately unwired** — it collects the fields,
shows the success pane, and sends nothing, with the payload named in a comment. It is a
design placeholder until there is somewhere to send it. Before launch, either wire it to a
real destination or the pane is a promise the app does not keep.

---

## d. The data path for existing users

### d.1 The problem, stated exactly

IndexedDB is **per-origin**. Records made at `nahdaeverything-web.github.io` are not
readable from `zajildb.com`, by any means, from inside the browser. There is no migration
API, no shared storage, and no way for the new origin to ask the old one for anything.

**If the domain simply changes and nothing is said, a returning fancier opens `zajildb.com`
and sees an empty loft with a first-run screen.** Their records are not lost — they are at
the old origin, reachable by typing the old URL — but nothing on the new screen says so, and
"the app deleted my birds" is what it will look like.

### d.2 The options

| | Option | What it carries | What it costs |
|---|---|---|---|
| 1 | **Do nothing** | nothing | the failure above |
| 2 | **Export / import**, through the tools card that already exists | every record, **and the photos** (the export embeds media as data URLs) | one deliberate action per person, on each old device |
| 3 | **Sync through the account** — sign in on the old origin, push; sign in on the new, pull | every record; **photos do NOT travel** (metadata syncs, blobs do not) | needs the production project live first, and it strands photos |
| 4 | **Keep the old origin serving** as a bridge for a stated period | — | the old origin keeps its own service worker and its own cache; two live deployments to reason about |

### d.3 Recommendation

**Option 2 as the primary, option 4 as the safety net, option 3 never relied on for this.**

1. Before the domain moves, the old origin gets one release whose only change is a notice:
   the app is moving, export your data here, and a link. (This is a vanilla change on
   `main`, and therefore outside the port's isolation contract — it needs its own decision.)
2. Each fancier exports once from the old origin. The file carries records *and* photos.
3. On `zajildb.com` they import it. `screens/tools.py` proves the round trip, including that
   merge does not duplicate and that a replace-import asks first.
4. The old origin keeps serving for a stated window — a month is a reasonable opening
   proposal — so anyone who arrives late still has their data.

Option 3 is the wrong tool here precisely because of §7: sync moves metadata and not blobs,
so a fancier who "migrated by syncing" would find every photo missing on the new device and
nothing would say why. Sync is for keeping devices level, not for moving house.

> **This is the section most likely to be wrong in a way that matters**, because it depends
> on how many people already have data at the old origin and how reachable they are. That
> number is not in this repo. If it is "Samir and two pilot users", most of this collapses
> into three export files and a WhatsApp message.

---

## e. Domain wiring

### e.1 `zajildb.com` to the deploy

For an apex domain on GitHub Pages: four **A** records to `185.199.108.153`,
`185.199.109.153`, `185.199.110.153`, `185.199.111.153` (or the four **AAAA** records, or an
ALIAS/ANAME to `nahdaeverything-web.github.io`), plus a `CNAME` record for `www` if wanted.
Setting the custom domain in repository settings writes a `CNAME` file into the repo root.

**HTTPS can take up to 24 hours to become available**, and *Enforce HTTPS* is a manual
setting afterwards. The service worker will not register at all without it
(`location.protocol` gate), so **the app has no offline mode until HTTPS is live** — which
makes this the step that must happen first and be waited out, not squeezed in on the day.

GitHub's own warning is worth carrying: a Pages site that is disabled while a custom domain
is still configured is exposed to a domain takeover. If the custom domain is ever removed,
remove it in settings and in DNS together.

### e.2 The Supabase API domain

`*.supabase.co` **was regionally blocked in the UAE during 2025**, and Zajil's audience is
Jordan and the Gulf. That makes a custom API domain a distribution requirement, not a
nicety — and it should be settled before users depend on it, not during an outage.

What it takes: a **CNAME** from the chosen host (say `api.zajildb.com`) to the project's
`*.supabase.co` domain, plus a **TXT** record at `_acme-challenge.api.zajildb.com` for
certificate issuance. It is a **paid add-on on a paid plan** and activation takes up to
about 30 minutes.

Three properties make this far less dangerous than it sounds, and all three should be
verified rather than assumed:

1. **The original `*.supabase.co` host keeps working** after activation. Both names resolve,
   so this is additive, not a switch.
2. **The client never stores the endpoint.** `syncConfig()` resolves it from the build every
   time (`src/db/sync.js:76-81`); only tokens live in `settings`. So changing the hostname is
   a redeploy, and older builds keep working against the old name.
3. Tokens are JWTs from the same project, so a hostname change does not invalidate a session.

The **vanity subdomain** feature does not help here: it is still on `supabase.co` and would
be blocked by exactly the same rule. It is a branding feature, not a distribution one.

---

## f. Rollback

### f.1 What makes it work at all

A service worker is replaced by serving a different file at the same URL and scope. Both
apps register at the deployment root — vanilla `./sw.js` from its single document, the port
`${BASE}/sw.js` with an explicit scope — so **redeploying the vanilla tree over the same
origin replaces the worker**, and the browser picks it up on the next navigation because
both use `skipWaiting()` and `clients.claim()`.

**Rollback is a redeploy to the same origin. It is not a DNS change.** Pointing DNS back at
the old host is slower (propagation, plus the old origin's own worker), leaves the port's
worker installed at `zajildb.com` for anyone who returns, and does nothing for a user whose
browser is already serving the port from cache.

### f.2 The timing, honestly

| | |
|---|---|
| upload of the vanilla tree | as fast as the host publishes; GitHub Pages is typically a minute or two |
| a visitor already on the page | sees nothing change until a navigation or reload |
| first reload | fetches the new `sw.js`, installs, activates, claims — and the page they are looking at was already served from the old worker |
| second reload | the vanilla app |
| a visitor who never reloads | keeps the port indefinitely; a cache-first worker has no expiry |

Two reloads is the honest number, and it is the same "double-reload dance" HANDOFF already
records for ordinary updates.

### f.3 What would strand a user

**The version collision of §0.1 is the thing that turns a rollback from awkward into
broken.** If both trees ship `zajil-v1.9.1`, the returning vanilla worker adds its 40
entries to a cache that still holds the port's 138 and deletes nothing, and the two apps'
files coexist under one cache-first worker for good. Bumping the port's version to `2.0.0`
makes the rollback clean: vanilla's `zajil-v1.9.1` is a different key, its sweep deletes
`zajil-v2.0.0`, and the port's files are gone.

### f.4 What it proves

`tests/e2e/live_deployment.py` run against the rolled-back origin: the six nav links, no
failed requests, a worker scoped correctly, a versioned cache, an installable manifest, the
38-bird example, offline boot, offline data, offline COI, zero page errors. Eleven
assertions that say "the app a user opens works", which is the question a rollback asks.

---

## g. The order of operations

Nothing in stages 1–4 touches a user. The first irreversible step is stage 6.

| # | Step | Gate before moving on |
|---|---|---|
| 1 | Bump `next/package.json` to the release version | `version_display.py`; the About row reports the new string |
| 2 | Build the config injection mechanism (§a.3) and its guard consequences | the full gate green; `config_injection.py` still proves the repo unconfigured |
| 3 | Create the production Supabase project: settings, the consolidated migration, the verification query | the four queries, **then** `push_live.py` + `pull_live.py` + `auth_live.py` against it — objects, then paths |
| 4 | Create the pilot account through the admin API; confirm `POST /auth/v1/signup` → 422 | `auth_live.py` signs in, refreshes and signs out against production |
| 5 | Point `api.zajildb.com` at the project; wait for the certificate | the same three live suites, re-run against the custom host |
| 6 | Point `zajildb.com` at the deploy; wait out HTTPS (up to 24h); enable Enforce HTTPS | the origin serves over HTTPS and a worker can register at all |
| 7 | **Deploy the port** to `zajildb.com`, configured, base path empty | **`live_deployment.py` — the first gate** |
| 8 | A real push and pull from a real device on the live origin | **`push_live.py` / `pull_live.py` against production — the second gate** |
| 9 | The old origin gets its migration notice; the export/import path is walked once end to end by a person | a file exported at the old origin imports at the new one with its photos |
| 10 | Samir's own loft moves | §h |

Stage 6 is the one that cannot be undone in ten minutes: DNS propagates, and an HTTPS
certificate takes up to a day. Everything before it is rehearsal and everything after it is
a redeploy.

---

## h. What must be true before Samir's own loft moves

This is the last gate, and it is deliberately strict, because his loft is the only copy of
data that matters and he is the person who cannot be told "restore from your export".

1. **`live_deployment.py` is green against `zajildb.com`** — all eleven, including the three
   offline ones.
2. **`push_live.py` and `pull_live.py` are green against the production project**, reached
   through `api.zajildb.com`, not through `*.supabase.co`.
3. **Two devices have converged for real**: a bird created on one appears on the other, an
   edit on the second wins, and a delete on either sticks. `convergence.py` proves the
   design; this proves the deployment.
4. **A full export has been taken from the old origin and imported into the new one**, by
   hand, with the photos checked — the same path §d asks of everyone else.
5. **That export is kept somewhere off both origins** until step 3 has held for a week.
6. **The rollback has been rehearsed once**, on a throwaway origin or a branch deploy: the
   vanilla tree redeployed over a port install, two reloads, `live_deployment.py` green.
   A rollback plan that has never been run is a hope.
7. **The version bump is in the shipped worker** — the About row on the live site reports
   the release version, not `1.9.1`. §0.1 is the whole reason.
8. **Public signups are still refused** on the production project — re-checked after all the
   domain work, because it is the one setting that would be quietly catastrophic.

---

## Appendix — the sixteen presentation differences, with a recommendation for each

Phase 6's fidelity pass left these needing a design ruling. They are grouped by what the
ruling actually is; none is a correctness defect, and none blocks a cutover.

**Carry the spec (cheap, and the spec is right)** — recommend doing these before launch:

| | Difference | Why |
|---|---|---|
| 1 | FCI rule line: the spec emphasises **20** and **150** | one `<strong>`; the numbers are the content of the sentence |
| 2 | Loft home: emphasised numerals in the count line | same, and the spec gives it a size and weight |
| 3 | Loft home: the search magnifier | the field reads as a box with no affordance without it; the CSS is already there and dead |
| 4 | Loft home: the desktop add button's plus icon | the FAB has the identical icon; the desktop button looks unfinished beside it |
| 5 | Loft home: the filter-group divider | the status pills and the year pills run together as one undifferentiated row |
| 6 | Certificate panel: the placeholder glyphs in the empty photo thumbs | an empty dashed box says less than a camera |
| 7 | Breeding: the new-pair sheet scrolls back to the top when a save is refused | the error list is above the fold the fancier is looking at; the spec does it explicitly |

**Follow the data, and correct the spec** — recommend ruling the spec wrong, as with «نشط»:

| | Difference | Why |
|---|---|---|
| 8 | The «نشط» chip on the form and the profile hero | **already ruled** at Phase 6 acceptance; the kit is corrected and SF-2 records it. Listed for completeness |
| 9 | The form's field-level error state | a dead branch: both duplicate-ring keys are **warnings**, never errors, so no input can ever carry the red border. Either remove the CSS or give it a real trigger; recommend removing |
| 10 | Sign-in: the early-access mail fallback | unreachable, because the form's own required fields prevent an empty submit. Dead code; recommend removing |
| 11 | Loft home: the ring plate's gold year cell | always empty on real data — the spec's plate splits a ring shape the app does not produce. Recommend dropping the cell rather than faking a year |

**Genuine design questions** — recommend a decision, not a default:

| | Difference | The question |
|---|---|---|
| 12 | The per-record document title («زاجل — ملف الطائر · برق») | the port sets one static title for every route. Per-record titles are what make browser history and shared links legible; recommend adopting, but it is new behaviour |
| 13 | The gallery photo tile as an interactive control | the spec draws a button with a hover state; the port renders a static tile. What should tapping a photo do? There is no lightbox in the port and none in vanilla |
| 14 | The health banner's dose-line order | the spec reads «آخر جرعة … · يُستحق …»; the port renders the same facts in the other order. Recommend the spec's, it reads as a sentence |
| 15 | The health banner's gold `.next.due` state | the spec designs the ground and never says what triggers it. Recommend: due within 30 days |
| 16 | FCI table: the qualified row tint and the ✗ chip | the table keys the tint on the count **and** an FCI ring; the phone card keys it on the count alone, as the engine does. They disagree with each other, which is the real defect — recommend the card's rule for both |

The certificate's print-chrome state is deliberately omitted from this list: it was fixed at
Phase 6 once the nav's print rule landed.
