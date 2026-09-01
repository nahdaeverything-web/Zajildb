# BACKLOG

Findings from an adversarially-verified audit: each item was claimed by one
agent reading the source, then a second agent tried to refute it against the
actual code. 32 further claims were refuted and are not listed. A further ~30
were never verified (that run hit a limit), so this list is thorough but not
exhaustive.

**20 open** (0 high · 10 medium · 10 low) ·
**13 closed in v1.7** · **0 closed in v1.8** · **0 closed in v1.9** ·
plus **3 open decisions**, **7 planned items**, a **v1.9.1 bundle**, and a
**release checklist**
below.

Nothing open is a crash or a blocker. Severity is the auditor's and reflects
user impact, not effort.

**v1.8 closed nothing from this list, deliberately.** It was a sync-shape pass —
additive infrastructure (op log, tombstones, provenance, device identity) rather
than defect work, so every item below survives it untouched. The one bug v1.8
did fix — merge-importing an older export resurrecting deleted birds — was
never in this list: it was found while specifying v1.8, not by the audit that
produced these findings. It is recorded here for completeness only:

> **Fixed in v1.8, not from this backlog** — deleted birds resurrected when
> merge-importing an older export. Closed by `b9d2f53` (tombstones + the import
> guard). The one user-visible behaviour change in that release.

**v1.9 closed nothing from this list either, and for the same reason.** It was
a sync release: auth, push, pull, conflicts, and the status UI. It did close
the one **planned** item (P1, the `db.js` split) and it fixed several defects
of its own making — but none of those were audit findings, so every item below
survives untouched. Recorded for completeness:

> **Found and fixed inside v1.9, not from this backlog** — the migration script
> was incomplete twice (a missing sequence grant, then a missing last-write-wins
> guard), a `4xx` was treated as a poison record and would have discarded the
> whole push queue, server and client spelled the same instant differently so
> two devices reached opposite verdicts about one conflict, and the sync error
> writer restarted the silence window on every cycle so a persistent failure
> never surfaced. Each is written up in HANDOFF §15.12 with what it cost.

---

## v1.9.1 — RELEASE-BLOCKING

**Bundled as ONE micro-release, not shipped separately.** `main` runs
sync-inert (`js/sync-config.js` empty), so no user was exposed to any of this,
and one coherent v1.9.1 beats four tiny deploys.

**COMPLETE on `release/v1.9.1`, awaiting merge.**

| | Item | State |
|---|---|---|
| R1 | sign-in surface | **done** — form, three error kinds, sign-out keeps data |
| R2 | `record_id` typed `uuid` | **fixed and verified** (server-side, live) |
| R3 | error surfacing under a real failure | **resolved, no defect** |
| R4 | an empty default loft per device | **done** — pristine lofts are never pushed; a lone remote loft is adopted |
| R5 | pulled-delete identity asymmetry | **done** — a record is keyed on the server's identity |
| R6 | a suite depended on a server it did not start | **done** — it provisions its own |
| B | example datasets → real uuids | **done** — plus a guard so it cannot return |

Everything below this table is either already closed or is future work.


### R1. There is no sign-in surface in the UI

`signIn()` exists and works; **nothing in `js/views/` calls it.** Signed out,
the المزامنة card renders one line of text — *"غير مسجّل الدخول"* — and offers
no way to change that. A fancier who installs Zajil cannot reach their account
from the interface at all.

> **An invite-only product where the invited person cannot sign in is not
> shippable to them.** This blocks any release to a real user. It does not
> block the deployed v1.9.0 build, which ships with sync inert by decision.

Found in the first-user session (2026-08-30), by walking the path rather than
by reading the spec — see HANDOFF §15.12 item 8.

**The work:** email + password fields and a sign-in button in the المزامنة card,
a sign-out button when signed in, `AuthError` surfaced by `kind` using the
strings that already exist (`sync.err.session` for a rejection, and the calm
network wording for `kind: 'network'` — a bad connection is not a wrong
password, and the split already exists in `js/db/sync.js`). Disable the button
while the request is in flight; the existing double-tap backlog item applies.

**What NOT to do:** do not add a "create account" flow. Accounts are created
through the admin API and public signups stay disabled — that is what makes
invite-only true rather than aspirational (SPIKE §4f).

The workaround used in the first-user session, for reference:

```js
(await import('./js/db.js')).signIn('you@example.com', 'your-password')
```

### R2. `record_id` was typed `uuid`; Zajil ids are not uuids — FIXED AND VERIFIED

Found by the first real user, within an hour of signing in. Fixed the same
session.

`sync_records.record_id` was `uuid`. Both shipped example datasets — offered in
the empty state and in الأدوات — use readable ids (`e-gouden`, `x-remco`,
`f-saqr`): **111 records between them, none of them uuids**. `importAll`
accepts any string id, so any export from such a loft carries them too.

```
400  {"code":"22P02","message":"invalid input syntax for type uuid: \"g1-lama\""}
```

Every push carried at least one, so **every push was rejected whole** —
including the valid records batched with them. 45 ops sat queued for half an
hour and would have sat there forever.

**Fixed:** `alter table public.sync_records alter column record_id type text;`
Verified on the dashboard (column is `text`, PK and both indexes intact, RLS on,
four policies, LWW guard present) and end-to-end: the queue drained on the next
cycle and 48 rows landed across six stores, owner-scoped and ascending.

**No format or length constraint replaces it**, deliberately — a `check` on id
shape would recreate the identical failure for the next import that does not
match it. See SYNC-DESIGN §1, "client ids are opaque strings".

**What did NOT fail, which is worth as much as the fix.** The 4xx rule from
Phase 5 held the queue instead of discarding it; the silence window escalated on
schedule; the header showed the amber interruption and الأدوات showed the full
error with count and date. One defect, and the containment and surfacing built
around it worked on the first real failure they ever met.

### R3. Error surfacing under a real failure — RESOLVED, NO DEFECT

Recorded because a mechanism that works under a genuine failure is worth as
much on the record as one that does not.

R2 produced a real 30-minute server rejection on a real device. Every part of
the containment and surfacing built in Phases 3, 5 and 6 behaved exactly as
designed, confirmed by screenshot:

- the **4xx rule** held the queue instead of discarding it — under the original
  "a 4xx is a short count of zero" implementation, bisection would have marked
  all 45 ops poison, acked past them and pruned them, destroying the loft
- the **silence window** stayed quiet through the transient phase and escalated
  on schedule
- the header showed the amber *"تعذّرت المزامنة"* interruption
- the الأدوات card showed the full error with status code and timestamp

No action. See HANDOFF §15.13.

### R4. Every device adds an empty default loft to the account — v1.9.1

`initDB()` creates a default loft on a fresh database, and first-login sync
dutifully pushes it. So a fancier with a phone, a tablet and a laptop ends up
with **three empty lofts plus the one they actually named**. Observed directly
in the first-user session: two devices produced three loft rows.

Nothing breaks — the clutter simply grows with device count, and every extra
loft is a row that syncs forever.

Not obvious which fix is right, so it needs a decision rather than a patch:
suppress the synthetic op for an untouched default loft; or adopt an existing
remote loft on first sync instead of pushing a local empty one; or let the user
delete lofts (there is no delete-loft flow today). The first is smallest, the
second is most correct, the third is needed regardless.

