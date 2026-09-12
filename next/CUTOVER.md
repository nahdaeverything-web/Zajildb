# Cutover plan — vanilla Zajil to the React port

**Status: A PLAN. Nothing in it has been executed.** Written at the end of Phase 6, when
the port passes 1747 assertions and the isolation contract has never been broken. Phase 7
is this document; Phase 8 would be carrying it out.

Every claim here is either cited to a file in this repo or marked as needing confirmation.
Where the plan recommends something, the alternatives that were rejected are named, because
a recommendation whose alternatives are invisible is just an assertion.

A first draft was then checked by six independent researchers — provisioning, the release
build, the invite posture, the data path, the rollback, the domain — with instructions to
verify the draft rather than restate it. They corrected it in six places, and every
correction is folded in and marked: §0.4 (the first gate does not exist in a form that can
gate the port), §c (one assertion credited to the wrong file), §d.2 (three costs of the
recommended path), §e.1a (which repository the domain points at), §e.1 (HTTPS takes about an
hour, not a day) and §f.3 (a rollback strand the version bump does not fix).

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

### 0.4 `live_deployment.py` cannot gate the port. It is a vanilla detector.

Phase 6 acceptance ruled its 11 assertions "the first gate of the cutover". Reading it for
this plan shows that the suite **as it exists cannot be that gate**, for three reasons:

1. **There is no port copy.** It exists only at `tests/e2e/live_deployment.py` in the
   vanilla tree; `next/tests/` has no such file.
2. **Every DOM token it uses is vanilla-only.** `.nav-link` (the port renders
   `data-testid="nav-link"` with hashed CSS-module classes), `.empty-state button`,
   `.bird-row`, `.coi-headline .coi-badge`, and a **hash route** `#/pedigree/<id>` that a
   path-routed static export cannot serve. `tests/pwa/subpath_hosting.py:15-23` already
   documents those five substitutions as what porting the root suite required.
3. **The URL and scope are hard-coded** — `URL='https://nahdaeverything-web.github.io/Zajildb/'`
   and `sw.scope.endswith('/Zajildb/')`. `run_all.py:9` documents a `ZAJIL_LIVE_URL`
   env var; **nothing reads it**, and the suite's `import os` is unused. Against an apex
   deploy it fails at the scope assertion for a reason that has nothing to do with the app.

There is a real gift inside that: green against a rolled-back origin, **it proves what the
browser got is vanilla and not the port** — which is exactly the question a rollback asks.
So the suite splits in two, and §g orders both:

- the **vanilla original**, URL-parameterised, becomes the rollback verifier;
- a **ported copy** under `next/tests/e2e/` becomes the deploy gate.

Four things neither copy proves, all load-bearing: it opens a **fresh browser profile**, so
the entire hard case — an old worker already installed, cache-first, two reloads — is
invisible to it; its cache assertion is `any('zajil-' in c)`, which the §0.1 collision
passes; it only ever walks the **root path**, never `/birds`, `/tools` or `/bird/edit`,
which are where §f strands people; and it uses `wait_until='networkidle'`, which HANDOFF
records as hanging under a service worker.

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

This is not merely a preference: **a GitHub Pages project site with a custom domain is
served at the domain root, and the `/Zajildb/` prefix ceases to exist.** With a custom
domain the base path *must* be empty. So the apex move and the prefix removal are the same
decision, not two.

Note also what the Pages source is today: the `Zajildb` repo serves the **vanilla** app from
the root of its source branch. Pointing `zajildb.com` at that repo as it stands publishes
vanilla at the apex. §e recommends the repo layout that follows from this.

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

**Allow anonymous sign-ins is a separate toggle and must also be off.** Disabling signups
does not disable it; it is an independent option (`external_anonymous_users_enabled`), and
leaving it on means the invite-only posture has a second door. Keep the **Email** provider
enabled — the client only ever calls `grant_type=password` and `grant_type=refresh_token` —
and every OAuth and phone provider off, since nothing in the client can initiate them.

The app matches the posture and is asserted to: **both** "no way to create an account"
assertions live in `screens/tools.py` (an earlier draft of this plan credited one of them to
`screens/sign_in.py`; that file contains no such assertion). They exist because v1.9 shipped
a card showing an email nobody could acquire.

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
"the app deleted my birds" is what it will look like. Worse, the first-run body text reads
«كل ما تسجّله يُحفظ على جهازك ويُزامَن حين يتوفر اتصال» — the wrong reassurance at exactly
that moment — and if the build is still sync-inert the tools card shows «غير مهيأة» with
deliberately no sign-in button, so there is no affordance on the screen that leads anywhere.
The app genuinely cannot tell this from a fresh install; no code path in either tree can
inspect another origin, and none can exist.

**The origin is the host, not the path.** Today's origin is
`https://nahdaeverything-web.github.io` *entire* — `/Zajildb/` is not part of it. Two
consequences, and the second is the useful one:

- the `zajil` database is already shared with anything else published under that account;
- **any page at any path on that host can read it.** A rescue/export page served from a
  different repo under the same account reaches the same records. That is what makes the
  bridge in d.3 buildable even after `/Zajildb/` itself stops being served.

### d.2 What an export does and does not carry

Verified against `src/db/io.js`. **Carried:** all five data stores whole, **the photos**
(each media row re-emitted with a base64 `dataURL`), tombstones so deletions survive, and
per-record provenance. **Not carried: `settings` — no key at all.** Language, numerals,
COI depth, high contrast, date mode, loft coordinates, device name, sync cursors: none of
it travels, and the person re-picks them on the far side. That is also *why* no auth token
can leak into an export, so it is a deliberate property and not an oversight — but it must
be said out loud to anyone migrating, or the new install will feel subtly wrong.

Two costs of the recommended path, both real:

- **The export button has no busy state and no chunking.** It builds the whole loft,
  every photo base64-expanded ~1.33× and pretty-printed, as one string on the main thread.
  BACKLOG measured this shape at ~400 MB of blob reads and ~530 MB of transient strings for
  200 photos at 2 MB. `autoBackup` was fixed by skipping media; **the user-facing export was
  not**, and this is the one moment it matters. A large loft on a phone may stall or fail.
- **The port does not render the export-freshness nudge.** The string `backup.warn30`
  («مرّ أكثر من ٣٠ يومًا على آخر تصدير») exists in the port's dictionary but **no component
  renders it**; vanilla banners it on every route. The one in-app prompt that puts an export
  in a user's hands lives only on the app being retired.
- **The migration path itself is proven nowhere.** `tools.py` proves a merge round trip into
  a database that already holds the same records — so `importAll` skips every media row —
  and the foreign-loft case deliberately strips media. **A full export with real photo bytes
  imported into a completely empty database has never been run.** That is a test to write
  before anyone is asked to do it, not a step to discover during the cutover.

### d.3 The options

| | Option | What it carries | What it costs |
|---|---|---|---|
| 1 | **Do nothing** | nothing | the failure above |
| 2 | **Export / import**, through the tools card that already exists | every record, **and the photos** (the export embeds media as data URLs) | one deliberate action per person, on each old device |
| 3 | **Sync through the account** — sign in on the old origin, push; sign in on the new, pull | every record; **photos do NOT travel** (metadata syncs, blobs do not) | needs the production project live first, and it strands photos |
| 4 | **Keep the old origin serving** as a bridge for a stated period | — | the old origin keeps its own service worker and its own cache; two live deployments to reason about |

### d.4 Recommendation

**Option 2 as the primary, option 4 as the safety net, option 3 never relied on for this.**