### R4. Every device added an empty default loft — FIXED (v1.9.1)

`initDB()` creates an empty loft on every fresh device and first-login sync
pushed it, so the account gained one empty loft per device — and the fancier
has no way to delete one.

**The half that actually damaged data**, found while writing up the options:
`currentLoftId` was set once at `initDB()` and only repaired when the current
loft was *missing*, never when the user's real loft arrived beside it. So every
device after the first showed a **blank loft name** and filed every new bird
under its own empty default's id. One loft, silently split in two. It did not
bite in the first-user session only because that second device was used to read,
not to write.

**Fixed:** a pristine loft — unnamed, unplaced, and referenced by no record —
is never pushed. After the first pull, if this device is still on its pristine
default and EXACTLY ONE remote loft arrived, it is adopted: `currentLoftId`
switches and the local default is dropped. Zero or several remote lofts and
nothing happens; which loft a fancier means is not a question this code answers
by picking one, the same refusal §6 makes about duplicate birds.

Dropping the pristine default logs no op and writes no tombstone — the third
exception in the op-enumeration matrix (§8), and different in kind from the
first two: that record was never anywhere but this device.

> **KNOWN LIMITATION.** A device that created records under its own default
> loft BEFORE first login is not pristine, so it keeps that loft and pushes it.
> Meeting a named remote loft, the account legitimately ends with two. The
> duplicate notice covers the birds; merging or deleting lofts is P6.

### R6. A suite depended on a server it did not start — FIXED (v1.9.1)

`subpath_hosting.py` assumed a static server on :8124 that nothing in the suite
provisioned. Its document root was a hand-made COPY of the repo, and the suite
passed against a week-old tree for eight days — surfacing only when the shipped
datasets changed under it in item B.

> **A test that depends on something it did not start can be green about the
> wrong thing.** It was not failing; it was passing, about a tree nobody was
> shipping.

Fixed: the suite starts its own threaded server on an **ephemeral port**, rooted
at a temp directory holding a symlink to the repo — the live tree by
construction, and no port to collide with. Verified with nothing external
running on 8124.

Worth generalising: this is the only suite that had such a dependency, but the
class is easy to reintroduce. If a suite needs infrastructure, it starts it.

### R5. A pulled record was keyed on its body id, not the server's — FIXED ON BRANCH

`applySyncPut` keyed the local write on `row.data.id` while `applySyncDelete`
keys on `row.record_id`. A row whose body disagreed with its primary key landed
under an identity the server does not know and became **unreachable by every
future sync, including its own deletion** — while every layer reported success
(`applied: 1`, `ok: true`, `state: synced`).

Found in the first-user session: one device held a record that no amount of
syncing could remove. Fixed on `fix/v1.9.1-pulled-delete` (`84d0571`), tests
first, four mutations all caught, browser 508 → 515. **Held for the v1.9.1
bundle** — the deployed build is sync-inert, so nobody is exposed.

The affected device was healed through the **normal sync path**, with no local
database surgery: a delete addressed to the identity the orphan actually had.
All three fingerprints — two devices and the server — then agreed exactly.

The part worth remembering is in HANDOFF lesson 10: the same asymmetry was also
hiding in the resurrection check, and the first fix left it there. Only a
mutation exposed it.

### B. Regenerate the example datasets with real uuids — v1.9.1 tidy-up

`sample-data.json` and `example-loft-large.json` use readable ids. That is no
longer a sync problem (R2 fixed the column), but it contradicts the convention
in HANDOFF §14 — *"UUIDs only"* — and a convention the shipped data breaks is
a convention that will mislead someone again.

Regenerate both through `tools/gen-sample.js` and `tools/gen-example-large.js`
with `crypto.randomUUID()`. **Not urgent and not risky to defer**: ids are
opaque to the server now.

Care needed: the COI acceptance fixtures are contractual and reference birds by
id (`tests/e2e/*.py`, `tests/sample.test.js`, `tests/example-large.test.js`).
Regenerating means updating those references in the same commit, and the four
COI values must come out identical — they are computed from pedigree structure,
not ids, so any change in them means the regeneration was wrong.

---

## Planned work

Not debt — a decision already taken, recorded so it is not rediscovered.

### P1. Split `js/db.js` at v1.9 — DONE in v1.9

Closed by `dbdc57d` (the split) and `d2bfe41` (the guard amendment).

`db.js` is now a **facade**: comment and re-export, nothing else, over
`db/storage.js`, `db/oplog.js`, `db/records.js`, `db/io.js` and `db/sync.js`.
The split was mechanical — of 59 top-level blocks, 55 moved byte-identical and
4 differ only by a prepended `export` — and the browser suite passed unchanged,
suite for suite.

The concern that prompted the plan was exactly right: the three guards keying
on "outside `js/db.js`" had to be updated deliberately. They were, and then
**tightened** rather than merely widened — they now exempt `js/db/` and *not*
the facade, because after the split `js/db.js` provably contains zero writes.
Tightening them immediately exposed a defect in the scan itself: the facade
re-exports `idbPut`/`idbDelete`/`idbClear` by name, and a bare-identifier scan
flagged its own re-export list. See HANDOFF §15.1.

### P2. Blob sync — v1.9.x

v1.9 syncs media **metadata** but not the bytes (SYNC-DESIGN §7). A device can
hold a media row whose blob lives on another device; the gallery says so
("الصورة على جهاز آخر") rather than showing a broken image.

Deferred deliberately, not overlooked: blobs are large and slow on the
connections this product targets, Supabase Storage needs its own
upload/download state machine with resumability, and the spike's storage proof
covers ownership rather than transfer of many megabytes over a weak link. The
design is already proven in SPIKE §6 — a private bucket with path-prefix
ownership `<user-id>/<media-id>`.

### P3. Proactive token refresh — v1.9.x nice-to-have

v1.9 refreshes **reactively**: use the access token, and on a `401` refresh once
and retry. That costs one wasted request per hour of active use and needs no
stored expiry and no timer to drift.

Proactive refresh would avoid that request. It was considered and rejected for
v1.9 on the grounds that the failure mode is a single retried request, which
push idempotency absorbs — and that storing an expiry means a settings key
holding a number the server already tells the truth about. Recorded so the
trade-off is not re-litigated from scratch.

### P7. A guard that HANDOFF's stated version equals sw.js VERSION — v1.9.x

Two rows of HANDOFF's status snapshot described the world before v1.9.0
shipped, and were caught by eye during v1.9.1's release prep rather than by
anything automatic. Nothing catches stale prose the way a guard catches stale
code, and the status snapshot is the first thing a new session reads — a wrong
version there sends someone looking at the wrong build.

**The cheap, high-value slice:** assert that the version string HANDOFF claims
to be current equals `sw.js`'s `VERSION`. That is a single fact, mechanically
checkable, and it is the one most likely to mislead.

Deliberately NOT "check every claim in HANDOFF" — most of it is prose that no
guard can validate, and a guard that tries would either be noisy or would
encourage writing only what a machine can check. One fact, checked exactly.