1. Before the domain moves, the old origin gets one release whose only change is a notice:
   the app is moving, export your data here, and a link. (This is a vanilla change on
   `main`, and therefore outside the port's isolation contract — it needs its own decision.)
2. Each fancier exports once from the old origin. The file carries records *and* photos.
3. On `zajildb.com` they import it. `screens/tools.py` proves the round trip, including that
   merge does not duplicate and that a replace-import asks first — but see d.2: the
   empty-target case it does *not* prove is exactly this one, so write that test first.
4. The old origin keeps serving for a stated window — a month is a reasonable opening
   proposal — so anyone who arrives late still has their data.

**Two things make the ordering of step 1 non-negotiable.**

- The old origin's worker is **cache-first with no revalidation**, and navigations are
  answered from the cached `index.html` before the network is consulted. A notice deployed
  there reaches a returning user only on their *second* load, and never at all if they never
  reload. So the notice must ship early and stand for a while — it cannot be a
  cutover-morning action.
- That same cache is why the old app keeps working perfectly for installed users after the
  move, which cuts both ways: it is the only remaining route to their data, **and** the
  mechanism by which someone goes on entering new records into the dead origin for weeks.
  Every day between the notice and the shutdown widens that split.

Option 3 is the wrong tool here twice over. First by design — sync moves media *metadata*
and not blobs, so a fancier who "migrated by syncing" would find every photo replaced by
«الصورة على جهاز آخر» and nothing would say why. Second by fact: **no existing user has ever
synced.** The shipped build is sync-inert, accounts are invite-only, and the server holds
zero rows of anyone's loft, so "sign in and pull" repopulates nothing. Sync is for keeping
devices level, not for moving house.

And if nothing is said, the silence is total: a pristine device against an empty server
takes the zero-remote-lofts branch, which adopts nothing deliberately — *never guess* — so
there is not even a toast.

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

**HTTPS: GitHub's own figure is up to an hour**, not the day I first wrote here. Saving the
domain starts a DNS check; on success GitHub queues a Let's Encrypt certificate, and
***Enforce HTTPS* only becomes available once provisioning succeeds** — a check mark appears
beside the domain. The service worker will not register without HTTPS (`location.protocol`
gate), so **the app has no offline mode until it is live**: this step is waited out, not
squeezed in on the day.

Three ways provisioning gets stuck, all avoidable:

- **extra A/AAAA/ALIAS/ANAME records at the apex** beyond the four — provisioning fails;
- **CAA records present without one for `letsencrypt.org`** — issuance is refused;
- if it hangs anyway, the documented remedy is to remove the domain, retype it and save,
  which cancels and restarts provisioning.

GitHub's own warning is worth carrying: a Pages site that is disabled while a custom domain
is still configured is exposed to a domain takeover. If the custom domain is ever removed,
remove it in settings and in DNS together.

### e.1a Which repository the domain points at — a decision, not a detail

One custom domain per repository, and the domain replaces the path: a custom domain on the
`Zajildb` repo serves that repo at the apex and **`/Zajildb/` stops existing**. Third-party
reports say the old URL then 301-redirects to the custom domain; I could not find that on
any GitHub docs page, so treat it as likely-but-unproven and verify with one `curl -I`.
Either way — redirect or 404 — the bridge §d depends on would be gone the moment the domain
is attached to that repo.

**Recommendation: publish the port from its own repository and point `zajildb.com` at that
one, leaving `Zajildb` serving vanilla at `nahdaeverything-web.github.io/Zajildb/`
untouched.** It costs nothing and buys three things: the old app keeps serving, so the
export bridge survives indefinitely; the two deploys can run side by side during the pilot
instead of one replacing the other; and the rollback in §f stays a redeploy into the port's
own repo rather than a domain move between repos with a fresh certificate to wait out.

The alternative — one repo, domain attached, Pages source switched to the port — is simpler
to hold in your head and strictly worse on every count above.

### e.2 The Supabase API domain

`*.supabase.co` **was regionally blocked in the UAE during 2025**, and Zajil's audience is
Jordan and the Gulf. That makes a custom API domain a distribution requirement, not a
nicety — and it should be settled before users depend on it, not during an outage.

What it takes: a **CNAME** from the chosen host (say `api.zajildb.com`) to the project's
`*.supabase.co` domain, plus a **TXT** record at `_acme-challenge.api.zajildb.com` for
certificate issuance. Flow is `supabase domains create` → `reverify` → `activate`, and it
takes up to about 30 minutes. It is **$10/domain/month on top of a paid plan** (Pro is $25;
Free does not offer it) — and the project must leave the free tier regardless, because
**free projects pause after a week of idle**. That already bit this port: RF-3 records the
dev project auto-pausing, its hostname withdrawn from DNS, every live suite failing at
`AuthError('network')` — which is **exactly how a regional DNS block would present**.

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

**The catch, and it is unresolved.** Supabase's own instruction is to CNAME the custom
hostname *at* `<ref>.supabase.co`. A resolver that blocks `*.supabase.co` **by name** may
break the chain when it resolves the target — write-ups of the India incident flag exactly
this and recommend a self-owned proxy instead. Supabase's own material does not address it.
So a custom domain is the right first move and may not be sufficient; the fallback, if the
chain turns out to be blocked, is a proxy on a host we control. Worth knowing before it is
needed rather than during.

Counter-consideration, in the other direction: the project already sits behind Cloudflare,
so an *IP*-level block would take out a large fraction of the internet. The DNS/SNI vector
is the realistic one, and that is the one a custom domain addresses — if the chain resolves.

One failure mode to keep in view while any of this is being changed: pointing the app at a
**different project** breaks silently. `syncCursor` becomes a meaningless high-water mark
into another project's sequence, so pulls report `idle`; `lastAckedSeq` suppresses pushes
that never landed; and only a 4xx clears a session, so a network failure never surfaces as
an auth verdict. Changing the *hostname* of the same project is safe; changing the project
is not.

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
broken**, and measuring the two SHELLs says exactly who it strands. They intersect in **8
entries** — `/`, `/index.html`, `/manifest.webmanifest`, the two datasets and the three
icons — which vanilla's `addAll` overwrites on the way back. The other **130 are port-only**:
`/birds.html`, `/tools.html`, `/bird/edit.html`, every `/_next/static/**` chunk, the fonts,
and 65 RSC payloads. So under a collision **the root URL recovers and every deep path stays
React forever**: a fancier who bookmarked `/birds`, or reopens the tab they left on
`/tools`, gets the port's document out of vanilla's own cache with the port's chunks beside
it, so it boots and looks fine. `start_url` is `./`, so a home-screen install does land on
root — a browser tab does not. No number of reloads fixes it, because the only eviction
signal is the version string changing. Bumping to `2.0.0` makes the sweep fire and the 130
vanish.

**One strand survives the version bump, and it is not in the fix above.** Vanilla's
`index.html` loads `<script type="module" src="./js/app.js">`, resolved against the
*document URL*. After a clean, version-bumped rollback, a user parked on a **two-level path**
— `/bird/edit`, `/bird/new`, both real documents in the port's shell — reloads:

1. vanilla's worker misses, sees `mode === 'navigate'`, and serves the cached `./index.html`;
2. that document, at URL `/bird/edit`, resolves `./js/app.js` to **`/bird/js/app.js`** → 404;
3. the module never loads, `#app` holds only a `<noscript>` → **blank white page**;
4. reloading repeats it exactly. Only typing the site root recovers.

One-level paths (`/birds`, `/tools`) are fine. This is a real, if narrow, hole in the
rollback, and the cheapest mitigation is a root-absolute `src="/js/app.js"` in vanilla's
`index.html` — a one-character-class change to the app being rolled back to, which should be
made *before* it is ever needed, not during.

**And one way the port itself can quietly destroy offline mode.** If a port build's
`SCOPE !== BUILT_FOR`, `precache()` returns early **without caching anything**, while
`install` still calls `skipWaiting()` and `activate` still runs the sweep and claims
clients. That build therefore **deletes vanilla's cache and installs nothing in its place**.
Online everything works; offline every navigation returns an empty 504, and the only signal
is a `console.error`. This is precisely what `base-path-consistent` now makes unshippable,
and it is the strongest argument for that guard existing at all.

### f.4 What it proves

The **vanilla** `tests/e2e/live_deployment.py`, URL-parameterised, run against the
rolled-back origin: the six nav links, no failed requests, a worker scoped correctly, a
versioned cache, an installable manifest, the 38-bird example, offline boot, offline data,
offline COI, zero page errors. Because every selector in it is vanilla-only (§0.4), green
means **the browser is getting vanilla and not the port** — which is exactly the question a
rollback asks. Its offline third is the most valuable part: it proves vanilla's 40-entry
precache actually took, from the real host, over the real network, which is the step a
rollback depends on and the one that can silently half-fail.

Two things it will not tell you, so check them by hand: it opens a **fresh profile**, so it
never exercises the returning user with the port's worker already installed, and it only
walks the **root path**, never the deep ones f.3 strands.

---

## g. The order of operations

Nothing in stages 1–6 touches a user. The first step a user can see is stage 7, and the
first that is slow to undo is stage 8.

| # | Step | Gate before moving on |
|---|---|---|
| 1 | Bump `next/package.json` to the release version | `version_display.py`; the About row reports the new string |
| 2 | **Port `live_deployment.py` into `next/tests/e2e/` and make both copies read `ZAJIL_LIVE_URL`** (§0.4) — without this there is no first gate | the ported copy green against a local static serve of the export; the vanilla copy green against the live `/Zajildb/` |
| 3 | **Write the empty-target import test** (§d.2) — a full export with real photo bytes into a database with nothing in it | green in the gate |
| 4 | Build the config injection mechanism (§a.3) and its guard consequences | the full gate green; `config_injection.py` still proves the repo unconfigured |
| 5 | Create the production Supabase project: settings (signups off, **anonymous off**, email provider on), the consolidated migration, the verification query | the four queries, **then** `push_live.py` + `pull_live.py` + `auth_live.py` against it — objects, then paths |
| 6 | Create the pilot account through the admin API; confirm `POST /auth/v1/signup` → 422 | `auth_live.py` signs in, refreshes and signs out against production |
| 7 | **The old origin gets its migration notice** — early, because its cache-first worker means it lands on the second reload and never for anyone who does not reload (§d.4) | the notice is visible on a device that already had the app installed |
| 8 | Point `api.zajildb.com` at the project; wait for the certificate | the same three live suites, re-run against the custom host |
| 9 | Point `zajildb.com` at the **port's own repository** (§e.1a); wait out HTTPS (~1h); enable Enforce HTTPS | the origin serves over HTTPS and a worker can register at all; `curl -I` the old URL and record whether it redirects |
| 10 | **Deploy the port** to `zajildb.com`, configured, base path empty | **the ported `live_deployment.py` — the first gate** |
| 11 | A real push and pull from a real device on the live origin | **`push_live.py` / `pull_live.py` against production — the second gate** |
| 12 | The export/import path is walked end to end by a person, on a real phone with real photos | a file exported at the old origin imports at the new one with its photos |
| 13 | Samir's own loft moves | §h |

Stage 7 moved ahead of the domain work deliberately: it is the only step whose effect is
delayed by days rather than minutes, because it has to propagate through a cache that never
revalidates.

Stage 9 is the one that cannot be undone in ten minutes — DNS propagates and a certificate
has to be issued. Everything before it is rehearsal; everything after it is a redeploy,
provided §e.1a's two-repo layout is what was built.

---

## h. What must be true before Samir's own loft moves

This is the last gate, and it is deliberately strict, because his loft is the only copy of
data that matters and he is the person who cannot be told "restore from your export".

1. **The ported `live_deployment.py` is green against `zajildb.com`** — all eleven,
   including the three offline ones. (The suite must exist first; §0.4, stage 2.)
2. **`push_live.py` and `pull_live.py` are green against the production project**, reached
   through `api.zajildb.com`, not through `*.supabase.co`.
3. **Two devices have converged for real**: a bird created on one appears on the other, an
   edit on the second wins, and a delete on either sticks. `convergence.py` proves the
   design; this proves the deployment.
4. **A full export has been taken from the old origin and imported into the new one**, by
   hand, with the photos checked — the same path §d asks of everyone else.
5. **That export is kept somewhere off both origins** until step 3 has held for a week.
6. **The rollback has been rehearsed once**, on a throwaway origin or a branch deploy: the
   vanilla tree redeployed over a port install, two reloads, the vanilla `live_deployment.py`
   green — **including one reload started from a two-level path** (§f.3), which is the case
   the version bump does not fix. A rollback plan that has never been run is a hope.
7. **The version bump is in the shipped worker** — the About row on the live site reports
   the release version, not `1.9.1`. §0.1 is the whole reason.
8. **Public signups are still refused** on the production project, **and anonymous sign-ins
   are still off** — both re-checked after all the domain work, because they are the two
   settings that would be quietly catastrophic.
9. **The export bridge still answers.** The old origin serves, and a page under it can still
   read the old `zajil` database (§d.1) — verified, not assumed, after the domain move.

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

**A seventeenth, found while writing this plan, and it is not spec-vs-port but
vanilla-vs-port.** The port never renders `backup.warn30` («مرّ أكثر من ٣٠ يومًا على آخر
تصدير»): the string is in the dictionary, no component reads it, and vanilla banners it on
every route when the last export is over thirty days old and the loft is not empty. It is
the only in-app prompt that puts an export in a fancier's hands — which §d now depends on
twice over, once for the migration and once for the "keep a copy off both origins" habit.
**Recommendation: restore it before the cutover**, not after; it is a small component and it
is the difference between a backup culture and a backup intention.