Note the ordering it implies: bumping `sw.js` VERSION without updating HANDOFF
would fail the build, which is the point.

### P6. Deleting and merging lofts — the cascade question first

**There is no delete-loft flow anywhere in the app.** `Lofts.remove()` exists
via `makeGeneric` and no view calls it. A fancier can create and rename lofts
and never remove one — which R4 made visible, and R4's known limitation leaves
standing for anyone who used a device before signing in.

Deliberately NOT rushed into v1.9.1. The blocker is not the UI, it is a
question the codebase has no answer for: **what happens to records filed under
a deleted loft?** `deleteBird` cascades because a bird's dependents are
unambiguous; a loft's are not. Orphan them to no loft, reassign them to another,
or refuse to delete a loft that holds records — each is defensible and each is a
product decision, not an implementation detail. Getting it wrong loses data.

Merging two lofts is the same question wearing a hat: it is a reassign-then-
delete, and it needs the same answer.

Decide the cascade rule first, then build it.

### P5. Real-time subscriptions — v2.x, when club mode needs them

v1.9 syncs on a ~60 s heartbeat, plus `online` and `visibilitychange`. Confirmed
in live use: an idle window pulled a bird unprompted on the heartbeat, a refresh
synced instantly via boot, and in-app navigation is deliberately not a trigger
because routing is local and must never wait on the network.

That cadence is right for one fancier's own devices and wrong for two people
watching the same thing. **When club mode or a marketplace needs live
cross-user updates, the upgrade is Supabase real-time subscriptions** on
`sync_records`, filtered by owner — the pull path already applies rows
idempotently through `applySyncPut`, so a subscription would feed the same
apply, not a second code path.

Not scheduled. Recorded so the option is known and the heartbeat is not
mistaken for a limitation nobody noticed.

### P4. Split `js/db/sync.js` — with the first v1.9.x item that touches it

`sync.js` is **1,098 lines**: auth, push, pull, conflict resolution, status,
backoff and the cycle loop. That is larger than `db.js` was (866) when P1 was
raised — the v1.9 split solved the problem and the sync layer has recreated it.

Nothing is wrong with it today, and this is deliberately **not** scheduled as
work of its own. Splitting a file that nothing is about to change buys nothing
and risks a regression in the most safety-critical code in the app. It is
scheduled instead with **the first v1.9.x item that touches it** — P2 (blob
sync) or P3 (proactive refresh), whichever lands first.

A likely shape, following the seam the code already has:

| Module | Content |
|---|---|
| `db/sync/auth.js` | config, session, refresh, the multi-instance re-read |
| `db/sync/push.js` | op→row mapping, batching, the ack rule, bisection, compaction |
| `db/sync/pull.js` | cursor, page fetch, apply, LWW resolution |
| `db/sync/status.js` | state derivation, backoff, the cycle loop |
| `js/db/sync.js` | facade over those, exactly as `js/db.js` is over `js/db/` |

The precedent from P1 applies in full, and so does its warning: **the guards
key on `js/db/`**, and `js/db/sync/` is not `js/db/` to a `startsWith` check.
That allow-list must be updated deliberately and every guard re-proven to fire,
or the split will quietly exempt the sync layer from the rules that police it.

---

## Release checklist — v1.9

Carried here rather than in a chat message, because every item is a thing
someone must do to a live system and none of them are code.

### Before merge

- [ ] **Nothing.** The branch is green: 138 node, 508 browser, and three live
      suites against the dev project (auth 13, push 24, pull 12).

### At release

- [ ] **Create the production Supabase project from SYNC-DESIGN §1's script,
      in one run.** That block is the complete current schema — sequence,
      table, index, the trigger with both the advisory lock and the
      last-write-wins guard, RLS, table grants, the **sequence usage grant**,
      the revokes, and four policies. A guard asserts it stays complete. Do not
      assemble it from the original plus the amendment sections; those are
      history.
- [ ] **Disable public signups** on the production project. This is what makes
      "invite-only" true rather than aspirational (SPIKE §4f), and it is a
      dashboard setting, not code.
- [ ] **Run the verification queries**, then run `--live-push` against the new
      project. Introspection proves objects exist, never that a write succeeds
      — that lesson cost a debugging session on the dev project (HANDOFF
      §15.12 item 1).
- [ ] **Fill in `js/sync-config.js`**, or inject `globalThis.ZAJIL_SYNC_CONFIG`
      at deploy. It ships empty on purpose: the publishable key is safe to
      publish, but a live project URL in a public repository is a release
      decision. Two guards will fail the build if the constants are filled in,
      so **filling them in means updating that guard deliberately** — which is
      the point.
- [ ] **Prove the UI against the real project.** Every sync suite runs against
      a stub; auth, push and pull are proven live, but nobody has yet driven
      the status row and the المزامنة card against a real endpoint. This closes
      in the first-user session after deploy, with config from the environment
      per §5a. **It is the last gap between "tested" and "seen working."**
- [ ] **A custom API domain** for the Supabase project, so the client is not
      pinned to a generated hostname it cannot change later.
- [ ] **Supabase Pro**, if the pilot needs the backup retention and the
      resource floor a free project does not guarantee.
- [ ] **Confirm backups.** The app's own `autoBackup` is a local safety net and
      is deliberately not synced; server-side backups are a separate,
      dashboard-level concern.

### After deploy

- [ ] Bump `main`'s tag and confirm the live service worker reports
      `zajil-v1.9.0` (`version_display.py --live`).
- [ ] Watch `syncAnomalies` on the first real devices. It is capped at 100 and
      is a diagnostic surface, not a log — if it is filling up, something is
      being refused and the الأدوات card names it.

---

## Open decisions

Not defects — choices from the v1.7 pass that need an owner. Full reasoning in
[docs/V1.7-NOTES.md](docs/V1.7-NOTES.md).

### D1. A pre-v1.7 export still violates the ownership invariant

`newBird()` guarantees `external === (status === REFERENCE_STATUS)`, and both
shipped datasets were regenerated to match. But `importAll` is the force path,
so **an export taken before v1.7 imports external birds carrying
`status: 'stock'`** — mislabelled and misfiltered in the register.

Normalising it is a data migration, which is why it was not done unilaterally.
Options: normalise silently on import; normalise and report ("12 ancestors were
re-labelled"); add a one-off "repair data" action in Tools beside the integrity
check; or leave it and accept that the ownership filter is slightly wrong for
old data.

### D2. Should an unconfirmed warning block a write?

`saveBird` is currently **strict by default** — hard errors *and* unconfirmed
warnings both reject, so a future view that forgets to confirm a duplicate ring
cannot silently create one. `{allowWarnings: true}` is the caller stating the
user confirmed.

The alternative is warnings never blocking, which is a one-line change in
`classifySave`. Strict was chosen because the v1.7 brief asked for duplicate
rings to be refused by `saveBird` itself, while a duplicate ring is
deliberately a *warning* (re-ringed birds are real).

### D3. `getBird` is synchronous, and the engine depends on it

The single biggest constraint on any future server-backed layer. COI traversal
calls `getBird` thousands of times inside recursive memoised paths, which is
why `db.js` keeps `state.birds` as an in-memory Map.

A server-backed layer cannot answer synchronously. Either keep a full local
mirror and sync it (engine untouched — and what local-first already implies),
or make the engine async, which makes `coi.js` substantially harder. Cheapest
to decide **before** building on top. Five further structural frictions are in
the notes.

---

## Medium (10)

### Re-picking files in the photo/document inputs accumulates instead of replacing — wrong photos get attached

**Where:** `js/views/bird-form.js`  
**Trigger:** On the bird form, tap "Add photo", select two photos, notice one is wrong, tap the input again and select only the correct photo. Save.  
**Effect:** Both `change` handlers do `for (const f of photoIn.files) pendingMedia.push(...)` and never clear `pendingMedia` for that input. The second selection replaces `photoIn.files` in the UI but the first batch is still queued, so `doSave` attaches all three files (and two copies of any file selected twice). There is no list of pending attachments and no way to remove one, so the user cannot see or undo it before saving.  
**Suggested fix:** Key pending media per input and rebuild on each change (e.g. `pendingPhotos = [...photoIn.files].map(...)` instead of pushing), then concatenate at save time; and render a small removable chip list of queued files.

### Edit URL for a missing bird renders a blank "New bird" form instead of redirecting

**Where:** `js/views/bird-form.js`  
**Trigger:** Open any `#/bird/<id>/edit` URL whose record is not present — a bookmarked/shared edit link on a device that never had that bird, a link kept after a Tools "Replace everything" import, or browser-Back onto the edit URL of a bird deleted in this session.  
**Effect:** `const existing = birdId ? getBird(birdId) : null;` has no guard, so `existing` is null, `isNew` becomes true and the user gets an empty create form titled "New bird" for a URL that says /edit. Saving creates a brand-new record under a freshly generated uuid rather than the one in the URL. Every other id-driven view (bird-detail.js:21, pedigree.js:21) guards this with `if (!bird) { navigateReplace('#/birds'); return null; }`.  
**Suggested fix:** Mirror the other views: `if (birdId && !existing) { navigateReplace('#/birds'); return null; }`.

### Pair saved into a different season vanishes: the season <select> is built once and never rebuilt

**Where:** `js/views/breeding.js`  
**Trigger:** Open Breeding (selector defaults to the current year, e.g. 2026). Click "+ New pair", fill sire/dam, change the Season field to 2027 (or 2025, or any season with no pairs yet), Save.  
**Effect:** `seasons` and `seasonSel` are computed once in renderBreeding() (lines 23-27); `refresh()` (line 31) only clears `listWrap` and re-filters by `p.season === vs.season`. The saved pair belongs to 2027, so it is filtered out of the list, and 2027 was never added as an <option> — so the user sees the "No pairs this season yet" empty state, a "Saved" toast, and no way to reach the pair they just created. app.js only re-runs route() on hashchange, so the pair stays unreachable until the user leaves the Breeding tab and comes back.  
**Suggested fix:** Move the seasons/option build into refresh() (rebuild the <select> options from state.pairs each time), and after Pairs.save set `vs.season = savedPair.season` before calling refresh() so the new pair is what the user is looking at.

### The same bird can be linked as the chick of two different eggs

**Where:** `js/views/breeding.js`  
**Trigger:** Link bird X to egg 1 of round 1. Add a second egg, mark it hatched, press "Link an existing bird" and pick bird X again (or do it from an egg of a completely different pair).  
**Effect:** The picker filter (line 270) only excludes `pair.sireId` and `pair.damId` — nothing excludes birds that already carry a `chickId` reference from another egg. Both eggs end up with `chickId === X`: the loft shows two chicks that are one bird, wean/ring flags are tracked twice for one record, and if the second link came from another pair, X's sireId/damId are silently rewritten to that pair while the first egg's row still displays X as its chick under the wrong parents. Unlinking one egg leaves the other dangling on the same bird.  
**Suggested fix:** Build a Set of every chickId already referenced by any egg in state.pairs and exclude those birds in the picker's filter (or block them in the onClick with a t('br.linkBlocked', …) message).

### "Mark failed" / "Mark hatched" are one-way with no confirm, no undo, and no way to delete an egg

**Where:** `js/views/breeding.js`  
**Trigger:** Mis-tap "Mark failed" on the wrong egg row (the buttons sit next to each other on a phone).  
**Effect:** The handler sets `egg.state = 'failed'` and saves (lines 217-222). A failed egg row renders only its label and laid date — no state buttons — and there is no remove-egg or remove-round control anywhere in roundBlock/eggRow, so the false record is permanent for that season. The same applies to "Mark hatched": once hatched, "Mark failed" disappears. Neither transition passes through confirmDialog or undoToast, contrary to the destructive-action invariant.  
**Suggested fix:** Offer undoToast after a state change (restoring the previous state/hatchDate), and add a small delete control for an egg and a round, also with undo.

### Race log's FCI column marks results as qualifying for birds with no FCI ring

**Where:** `js/views/races.js`  
**Trigger:** Open Races → race log with the shipped sample-data.json loaded. Race r-5 ("بطولة الاتحاد — العقبة", 27 fanciers / 214 birds, type federation) belongs to bird فجر, which carries no FCI ring.  
**Effect:** The FCI column (line 69) is computed from `resultQualifies(r)` alone, which only checks fanciers >= 20, birds >= 150 and raceType !== 'training'. ENGINE.md §6 and the FCI tab in the same view both state a result counts only if the bird also carries an FCI ring. So the log shows ✓ for فجر's result while the FCI tab in the adjacent tab shows ✗ (no ring) for the same bird — the two tabs of one view contradict each other, and the user is told a result counts toward FCI awards when it does not. Note `hasFCIRing` is already imported at the top of races.js and never used.  
**Suggested fix:** In logTab, compute `const q = resultQualifies(r); const ok = q.qualifies && hasFCIRing(getBird(r.birdId));` and render ✓ only for `ok` (or render a third state for 'race qualifies but bird has no FCI ring').

### Coordinate parser silently mis-reads DMS/degree-symbol/Arabic-numeral coordinates instead of rejecting them

**Where:** `js/views/races.js`  
**Trigger:** In the race result dialog, paste coordinates in any format other than plain decimal pairs — e.g. "29 32 15 N, 35 0 22 E" (space-separated DMS, a common copy from a GPS/handheld), or "29.5321° N, 35.0063° E" (Google Maps default), or Eastern-Arabic digits, then press "حساب السرعة من الإحداثيات".  
**Effect:** `parseCoords` (line 135) uses an unanchored regex `/(-?\d+(?:\.\d+)?)[\s,;]+(-?\d+(?:\.\d+)?)/`, which matches the first number pair anywhere in the string and ignores the rest. Verified in node: "29 32 15 N, 35 0 22 E" → {lat:29, lon:32}, so the release point is silently placed ~250 km from the real one and the computed distance and velocity written into the form (and then saved) are wrong with no warning. "29.5321° N, 35.0063° E", "N29.53 E35.00" and Eastern-Arabic digits all → null, in which case the calc button returns silently (line 140: `if (!a || !b) return;` with no toast) and on save   
**Suggested fix:** Anchor and validate: require the whole trimmed string to be a coordinate pair, normalise Eastern-Arabic digits first, accept an optional degree symbol / N,S,E,W hemisphere suffix and DMS, and range-check lat ∈ [-90,90], lon ∈ [-180,180]. When parsing fails, show a toast/field error instead of returning silently, and only persist loftCoords once it parses.

### Save button is a silent dead end when the bird field holds text but no selection

**Where:** `js/views/races.js`  
**Trigger:** Edit an existing race result (or open a new one), click into the bird field — the picker selects the prefilled label on focus — type a character, then click Save. Same in the Health event dialog with scope "single bird".  
**Effect:** birdPicker's `input` listener (js/ui.js:301) sets `root.value = null` on any keystroke, so the field still displays text while the selection is gone. races.js:178 (`if (!birdP.value) return false;`) and health.js:84 do keep the modal open but render no message at all, so Save appears to be broken: the user sees a filled bird field and a button that does nothing, with no clue that they must click a row in the dropdown. breeding.js:91-94 handles the same case correctly by appending errors to an errBox before returning false.  
**Suggested fix:** Mirror breeding.js: add an error box to both dialogs and populate it with `t('bird.chooseBird')` (and any other failed validation) before `return false`, or at minimum fire a toast.

### Statistics view recomputes COI per bird from scratch and freezes the UI for seconds on a real loft

**Where:** `js/views/stats.js`  
**Trigger:** Open the Statistics tab on a loft of a few hundred birds or more (especially a line-bred one) at the default COI depth of 10.  
**Effect:** `birds.map((b) => ({ b, coi: inbreeding(getBird, b.id, depth).coi }))` runs synchronously inside `renderStats`, and each `inbreeding` call rebuilds its own `truncatedGraph` and a fresh `makeKinship` memo — nothing is shared between birds, so the pair-memo work is repeated N times. Measured in node with the real engine (browsers, and phones especially, are slower): 512-bird selectively-bred loft = 334 ms, ~970-bird line-bred loft = 3.1 s at depth 10 and 3.9 s at depth 15. `route()` has already called `clear(main)`, so the user stares at an empty page with no spinner while the main thread is blo  
**Suggested fix:** Render the page shell first and fill the histogram asynchronously in chunks (or in a worker), and share one `makeKinship` memo across the whole collection instead of allocating one graph+memo per bird; cache results keyed by bird id + updatedAt + depth.

### Date-display setting is unreachable for English users: the dropdown shows "Gregorian + Hijri" while dates render Gregorian-only, and re-picking it fires no change event

**Where:** `js/views/tools.js`  
**Trigger:** Fresh install → Tools → set Language to English (never touching Date display) → look at the Date display dropdown, then try to enable Hijri by selecting "Gregorian + Hijri".  
**Effect:** The control is built as `select([...], state.settings.dates || 'both')` while app.js resolves the effective value as `state.settings.dates || (state.settings.lang === 'en' ? 'gregorian' : 'both')`. With `settings.dates` unset and lang='en', the dropdown displays "Gregorian + Hijri" but dates everywhere render Gregorian only — the displayed setting contradicts the app's behaviour. Worse, because the select's value already *is* `both`, choosing "Gregorian + Hijri" changes nothing and the `change` listener never fires, so nothing is persisted: the user can only reach the both-mode by selecting a   
**Suggested fix:** Use the same resolution in both places — export the default from a single helper (`effectiveDateMode()`) and seed the select with it, or write the resolved default into settings on first `applySettings()`.


## Low (10)

### Enter from a <select> triggers "Save & add another" instead of Save

**Where:** `js/views/bird-form.js`  
**Trigger:** On a new-bird form, tab to the Sex / Status / ring-type / Ownership dropdown, choose a value and press Enter (browsers that perform implicit submission from a closed select, e.g. Chrome on Windows and Firefox).  
**Effect:** The keydown guard whose comment says "Enter must never save a half-entered bird" only tests `e.target instanceof HTMLInputElement`, so selects are unguarded and implicit submission proceeds. Implicit submission fires the form's default button = the first submit button in tree order, which is "Save & add another" (it is appended before the primary Save). The half-entered bird is saved and immediately replaced by a fresh blank form with a "Saved … — enter the next one" toast, instead of landing on the saved bird's page.  
**Suggested fix:** Include selects in the Enter guard (`e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement`), and put the primary Save first in the DOM (reordering visually with CSS) so it is the default button.

### Filtering to zero matches renders a completely blank list — the empty state only appears when the database is empty

**Where:** `js/views/birds.js`  
**Trigger:** With birds in the register, set Ownership = "External only" (or any filter/search combination) that matches nothing. Optionally navigate to another tab and back — `vs` is module-level, so the filter persists.  
**Effect:** `refresh()` gates the empty state on `!state.birds.size`, not on `rows.length`, so with birds present but no matches the list area is rendered completely empty: no "no results" message, no hint that a filter is active, and no way to clear filters other than reopening each dropdown. Because the view state survives navigation, a user who leaves and returns sees a blank register and can reasonably think the data is gone.  
**Suggested fix:** Add a second branch: when `state.birds.size && !rows.length`, render a "no matches" block with a "clear filters" button that resets `vs` and calls `refresh()` (also re-syncing the select values).

### Hatch-from-ring-year hint goes stale after a ring row is deleted

**Where:** `js/views/bird-form.js`  
**Trigger:** Type a ring such as JO-2023-12345, see the "📅 Use ring year: 2023" button appear under Hatch date, then press the ✕ on that ring row (e.g. it was typed into the wrong row).  
**Effect:** `updateHatchHint` is only wired to `ringsWrap`'s `input` event and to `hatchIn`; `del`'s click handler just calls `row.remove()`. Removing a row fires no input event, so the hint keeps offering a year taken from a ring that no longer exists on the form, and clicking it writes 2023-01-01 into Hatch date. Adding a row has the same gap in reverse.  
**Suggested fix:** Call `updateHatchHint()` from the ✕ handler and from `addRing`'s onclick (or listen for a custom event dispatched on ringsWrap).

### Submit buttons are never disabled during save — a double tap duplicates attached media

**Where:** `js/views/bird-form.js`  
**Trigger:** On a phone, double-tap "Save" (or "Save & add another") on a form with photos attached while IndexedDB is writing.  
**Effect:** Nothing guards re-entry of the submit handler: both submissions run `doSave`, so the `pendingMedia` loop runs twice and `addMedia` stores a second copy of every photo/document under new ids. In the add-another case, the second handler's `root.replaceWith(next2)` is a no-op because `root` was already detached by the first, so the second freshly built form (and any focus/prefill work) is silently discarded while two toasts appear.  
**Suggested fix:** Set a `let saving = false` re-entry flag (and disable the submit buttons) for the duration of `doSave`, resetting it in a finally block.

### Save failures are silent — no try/catch around saveBird/addMedia

**Where:** `js/views/bird-form.js`  
**Trigger:** Save a bird with several large photos on a device where the IndexedDB quota is exceeded (or storage is otherwise unavailable).  
**Effect:** `doSave` awaits `saveBird` and `addMedia` with no error handling, and the warnings-modal path calls `doSave(bird, andNew)` without awaiting or catching. A rejection becomes an unhandled promise rejection: no toast, no navigation, no problem list — the form just sits there, so the user cannot tell whether the bird was saved and may re-enter it.  
**Suggested fix:** Wrap `doSave` in try/catch, surface the failure via `toast()`/the `problems` block, and attach a `.catch` to the modal's non-awaited `doSave` call.

### Bird rows carry role="listitem" on the <a>, removing their link semantics

**Where:** `js/views/birds.js`  
**Trigger:** Browse the register with a screen reader (or list the page's links).  
**Effect:** `row()` builds `h('a', { class:'bird-row', role:'listitem', href: '#/bird/'+b.id, ... })`. An explicit `role="listitem"` overrides the anchor's implicit `link` role, so assistive tech announces each row as a plain list item with no indication it is actionable, and rows do not appear in the links rotor. The filter selects (ownership/status/sex/sort) also have no accessible name beyond their first option's text, and the sort select has none at all.  
**Suggested fix:** Wrap each anchor in a `role="listitem"` element (or use ul/li) and leave the anchor's role alone; add `aria-label` to the four filter selects.

### IntersectionObserver and picker document listeners are never torn down — leak grows through the batch-entry loop

**Where:** `js/views/birds.js and `js/ui.js (driven by `js/views/bird-form.js)`  
**Trigger:** Batch-enter records with "Save & add another" for a long session (each iteration builds a new form with two birdPickers), and navigate in and out of the register repeatedly.  
**Effect:** `renderBirds` creates an IntersectionObserver per render and never disconnects it, and every `birdPicker` registers a permanent `document.addEventListener('click', ...)` with no removal path. Each abandoned form's picker closures keep the whole detached form subtree alive — including `pendingMedia`'s File references — so memory grows monotonically during exactly the flow the app optimises for, and every page click runs an ever-growing list of `root.contains(e.target)` checks.  
**Suggested fix:** Disconnect the observer and remove the document listener when the node leaves the document (a shared teardown registry the router calls on `clear(main)`, or a MutationObserver/`AbortController` signal tied to the view's lifetime).

### Pairing date and acquired date are collected but never displayed, and a pair cannot be edited

**Where:** `js/views/breeding.js`  
**Trigger:** Create a pair filling in "Pairing date" and "Acquired on" (the new bought-pair fields), then look at the pair card.  
**Effect:** pairCard renders only nestBox, acquiredFrom and status (lines 122-126); `pair.startDate` and `pair.acquiredDate` are read nowhere in the codebase (fmtDate is imported at line 10 and never used in this file). There is also no edit dialog for a pair, so a wrong nest box, season or date can only be corrected by deleting the pair — which throws away all its rounds and eggs. The user's input is silently swallowed.  
**Suggested fix:** Show the pairing/acquired dates in the pair-meta chips via fmtDate, and add an edit action that reopens the pair dialog on the existing record.

### Arabic comma hardcoded in the FCI non-qualifying reason list, leaking into English UI

**Where:** `js/views/races.js`  
**Trigger:** Switch the app language to English, open Races → FCI eligibility checker, and look at a bird whose result fails two rules (e.g. too few fanciers and too few pigeons).  
**Effect:** Line 111 joins the reason strings with the literal Arabic comma `'، '`, so the English UI renders "Fewer than 20 fanciers، Fewer than 150 pigeons" — an Arabic punctuation mark inside English text, which also disturbs bidi rendering of the surrounding LTR run. It is the only user-visible string in these two views not routed through t().  
**Suggested fix:** Use a language-dependent separator, e.g. a `list.separator` dictionary key (`{ ar: '، ', en: ', ' }`), or `getLang() === 'ar' ? '، ' : ', '`.

### COI depth field silently clamps out-of-range input and keeps showing the rejected number

**Where:** `js/views/tools.js`  
**Trigger:** Tools → type 30 (or 1, or clear the field) into "COI depth (generations)" and click elsewhere.  
**Effect:** The handler stores `Math.max(3, Math.min(15, +depthIn.value || 10))` but never writes the clamped value back to the input and never rerenders, so the box keeps displaying 30 while the persisted depth is 15 (or displays empty while 10 was stored). The user believes the pedigree/statistics COI is computed at the depth shown; the certificate and Statistics headings (`ped.coiAtN`) will then contradict the field on the settings page.  
**Suggested fix:** Assign the clamped value back: `depthIn.value = v;` after `setSetting`, and toast when the entered value was out of range.


---

# Closed in v1.7

Kept on record. All 13 were resolved as side effects of installing
the five shared primitives, not patched individually — see
[docs/V1.7-REPORT.md](docs/V1.7-REPORT.md).

| Finding | Commit | How |
|---|---|---|
| "Ring chick" creates a bird bypassing validateBird entirely | `1dae8f7` | phase 1.2 — validation moved inside `saveBird()` |
| Link path applies hatchDate after validation, so an impossible date is saved unvalidated | `1dae8f7` | phase 1.2 — the final record is composed, then validated |
| Undo of a bird deletion restores the record but never refreshes the visible bird registe | `2f9c86d` | phase 1.3 — the router refreshes on change events |
| Undo of a media deletion silently does nothing visible, and throws if the item is alread | `2f9c86d` | phase 1.3 — `restoreMedia()` emits; the snapshot is guarded |
| New health event defaults to the wrong day (date computed in UTC, not local time) | `3c79b9d` | phase 1.1 — `todayISO()` returns the local calendar date |
| Date-only values render one day early for users at negative UTC offsets | `3c79b9d` | phase 1.1 — `parseLocalDate()` keeps a bare date on its own day |
| Auto-filled dates use UTC, so between midnight and 03:00 local they record yesterday | `3c79b9d` | phase 1.1 — every date default goes through `todayISO()` |
| Every automatic snapshot base64-encodes all photos and then throws them away | `a5e2e79` | phase 3 — `exportAll({includeMedia:false})` |
| Replace-import erases the database before decoding the payload, so a mid-import failure  | `a5e2e79` | phase 3 — decode and validate everything first; snapshot to `backups` |
| Ancestors created inline from a parent picker get status 'stock', so the register mislab | `a932606` | phase 1.5 — `newBird()` derives status from `external` |
| Add-sibling placeholder flow rewrites the bird's parents before the sibling exists, with | `a932606` | phase 1.5 — writes deferred to the form's successful save |
| egg.chickId is left dangling when the chick bird is deleted, stranding the egg | `d6cc5ea` | phase 1.4 — `deleteBird` cascades and unlinks eggs |
| Deleting a bird orphans its race results, health events and breeding pairs | `d6cc5ea` | phase 1.4 — cascading delete with a complete undo snapshot |

## The closed findings in full

### ✅ "Ring chick" creates a bird bypassing validateBird entirely

**Closed by `1dae8f7`** — phase 1.2 — validation moved inside `saveBird()`

**Where:** `js/views/breeding.js`  
**Trigger:** Press "Ring chick" on a hatched egg and type a ring number that already exists on another bird — or ring a chick of a pair whose sire was later corrected to sex "hen" (or whose sire's hatchDate is after the egg's hatch date).  
**Effect:** ringChickDialog (lines 326-343) calls newBird()/saveBird() with no validation at all, while the sibling link path calls validateBird and the bird form blocks on errors and confirms on warnings (bird-form.js:209-228). Result: duplicate ring numbers are created with no warning (they only surface later in Tools' duplicate finder), and records the bird form would refuse as hard errors — sire recorded as a hen, parent hatched after the chick — are written silently.  
**Suggested fix:** Run `validateBird(chick, getBird, allBirds())` before saving; render errors in the dialog and `return false` to keep it open, and surface warnings (duplicate ring) for confirmation as the bird form does.

### ✅ Link path applies hatchDate after validation, so an impossible date is saved unvalidated

**Closed by `1dae8f7`** — phase 1.2 — the final record is composed, then validated

**Where:** `js/views/breeding.js`  
**Trigger:** Link an existing bird that has no hatchDate recorded to a hatched egg whose hatch date is earlier than the pair's sire or dam hatch date (easy after backdating a bought clutch's dates).  
**Effect:** validateBird is run on `candidate` while `candidate.hatchDate` is still empty (line 287), and validate.js's parent-age block is guarded by `if (bird.hatchDate)` — so it is skipped entirely. The code then saves `{ ...candidate, hatchDate: egg.hatchDate }` (line 298) without re-validating, writing a bird whose parents hatched after it — exactly the `val.parentYounger` hard error the bird form refuses. The `warnings` array returned by validateBird is also discarded, so a duplicate ring introduced by the link is never surfaced.  
**Suggested fix:** Compose the final record (including hatchDate) first, validate that, and show warnings for confirmation before the single saveBird call.

### ✅ Undo of a bird deletion restores the record but never refreshes the visible bird register

**Closed by `2f9c86d`** — phase 1.3 — the router refreshes on change events

**Where:** `js/views/bird-detail.js`  
**Trigger:** Open a bird → Delete → confirm. You land on #/birds and the bird is gone from the list. Within the 8-second window click Undo on the toast.  
**Effect:** `del()` calls `restoreBird(snapshot)` and shows `toast(t('toast.undone'))`, and the record really is put back into IndexedDB and into `state.birds`. But nothing re-renders: `js/app.js:133` subscribes with `onChange((ev) => { if (ev && ev.type === 'import') rerender(); })` and `restoreBird` emits `{type:'bird'}`; `js/views/birds.js` has no `onChange` subscription at all (the only two `onChange` references in the whole tree are app.js:133 and the definition in db.js:99). So the user sees a success toast on a list that still shows the bird missing. Since the register is the app's home screen, the  
**Suggested fix:** Either broaden the app.js subscriber to `rerender()` (or at least re-run `route()`) for `bird`/`media` change events, or have `del()`'s undo callback explicitly re-route after `restoreBird` (e.g. `navigateReplace('#/bird/' + id)` so the user lands back on the restored bird).

### ✅ Undo of a media deletion silently does nothing visible, and throws if the item is already gone

**Closed by `2f9c86d`** — phase 1.3 — `restoreMedia()` emits; the snapshot is guarded

**Where:** `js/views/bird-detail.js`  
**Trigger:** On a bird page, click ✕ on a photo in the gallery, confirm the delete, then click Undo on the toast. Separately: double-click ✕ so two confirm dialogs stack, confirm both.  
**Effect:** Two defects in the same handler (lines ~224-236). (1) The undo does `const { idbPut } = await import('../db.js'); await idbPut('media', snap);` — a raw `idbPut` that emits no change event — while `fig.remove()` has already permanently detached the figure from the gallery. The record comes back in IndexedDB but the page still shows it as deleted and there is no re-render path (app.js only rerenders on `type === 'import'`), so the 'Undone' toast is contradicted by the UI; the photo only reappears after a manual navigation. (2) `deleteMedia(id)` returns `await idbGet('media', id)`, which is `null  
**Suggested fix:** Guard with `if (!snap) return;` before offering undo; re-insert the figure node (or re-run the gallery fetch) inside the undo callback; and route the restore through a db.js helper that calls `emitChange({type:'media', ...})` instead of importing `idbPut` directly.

### ✅ New health event defaults to the wrong day (date computed in UTC, not local time)

**Closed by `3c79b9d`** — phase 1.1 — `todayISO()` returns the local calendar date

**Where:** `js/views/health.js`  
**Trigger:** Tap "+ New event" on the Health view outside the UTC-overlap window — e.g. at 01:00 local in Amman (UTC+3), or at 20:00 local in New York (UTC-4).  
**Effect:** Line 66 prefills the date input with `new Date().toISOString().slice(0,10)`, which is the UTC calendar day. Verified with node: TZ=Asia/Amman at 01:00 on 2026-08-24 yields "2026-08-23" (yesterday); TZ=America/New_York at 20:00 on 2026-08-24 yields "2026-08-25" (tomorrow). The user accepts the default and the vaccination/treatment is logged on the wrong date — and health events cannot be edited afterwards in this view, only deleted and re-entered. (js/views/breeding.js:67 has the identical line for pairing start date.)  
**Suggested fix:** Build the default from local fields, e.g. `const d = new Date(); const local = new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,10);` — ideally as one shared `todayISO()` helper reused by breeding.js.

### ✅ Date-only values render one day early for users at negative UTC offsets

**Closed by `3c79b9d`** — phase 1.1 — `parseLocalDate()` keeps a bare date on its own day

**Where:** `js/i18n.js`  
**Trigger:** Set the device timezone to any negative offset (e.g. America/New_York) and open the race log or health log containing a record dated "2025-04-12".  
**Effect:** fmtGregorian (line 444) and fmtHijri (line 454) do `new Date(iso)`; a bare "YYYY-MM-DD" is parsed as UTC midnight per spec, then formatted in local time. Verified in node with TZ=America/New_York: `new Date('2025-04-12').toLocaleDateString('en-GB',{year:'numeric',month:'short',day:'numeric'})` → "11 Apr 2025". Every stored date-only field (race date, health event date, hatch date, etc.) displays one day earlier than what was entered and saved, and the Hijri rendering shifts with it. Users at positive offsets (the Arabic-first target, UTC+2/+3) are unaffected, which is why it hides.  
**Suggested fix:** For date-only strings, parse the parts explicitly into a local Date (`new Date(y, m-1, d)`) rather than letting Date parse them as UTC; keep the current behaviour only for full datetime strings.

### ✅ Auto-filled dates use UTC, so between midnight and 03:00 local they record yesterday

**Closed by `3c79b9d`** — phase 1.1 — every date default goes through `todayISO()`

**Where:** `js/views/breeding.js`  
**Trigger:** In Jordan (UTC+3), at 01:00 local, add an egg, press "Mark hatched", or press "Wean".  
**Effect:** All defaults use `nowISO().slice(0, 10)` / `new Date().toISOString().slice(0, 10)` (lines 67, 101, 176, 213, 249), which is the UTC calendar day — three hours behind local in Amman. The egg's laid/hatch/wean dates are stamped with the previous day, and the hatch date is copied straight into the chick's permanent `hatchDate` when the chick is ringed (line 333). Same pattern in health.js:66.  
**Suggested fix:** Add a shared `todayISO()` helper that formats the local date (e.g. via getFullYear/getMonth/getDate padded, or sv-SE toLocaleDateString) and use it for every date-input default.

### ✅ Every automatic snapshot base64-encodes all photos and then throws them away

**Closed by `a5e2e79`** — phase 3 — `exportAll({includeMedia:false})`

**Where:** `js/db.js`  
**Trigger:** Happens on boot when a snapshot is due and every 12 h thereafter (`autoBackup()` from app.js), for any loft with photos/documents attached.  
**Effect:** `autoBackup()` calls the full `exportAll()`, which reads every media record and awaits `blobToDataURL(m.blob)` for each one — building base64 strings ~1.33× the size of all stored photos — and the very next line discards them (`payload.media = []`). A loft with 200 photos at 2 MB each churns ~400 MB of blob reads and ~530 MB of transient strings on the main thread just to store a media-free snapshot; on a phone this stalls the app or crashes the tab, twice a day.  
**Suggested fix:** Give `exportAll` an `{ includeMedia = true }` option and call `exportAll({ includeMedia: false })` from `autoBackup`, so media blobs are never read or encoded for snapshots.

### ✅ Replace-import erases the database before decoding the payload, so a mid-import failure destroys the user's data

**Closed by `a5e2e79`** — phase 3 — decode and validate everything first; snapshot to `backups`

**Where:** `js/db.js`  
**Trigger:** Tools → Import → mode "Replace everything" with a large export containing photos, on a device near its storage quota (or with any media entry whose data URL cannot be decoded).  
**Effect:** `importAll` clears all six stores up front, then inserts records one by one; media go through `await dataURLToBlob(m.dataURL)` (a `fetch` that rejects on a malformed data URL) and `idbPut` (which aborts with QuotaExceededError when storage runs out). Any such failure rejects out of `importAll` after the wipe, leaving a half-populated database — the original loft is already gone and nothing rolls it back. The caller in tools.js just shows a toast; the only remaining copy is an auto-snapshot, which itself contains no media.  
**Suggested fix:** Decode/validate the entire payload (all media blobs included) before clearing anything, and perform the wipe + writes so a failure can restore the previous contents (snapshot to `backups` first, or stage into temp stores and swap).

### ✅ Ancestors created inline from a parent picker get status 'stock', so the register mislabels and misfilters them

**Closed by `a932606`** — phase 1.5 — `newBird()` derives status from `external`

**Where:** `js/ui.js (birdPicker allowCreate, used by `js/views/bird-form.js) — visible in `js/views/birds.js`  
**Trigger:** In the bird form's Sire field type an unknown ring number and tap "+ Create a NEW record for …". Then go to the register and set the Status filter to "Stock".  
**Effect:** The stub is built with `newBird({ external: true, sex, name, rings })`, so `status` takes the default `'stock'` instead of `REFERENCE_STATUS`. In the register that bird renders a "Stock" status chip next to its "External" chip and is returned by the Status = Stock filter, mixed in with real loft birds — while an identically-external bird saved through the form's ownership selector gets `status: 'reference'` and renders "Pedigree reference". The same inconsistency is produced by the placeholder parents in bird-detail.js:65-66.  
**Suggested fix:** Pass `status: REFERENCE_STATUS` wherever `external: true` records are created (ui.js inline create and bird-detail.js placeholder parents), or have `newBird()` derive `status` from `external`.

### ✅ Add-sibling placeholder flow rewrites the bird's parents before the sibling exists, with no undo

**Closed by `a932606`** — phase 1.5 — writes deferred to the form's successful save

**Where:** `js/views/bird-detail.js`  
**Trigger:** Open a bird that has no sire and no dam → click '👥 Add sibling' → click 'Create parents & continue' in the modal → then hit browser Back, or navigate to any other tab, without saving the new sibling.  
**Effect:** The modal's primary action (lines ~63-79) creates two external placeholder birds, then does `bird.sireId = sire.id; bird.damId = dam.id; await saveBird(bird);` and only afterwards navigates to `#/bird/new?sire=…&dam=…`. The parent write is committed unconditionally and up front, so abandoning the new-bird form leaves the loft with two junk 'Unknown sire'/'Unknown dam' records that appear in the bird register (newBird gives them `status: 'stock'`, not REFERENCE_STATUS) and permanently re-parents the original bird to fabricated ancestors. That silently changes its pedigree everywhere downstream:  
**Suggested fix:** Defer the writes: pass a pending intent to the new-bird form (e.g. `#/bird/new?siblingOf=<id>`) and create the two placeholders plus the parent link only inside the form's successful save. If the eager write is kept, wrap it in `undoToast` that deletes the two placeholders and restores the original `sireId`/`damId`.

### ✅ egg.chickId is left dangling when the chick bird is deleted, stranding the egg

**Closed by `d6cc5ea`** — phase 1.4 — `deleteBird` cascades and unlinks eggs

**Where:** `js/views/breeding.js`  
**Trigger:** Ring a chick from an egg, then open that bird's page and delete it (or delete it from Tools' duplicate cleanup). Return to Breeding.  
**Effect:** db.deleteBird (db.js:189) detaches the bird only from other birds' sireId/damId — it never scans pair.rounds[].eggs[].chickId. eggRow (line 236) then does `getBird(egg.chickId)` → null, so the row renders a link labelled "Unknown" pointing at `#/bird/<deleted-id>`, which bounces to #/birds via renderBirdDetail's guard. Because `egg.chickId` is still truthy, both "Ring chick" and "Link an existing bird" stay hidden, so the egg cannot be re-ringed until the user notices the ⛓ button and unlinks.  
**Suggested fix:** In eggRow treat a missing getBird(egg.chickId) as unlinked (show the ring/link buttons plus a 'missing record' note); better, have deleteBird clear matching egg.chickId in state.pairs and include those pair snapshots in the undo payload.

### ✅ Deleting a bird orphans its race results, health events and breeding pairs

**Closed by `d6cc5ea`** — phase 1.4 — cascading delete with a complete undo snapshot

**Where:** `js/db.js`  
**Trigger:** Give a bird some race results (Races tab) and pair it in the Breeding tab, then open the bird's detail page and Delete → confirm, and let the undo toast expire.  
**Effect:** `deleteBird` (js/db.js:180-200) detaches the bird as a parent and deletes its media, but never touches `state.raceResults`, `state.healthEvents` or `state.pairs`. The rows survive pointing at a nonexistent id. Concretely: the Races tab renders the row forever with '—' in the bird column (js/views/races.js:53 null-checks `getBird`), so the result can no longer be attributed but still occupies the log and is exported by `exportAll`; and js/views/breeding.js:120-121 emits `<a href="#/bird/${pair.sireId}">` unconditionally even when `getBird(pair.sireId)` returned null, so the pair card shows a li  
**Suggested fix:** Either cascade-delete the dependent raceResults/healthEvents/pairs and include them in the snapshot returned to `restoreBird` (so undo stays complete), or leave them but null out `birdId`/`sireId`/`damId` and make consumers render dead references as plain text rather than links (breeding.js:120-121 should not emit an `<a>` when the bird lookup is null).
