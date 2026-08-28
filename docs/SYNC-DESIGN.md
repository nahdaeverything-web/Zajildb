# Zajil v1.9 — sync & accounts: design

**Status: DESIGN ONLY.** No code, no schema executed. This document is the thing
being approved.

The server becomes the source of truth; the phone keeps working offline and
reconciles on reconnect. Invite-only accounts, one fancier across several
devices. No sharing, no cross-loft features, no public pages.

The server contract is [SPIKE-SUPABASE.md](SPIKE-SUPABASE.md) and every rule
proven there is load-bearing here — particularly the **affected-row rule** (a
blocked write returns `200` with `0` rows) and the **404-no-inference rule**.

---

## 0. The shape of the thing

v1.8 built the parts a sync layer cannot reconstruct after the fact: an op log
with per-device monotonic `seq`, tombstones, provenance, device identity. v1.9
is the layer that carries them across the wire. Almost nothing about the
existing write path changes — that is the point of having done v1.8 first.

```
  ┌─ device ─────────────────────────────┐        ┌─ Supabase ──────────┐
  │  views → db.js write boundary        │        │                     │
  │            │                         │        │  sync_records       │
  │            ├→ IndexedDB (mirror)     │        │  (owner, store,     │
  │            ├→ oplog  ─── PUSH ──────────────→ │   record_id, data,  │
  │            └→ tombstones             │        │   deleted, …,       │
  │                                      │        │   server_seq)       │
  │  apply ←──────────── PULL ─────────────────── │                     │
  │  (origin 'sync', logs NO ops)        │        │  RLS: owner-only    │
  └──────────────────────────────────────┘        └─────────────────────┘
```

Two invariants hold the whole design together:

1. **The mirror stays complete and synchronous.** `getBird` must remain sync
   because the COI engine calls it thousands of times inside recursive memoised
   traversals (D3). Sync therefore *fills* IndexedDB; it never becomes a thing
   the engine awaits. This is the "keep a full local mirror" fork from
   V1.7-NOTES §2.1, chosen deliberately.
2. **A pulled change must never push back.** Applying remote data goes through
   the write boundary with `origin: 'sync'`, and `origin: 'sync'` logs **no
   op**. Without this the two devices ping-pong the same record forever.

---

## 1. Server schema

One sync table, not per-store tables.

**Rationale.** One RLS policy surface to get right instead of six. One cursor to
pull from instead of six interleaved ones. And the client schema can evolve —
a new field on a bird, a new store entirely — **without a server migration**,
because the row body is `jsonb`. In v1.9 the server is a *sync bucket*: it
stores and orders records without interpreting them. Relational, cross-loft
features (club mode) materialise server-side later, projecting out of these
rows or alongside them; that is a v2 concern and nothing here forecloses it.

The cost, stated honestly: the server cannot validate or query record contents,
so it cannot enforce Zajil's invariants. Those stay where v1.7 put them — at
the client write boundary. The server enforces *ownership and ordering only*.

### Migration SQL

To be run in the dashboard SQL Editor. **Verification query follows; run it and
paste the output — the proven workflow from the spike, where a policy set was
twice assumed applied and was not.**

```sql
-- ── Zajil v1.9 sync table ────────────────────────────────────────────────

create sequence if not exists public.sync_server_seq;

create table public.sync_records (
  owner       uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  store       text        not null,
  record_id   uuid        not null,
  data        jsonb       not null,
  deleted     boolean     not null default false,
  updated_at  timestamptz not null,
  device_id   uuid        not null,
  op_seq      bigint      not null,
  server_seq  bigint      not null,
  primary key (owner, store, record_id)
);

-- The pull cursor. Every pull is: where owner = auth.uid() and server_seq > ?
create index sync_records_owner_seq on public.sync_records (owner, server_seq);

-- server_seq is assigned by a trigger on INSERT **and** UPDATE.
-- An identity/default column will NOT do: it fires on insert only, so an
-- updated row would keep its original seq and be invisible to every cursor
-- already past it — a silently missed change, the worst kind.
create or replace function public.sync_assign_server_seq()
returns trigger language plpgsql as $$
begin
  -- Serialise sequence assignment PER OWNER. Without this there is a
  -- sequence-gap race: two devices push concurrently, the transaction holding
  -- server_seq = 1000 commits AFTER 1001 is already visible, and a pull with
  -- cursor = 1001 never sees row 1000 — until that row happens to be updated
  -- again, which may be never. A silently missed change.
  --
  -- One fancier's devices serialise against each other, which at this scale is
  -- a handful of writes; different owners hash to different lock keys and are
  -- unaffected. The lock is transaction-scoped and released on commit.
  perform pg_advisory_xact_lock(hashtext(new.owner::text));
  new.server_seq := nextval('public.sync_server_seq');
  return new;
end $$;

create trigger sync_records_seq
  before insert or update on public.sync_records
  for each row execute function public.sync_assign_server_seq();

alter table public.sync_records enable row level security;

-- Rejected alternative for the same race: pull with an OVERLAP — re-request
-- from (cursor - N) every time and rely on idempotent apply to absorb the
-- repeats. Rejected because N is a guess: too small and the race survives, too
-- large and every pull re-downloads and re-applies rows for nothing. It trades
-- a correctness guarantee for a tunable that can only be wrong. The advisory
-- lock removes the gap instead of hoping to out-run it.

-- ── grants ───────────────────────────────────────────────────────────────
-- No DELETE to anyone: a deletion is an UPDATE setting deleted = true.
-- The server never hard-deletes, so a tombstone can never be lost.
grant select, insert, update on table public.sync_records to authenticated;
-- (no grant to anon, by design)

-- Standing revoke pattern (SPIKE §3a): Postgres default privileges hand
-- TRUNCATE/TRIGGER/REFERENCES to anon and authenticated regardless of the
-- project's deny-by-default posture. TRUNCATE especially — RLS does not
-- apply to it, so the grant alone would let a client empty the table.
revoke truncate, trigger, references on table public.sync_records from anon, authenticated;

-- ── RLS: owner-only on all four verbs ────────────────────────────────────
create policy "sync_records owner select" on public.sync_records
  for select to authenticated
  using (owner = (select auth.uid()));

create policy "sync_records owner insert" on public.sync_records
  for insert to authenticated
  with check (owner = (select auth.uid()));

create policy "sync_records owner update" on public.sync_records
  for update to authenticated
  using (owner = (select auth.uid()))
  with check (owner = (select auth.uid()));

-- A delete policy exists so intent is explicit even though no DELETE is
-- granted: if a future release grants it, ownership is already enforced.
create policy "sync_records owner delete" on public.sync_records
  for delete to authenticated
  using (owner = (select auth.uid()));
```

### Verification query — run after, paste the output

```sql
-- 1. the trigger exists and fires on BOTH insert and update
select tgname, tgtype,
       pg_get_triggerdef(oid) as definition
from pg_trigger
where tgrelid = 'public.sync_records'::regclass and not tgisinternal;

-- 2. the four policies exist, and against which roles
select policyname, cmd, roles::text
from pg_policies
where schemaname = 'public' and tablename = 'sync_records'
order by policyname;

-- 3. grants: authenticated should hold exactly SELECT, INSERT, UPDATE.
--    anon should appear NOT AT ALL.
select grantee, string_agg(privilege_type, ', ' order by privilege_type) as privs
from information_schema.role_table_grants
where table_schema = 'public' and table_name = 'sync_records'
  and grantee in ('anon', 'authenticated', 'service_role')
group by grantee order by grantee;

-- 4. RLS is on
select relname, relrowsecurity from pg_class where relname = 'sync_records';
```

Expected: one trigger `INSERT OR UPDATE`; four policies for `authenticated`;
`authenticated` holding exactly `SELECT, INSERT, UPDATE`; **no `anon` row at
all**; `relrowsecurity = true`.

Per SPIKE §3b, `service_role` will hold no DML here either. That is fine —
nothing in v1.9 uses the secret key against this table. Only the admin user
creation does, and only on the server side.

---

## 2. Push — replaying the op log

The op log is already an ordered, complete record of what this device did. Push
replays it.

```
  idle ──(dirty ∨ timer ∨ reconnect)──→ collecting
  collecting ─→ take ops where seq > lastAckedSeq, ordered by seq, cap BATCH
             ─→ collapse to one upsert per (store, record_id): last op wins,
                because replaying three edits to one bird is three round trips
                for one final state. Ordering within the batch is preserved by
                taking the LAST op's data and the HIGHEST op_seq.
  sending    ─→ POST /rest/v1/sync_records
                Prefer: resolution=merge-duplicates, return=representation
  verifying  ─→ affected-row check (see below)
  acking     ─→ lastAckedSeq = highest seq in the batch; persist; prune
  ─→ more ops? collecting : idle
```

### 2a. The op → row mapping — and the timestamp rule that makes it correct

> **`updated_at` on the server row is the OP's `at` — the moment the operation
> happened. It is NEVER `record.updatedAt`.**

| Server column | Source |
|---|---|
| `owner` | omitted; defaulted server-side to `auth.uid()` |
| `store` | `op.store` |
| `record_id` | `op.recordId` |
| `data` | `op.record` (the full record; blobs already stripped by `opRecord`) |
| `deleted` | `op.op === 'delete'` |
| `updated_at` | **`op.at`** — operation time, never `record.updatedAt` |
| `device_id` | `op.deviceId` |
| `op_seq` | `op.seq` |
| `server_seq` | assigned by the trigger; never sent |

For a collapsed batch (several ops on one record reduced to one upsert), the
row takes the **last** op's `at`, `data` and `seq`.

#### Why this is not a detail

`restoreBird` **deliberately reinstates a record's original timestamps** — an
undo restores what was there; it is not a new edit. That is a v1.8 decision and
it is correct. But it means `record.updatedAt` can move *backwards*, and a sync
layer that trusted it would diverge permanently:

```
  10:00  A deletes a bird       → tombstone at 10:00, pushed
  10:01  B pulls the delete     → B applies it, writes its own tombstone
  10:05  A undoes the delete    → restoreBird reinstates updatedAt = 09:00
         push maps updated_at = 09:00   ← WRONG
  10:06  B pulls the restore    → 09:00 < B's tombstone at 10:00
                                → B SKIPS it. A has the bird. B does not.
                                → they never converge.
```

With `updated_at = op.at`, the undo's op happened at 10:05, beats B's 10:00
tombstone, and B restores the bird. The two devices converge.

The same rule governs **LWW comparison** (§4) and **tombstone comparison**
(§3): every timestamp decision in sync reads operation time. `record.updatedAt`
is a local bookkeeping field and plays no part in sync ordering.

#### Corollary — a winning record clears the tombstone

> When a pulled row with `deleted = false` **beats** a local tombstone (its
> `updated_at` is newer), applying it must **delete that tombstone**.

Leaving it would let the record be re-suppressed by the next merge-import or
comparison, and the device would flip between states. This mirrors v1.8's
`restoreBird`, which already clears tombstones on undo — the same rule reached
from the other direction.

**Test:** delete a bird on device A, let device B pull the delete, undo on A,
sync both — assert both devices hold the bird and neither retains a tombstone.

### The affected-row rule is the ack condition

SPIKE §4d: **a write blocked by RLS returns `200` with `0` rows.** So a `200`
alone must never advance `lastAckedSeq`.

> **Ack only when the response body contains a row for every record in the
> batch.** Count them. A short count means some records did not land, and the
> batch is retried rather than acked. Advancing the cursor on an unverified
> `200` would silently drop writes — the exact failure v1.7 and v1.8 exist to
> prevent.

#### A poison record must never deadlock the queue

"Retried rather than acked" is correct exactly once. Repeated forever it is a
deadlock: **one permanently-rejected record blocks all sync, for every store,
indefinitely** — and the user sees only a sync that never completes.

```
  short count ─→ retry the same batch (backoff)
              ─→ still short, 3 identical attempts?
                 ├→ batch > 1 : BISECT — split and retry each half
                 └→ batch = 1 : this record is poison
                                ├→ record it in syncAnomalies (loud, in الأدوات)
                                ├→ ACK it — advance past it
                                └→ continue with the rest
```

Bisection isolates the offender in `log₂(n)` round trips rather than `n`, and
for a healthy batch costs nothing because it never triggers.

> **An anomaly is loud but never a roadblock.** The alternative — a correct-
> looking queue that never drains — is worse than a visible, named failure the
> fancier can be asked about.

`syncAnomalies` is capped at **100 entries**, newest kept; it is a diagnostic
surface, not a log. Each entry records store, record id, the server's status
and body, and when it happened.

### Deletes

A delete is an upsert with `deleted = true` and the record's last-known `data`.
The body is kept, not nulled: it costs little and makes an undo or an audit
possible server-side later. The server never hard-deletes (no DELETE grant), so
a tombstone cannot be lost by any client bug.

### Compaction — the v1.8 deferral, now implemented

v1.8 wrote: *"compaction is a sync-time concern: ops can be dropped once
acknowledged by a server."* That time has come.

**Rule: an op with `seq <= lastAckedSeq` is prunable.** Pruning runs after a
successful ack, deleting acked ops in one pass, keeping the most recent
`OPLOG_KEEP = 500` regardless of ack state as a forensic tail. Tombstones are
**not** pruned — they are the resurrection protection and are cheap.

Until a device has ever synced, `lastAckedSeq = 0` and nothing prunes, so a
never-synced device keeps its full history exactly as in v1.8.

---

## 3. Pull — cursor on server_seq

```
  pull ─→ GET /rest/v1/sync_records
          ?select=*&server_seq=gt.<cursor>&order=server_seq.asc&limit=<PAGE>
       ─→ apply each row THROUGH the write boundary, origin 'sync'
       ─→ cursor = max(server_seq) seen; persist
       ─→ full page returned? pull again : done
```

`server_seq` is assigned per row by the trigger, so a row updated after our
cursor moves *above* it and is re-delivered. That is why the trigger must fire
on UPDATE and not merely on INSERT.

### Apply goes through the write boundary

Applying a remote record is a write, and it obeys every rule the local path
does: it goes through `saveBird` / the generic savers, it emits a change event,
and it keeps the in-memory mirror in step. It is *not* a raw `idbPut`.

Three differences, all deliberate:

- **`origin: 'sync'` logs no op.** Echo prevention. This is the single most
  important line in the design: a pulled change that logged an op would be
  pushed straight back, and two devices would trade the same record forever.
- **`origin: 'sync'` does NOT re-stamp the record.** `stamp()` writes
  `updatedAt = now` and *this* `deviceId` onto everything it touches. A pulled
  record put through it would become locally-authored with a fresh timestamp —
  it would then beat the very version it came from in every later comparison,
  and would claim this device as its last writer when another device wrote it.
  LWW would be corrupted and the audit trail falsified.

  > **A sync-apply writes the incoming record verbatim: `updatedAt`,
  > `deviceId`, `provenance` and all.** This follows the `restoreBird`
  > precedent — *"an undo restores exactly what was there; it is not a new edit
  > to re-judge"* — not the `saveBird` one. Applying a remote record is
  > likewise not authorship.

  **Test:** apply a pulled record, assert `updatedAt` and `deviceId` are
  byte-identical to what came over the wire.
- **Validation runs in `force` mode.** A record that already exists on the
  server is a historical fact, not a new edit to re-judge — the same reasoning
  that made `importAll` a `force` path in v1.7. A remote record that fails
  local validation is applied and **reported**, never silently dropped: it is
  logged to a `syncAnomalies` list surfaced in the dev panel. Dropping it would
  make the mirror diverge from the server invisibly, which is worse than
  holding a record the local rules dislike.

### Tombstone and resurrection semantics: identical to v1.8 merge-import

A pulled row with `deleted = true` deletes locally **and writes a tombstone**.
A pulled row with `deleted = false` is skipped if a local tombstone for it is
newer than the row's `updated_at` — the v1.8 rule, unchanged. Reusing it
exactly is deliberate: it is already tested, and a second, subtly different
deletion rule would be a defect generator.

---

## 4. Conflicts — per-record last-write-wins

Both sides carry the op that produced the record. Compare **the ops' `at`
timestamps**; tie-break on `deviceId` (lexicographic — arbitrary but stable,
and a tie means the same millisecond on two devices).

Per record, not per field. Per-field merge is defensible for a shared document;
for one fancier editing their own bird on two devices it adds machinery to
resolve a conflict that is nearly always "the same person edited the same bird
twice, the later one is what they meant".

### The accepted imperfection: device clock skew

LWW on a wall-clock timestamp is only as good as the clocks. A device set
three days fast wins every conflict until its clock is corrected.

**Why this is tolerable here, and would not be elsewhere:** the two devices
belong to *the same person*. There is no adversary, no competing editor, and no
cross-user data. The realistic failure is a fancier seeing a slightly stale
edit win on one device — annoying, visible, and fixable by editing again. It
is not data loss: the losing version remains in the op log and in the server
row's history of updates.

**What is NOT affected by skew** — worth stating because it was the reason
v1.8 chose `seq` over `updatedAt`:

> **Per-device ordering is preserved regardless of clocks.** Push replays a
> device's ops in `seq` order, and `seq` is monotonic per device. So
> *delete-then-undo stays correct*: the undo is a later op on the same device
> and is replayed after the delete, whatever the timestamps say. Cross-device
> conflicts use `at`; same-device sequencing never does.

If skew proves to be a real problem in the pilot, the upgrade path is a server
-assigned logical clock (`server_seq` already is one) — recorded here so the
option is known, not scheduled.

---

## 5. Auth — invite-only

Accounts are created by us through the admin API (SPIKE §2). **Public signups
stay disabled** — SPIKE §4f records that as a required production setting, and
it is what makes "invite-only" true rather than aspirational.

```
  sign in  : POST {URL}/auth/v1/token?grant_type=password
             { apikey: <publishable> }                      → access + refresh
  refresh  : POST {URL}/auth/v1/token?grant_type=refresh_token
  data     : { apikey: <publishable>, Authorization: Bearer <access token> }
```

An API key is **never** an `Authorization: Bearer` value (SPIKE §1). The
secret key appears nowhere in the client, ever.

Access tokens live 3600 s; the refresh grant returns a **new refresh token
each time**, so the stored one must be replaced on every refresh — the old one
is spent.

Tokens are stored in `settings`, which is already out of sync scope (v1.8) —
they are per-device by definition and must not travel. See §9 for the export
exclusion that keeps them there.

**Multi-instance refresh race.** The installed app and a browser tab on the
same device share one IndexedDB, so both may attempt a refresh with the same
token and one loses. Supabase applies a **reuse grace interval** to refresh
tokens for exactly this case, so the loser's token is not immediately invalid.
v1.9 relies on that rather than building a cross-instance lock: on a refresh
rejection the instance re-reads the stored tokens once before concluding the
session is dead, which resolves the ordinary case where the other instance had
already written a fresh pair.

### Offline behaviour — the part that matters most

> **A logged-in device works fully offline on its mirror. Auth is required to
> SYNC, not to function.**

Every existing feature — the register, pedigrees, COI, breeding, certificates —
runs against IndexedDB and does not know sync exists. If the token cannot be
refreshed, sync stops and the app does not. This is not a fallback mode; it is
the same code path the app has always used.

`actorId` on ops becomes the authenticated user id once signed in. Ops written
before sign-in keep `actorId: null` and are pushed as-is: they were genuinely
made by an unidentified actor on this device, and rewriting history to claim
otherwise would be a lie in the audit trail.

---

## 6. First-login flows

**Fresh device, no local data.** Sign in → full pull from cursor 0 → done. The
simple case.

**Device with existing local data.** The records were made before this device
knew about an account. They are the fancier's records and must not be lost.

> On first successful sign-in, every local record is enqueued as a synthetic op
> (`origin: 'user'`, current device, current `seq`) whose **`at` is the
> record's own `updatedAt` — NOT `now()`**. Then normal push runs; nothing is
> special-cased in push itself.

#### Why `at` must not be `now()`

A laptop last used months ago holds stale copies. Stamping its synthetic ops
with today's time would make every one of them **beat the fresher server data**
in LWW (§4) — the stale device would silently overwrite edits the fancier made
on their phone last week, simply by logging in.

Using each record's own `updatedAt` says what is true: *this is what this
device knew, as of when it knew it.* Fresh server data then wins, which is the
correct outcome.

This is the one place `record.updatedAt` legitimately feeds an op's `at` — and
it is not an exception to §2a but an instance of it: for a record that has
never been synced, the last local write **is** the operation being replayed.

**Test:** a stale device holding an old copy signs in; assert the server's
newer version wins and the stale copy does not overwrite it.

Ordering matters: **push before pull** on first login. Pulling first would apply
server rows over local records and the subsequent push would send back
server-derived data, quietly discarding local edits. Pushing first means both
sides are present and the conflict rule decides, per record.

### The collision story, honestly

Same fancier, two devices, both with pre-sync data, both logging in.

Records have **client-generated UUIDs** (v1.7 D-note). Two devices that never
synced generated *different* ids for the same real bird. So:

> **The same physical bird entered separately on two devices becomes two
> records after the first sync.** Not a merge conflict — two rows with different
> primary keys, both valid, both surviving.

This is not solvable automatically without guessing, and guessing would be
worse: ring number is the natural business key but is deliberately **not**
identity (birds carry several rings, rings get reused, and BACKLOG already
tracks duplicate-ring warnings as warnings, not errors).

**What v1.9 does:** after the first sync completes on a device that had local
data, run the existing **duplicate finder** (Tools → طيور مكررة, v1.6) and
surface a one-time notice: *"تمت المزامنة. وُجدت N حلقة مكررة — راجعها."* The
tool already groups by normalised ring and shows which copy carries links.
Resolution is the user's, which is correct: only they know whether two records
are one bird.

**What v1.9 does not do:** automatic merge. Recorded as a known limitation, not
an oversight.

---

## 7. Media — metadata syncs, blobs do not

**Scope decision, explicit.**

Media *metadata* rows (id, birdId, kind, subtype, name, addedAt) sync as
ordinary records. **Blobs do not sync in v1.9.**

Reasons: blobs are large and slow on the connections this product targets;
Supabase Storage needs its own upload/download state machine with resumability;
and the spike's storage proof, while green, covers ownership, not transfer of
many megabytes over a weak link.

**Consequence, made visible rather than hidden:** a device may hold a media row
whose blob lives on another device. The UI shows a placeholder in the gallery —
*"الصورة على جهاز آخر"* — instead of a broken image. The record is real; the
bytes are elsewhere.

**Follow-up: v1.9.x**, using the storage design already proven in SPIKE §6
(private bucket, path-prefix ownership `<user-id>/<media-id>`).

---

## 8. The db.js split

v1.9 is the release where `db.js` splits. It is 866 lines and about to grow a
sync layer.

**The facade rule: `js/db.js` remains and re-exports the same API. No view
changes a single import.** The invocation contract is stable; only internals
move.

```
  js/db.js            facade — re-exports everything, adds nothing
  js/db/storage.js    openDB, idb*, state mirror, stamp, change events
  js/db/records.js    newBird, saveBird, checkBird, deleteBird, restoreBird,
                      makeGeneric + Pairs/Races/Health/Lofts, media
  js/db/oplog.js      logOp, nextSeq, tombstones, getOpsSinceSeq, pruning
  js/db/io.js         exportAll, importAll, exportBirdWithAncestry, backups
  js/db/sync.js       NEW — push, pull, cursors, auth token handling
```

All 44 current exports keep their names and signatures.

### The guards must be updated deliberately, in the same commit

Three guards key on the literal `js/db.js`:

| Guard | Current allow | Becomes |
|---|---|---|
| no view writes to IndexedDB | `rel === 'js/db.js'` | `rel === 'js/db.js' \|\| rel.startsWith('js/db/')` |
| `logOp` never escapes | same | same |
| no raw `oplog`/`tombstones` reads | same | same |

> **Every guard is re-proven to fire after the split**, by reintroducing each
> violation in a view and confirming the failure — exactly as in v1.7 and v1.8.
> A guard whose allow-list was widened without re-proving is a guard that may
> now allow everything.

### The v1.8 enumeration matrix extends, it does not bend

`tests/e2e/op_enumeration.py` asserts *one op per record touched* for every
mutation type. Sync introduces two cases that would otherwise look like
failures of that rule, so the matrix gains them explicitly rather than having
the rule loosened:

| Case | Expected ops |
|---|---|
| apply a pulled record (`origin: 'sync'`) | **ZERO** — mutation without an op, by design (echo prevention) |
| apply a pulled delete (`origin: 'sync'`) | **ZERO** — the tombstone is written, no op |
| first-login synthetic op | **one op, no mutation** — the record already exists locally; the op is enqueued to describe it |

These are the only two places in the codebase where mutations and ops do not
correspond one-to-one, and both are deliberate. Naming them in the matrix means
a *third* such case cannot appear by accident without failing a test.

A **new** guard is added with the sync layer:

> **`origin: 'sync'` must never reach `logOp`.** Echo prevention is the
> load-bearing invariant of the pull path, and it is one careless line from
> being broken. Enforced both as a source scan and as a behavioural test
> (apply a pulled record, assert the op count did not change).

---

## 9. Settings keys added

All in `settings`, which is out of sync scope — these are per-device by nature.

| Key | Purpose |
|---|---|
| `authAccessToken` | current access token (3600 s) |
| `authRefreshToken` | replaced on every refresh; the old one is spent |
| `authUserId` | the signed-in user id; becomes `actorId` on new ops |
| `authEmail` | for the sync-status display |
| `syncCursor` | highest `server_seq` applied |
| `lastAckedSeq` | highest local op `seq` the server has verifiably accepted |
| `lastSyncAt` | ISO timestamp of the last successful cycle |
| `lastSyncError` | last error key + timestamp, or null |
| `syncEnabled` | user can turn sync off and keep working locally |
| `syncAnomalies` | capped at 100 entries, newest kept — a diagnostic surface, not a log |

### Tokens must never leave the device

`authAccessToken` and `authRefreshToken` are bearer credentials. If they
reached an export, they would travel in every JSON backup a fancier shares —
over WhatsApp, to a club administrator, anywhere — and whoever received the
file could act as that user until the tokens expired or were rotated.

**Current behaviour, checked in the source rather than assumed:**

`exportAll()` builds an explicit key list — `format`, `version`, `exportedAt`,
`tombstones`, `lofts`, `birds`, `pairs`, `raceResults`, `healthEvents`,
`media`. **`settings` is not among them**, so no setting of any kind is
exported today. `autoBackup()` wraps `exportAll({ includeMedia: false })` and
adds only `kind`, so the `backups` store inherits the same exclusion.

> **So tokens do not leak today. This amendment is a REGRESSION GUARD, not a
> fix.** The risk is a future release adding `settings` to an export for some
> reasonable-sounding purpose — remembering a COI depth across a restore, say —
> and carrying credentials out with it.

**Required:** a test asserting that **no export payload and no backups-store
snapshot contains any key beginning `auth`**, run against a database where a
user is signed in and the tokens are genuinely present. Belt and braces: if a
future change ever does export settings, the `auth*` keys are filtered at the
export boundary, and the test fails first if that filter is forgotten.

### DB_VERSION impact: none

`DB_VERSION` **stays at 2**. No new object store is required: sync state lives
in `settings`, and `syncAnomalies` is a settings-held array. Nothing about the
existing stores changes.

Stated explicitly because the instinct is to bump it; there is nothing to
migrate, and a bump would trigger an upgrade path for no reason.

---

## 10. Sync status UI — Arabic, minimal

One row in the header, plus a section in الأدوات. The design principle:
**sync is infrastructure and should be almost invisible when it works.**

| State | Header | Meaning |
|---|---|---|
| synced | `✓ متزامن` (muted) | everything pushed and pulled |
| syncing | `⟳ جارٍ المزامنة…` | a cycle is running |
| pending | `⌁ N تغييرًا بانتظار المزامنة` | offline or paused, work is queued |
| offline | `⚡ دون اتصال — يعمل محليًا` | reassurance, not an error |
| error | `⚠ تعذّرت المزامنة` + a link to الأدوات | needs attention |

Offline is deliberately **not** styled as an error. It is the normal condition
this product was built for, and a red banner every time a fancier walks into a
loft would train them to ignore warnings.

الأدوات gains a **المزامنة** card: signed-in email, last sync time, pending op
count, an explicit «مزامنة الآن» button, a sync-off toggle, and the last error
in full when there is one.

---

## 11. Open questions — answered

**Batch size.** **200 records per push**, **500 per pull page.** Push batches
are smaller because a failed batch is retried whole, and 200 records of `jsonb`
is a comfortable request on a weak connection. Pull is cheaper to redo and
benefits from fewer round trips. Both are constants, tuned once against the
real latency profile (SPIKE §5: ~84 ms median CRUD from Amman).

**Backoff curve.** Exponential with jitter: **2 s, 4 s, 8 s, 16 s, 32 s, 60 s**,
then every 60 s, each with ±25 % jitter. Cap at 60 s so a device that has been
offline for hours reconnects within a minute of the network returning. Jitter
because several devices coming back on the same wifi should not retry in
lockstep. Reset to 2 s on any success.

**Reconnect detection.** Three signals, cheapest first:
1. `window.addEventListener('online')` — instant when it fires, but lies often
   enough that it cannot be the only one.
2. A **60 s heartbeat timer** while pending work exists.
3. **On `visibilitychange` to visible** — the phone coming out of a pocket is
   the single most likely moment for a fancier to have walked back into signal.

Never a network poll for its own sake: it costs battery and proves nothing that
attempting the actual sync would not.

**Token refresh fails mid-sync.** Distinguish two cases, because conflating
them is how apps log people out for no reason:

- **Network failure** (fetch throws, or 5xx): not an auth problem. Stop the
  cycle, keep the tokens, back off, retry. The user is told nothing.
- **Genuine rejection** (400/401 with an auth error body): the refresh token is
  spent or revoked. Clear tokens, set state to `error`, and surface *"انتهت
  الجلسة — سجّل الدخول من جديد"* in the header and الأدوات.

In both cases **the in-flight batch is abandoned, not acked**. `lastAckedSeq`
does not move, so the ops are still there and replay on the next successful
cycle. Push idempotency (upsert on the primary key) makes a re-sent batch
harmless.

**Surfacing errors without alarming.** Three rules:

1. **Offline is not an error.** It gets its own calm state.
2. **A transient failure is silent** until it has persisted through several
   backoff rounds — roughly **two minutes** — because most resolve themselves
   and a warning that clears itself teaches users to ignore warnings.
3. **Only two things ever interrupt:** session expired (needs a password) and
   a persistent server rejection (needs us). Everything else lives in الأدوات
   for the curious.

The wording avoids blame and jargon: *"تعذّرت المزامنة — سنحاول تلقائيًا"*
rather than an HTTP status. The status code goes in الأدوات, where someone
debugging will look for it.

---

## 12. Phase plan

Tests first, one commit per phase, same reporting as v1.8 (verbatim `tee`'d
tails, `git diff --stat`, node and browser counts per phase). Baseline: **96
node / 287 browser**.

| Phase | Content | Node | Browser |
|---|---|---|---|
| **0** | This document | 96 | 287 |
| **1** | `db.js` split + facade; guards updated and **re-proven**; zero behaviour change | 96 → ~100 | 287 → ~292 |
| **2** | Auth: sign-in, refresh loop, token storage, offline-tolerant | ~104 | ~305 |
| **3** | Push: op→row mapping, batching, affected-row-verified ack, poison bisection, `lastAckedSeq`, compaction | ~114 | ~326 |
| **4** | Pull: cursor, verbatim apply via `origin: 'sync'`, echo-prevention guard, tombstone-clearing corollary | ~120 | ~346 |
| **5** | Conflicts (incl. the delete+undo convergence test), first-login flows with `updatedAt`-based synthetic ops, the duplicate notice | ~126 | ~362 |
| **6** | Sync-status UI, الأدوات card, error surfacing | ~126 | ~365 |
| **7** | Docs: HANDOFF, BACKLOG, WRITEPATH regenerated | ~126 | ~365 |

Phase 1 is deliberately first and deliberately behaviour-free: **splitting a
file and changing what it does in the same release is how a refactor hides a
bug.** Its success criterion is that all 287 browser assertions pass unchanged.

Counts beyond phase 1 are estimates and will be reported as actuals.

---

## 13. What v1.9 is NOT doing

Stated so scope creep has to argue with a document.

- **No blob sync.** Metadata only; v1.9.x follow-up (§7).
- **No sharing, no cross-loft features, no public pages.** One fancier, several
  devices.
- **No club mode.** `loftId` remains stamped and unenforced.
- **No per-field merge.** Per-record LWW (§4).
- **No automatic duplicate merging** after a two-device first sync (§6).
- **No server-side validation.** The server orders and owns; it does not
  interpret. Invariants stay at the client write boundary.
- **No public signup.** Invite-only, permanently.
- **No `supabase-js`.** Plain `fetch()`; the dependency-free rule stands.
- **No async engine.** `getBird` stays synchronous; the mirror stays complete.
- **No DB_VERSION bump.** Nothing to migrate (§9).
- **No real-time subscriptions.** Poll and reconcile. Realtime is a later
  optimisation and would add a second, differently-shaped delivery path before
  the first one is proven.
- **No conflict UI.** LWW resolves silently; the losing version survives in the
  op log. A conflict-resolution screen for a single owner editing their own
  data would be ceremony.

---

## 14. Risks

| Risk | Mitigation |
|---|---|
| Echo loop (pulled change pushes back) | `origin: 'sync'` logs no op; enforced by a source guard **and** a behavioural test |
| Cursor advances past unapplied data | Cursor persists only after a page applies completely |
| Ack on an unverified `200` | Affected-row count is the ack condition (SPIKE §4d) |
| Clock skew decides a conflict wrongly | Accepted (§4); per-device order unaffected; `server_seq` is the upgrade path |
| Op log grows forever | Compaction at `lastAckedSeq`, keeping a 500-op tail |
| Two devices, same bird, different UUIDs | Surfaced through the existing duplicate finder; user resolves (§6) |
| `*.supabase.co` blocked regionally | Custom domain **before** any Gulf pilot — SPIKE standing note |
| A split that quietly changes behaviour | Phase 1 is refactor-only; success = 287 browser assertions unchanged |
| Delete+undo diverges across devices | `updated_at` is the OP's `at`, never `record.updatedAt` (§2a); convergence test |
| Sync-apply re-stamps and falsifies authorship | `origin: 'sync'` writes verbatim — no stamp, no op (§3) |
| Stale device overwrites fresher server data on first login | Synthetic ops carry each record's own `updatedAt` as `at` (§6) |
| One poison record blocks all sync forever | Bisect after 3 short counts, isolate to `syncAnomalies`, ack the rest (§2) |
| Tokens leak into a shared backup | Not exported today (checked); regression guard test on `auth*` keys (§9) |
| Sequence gap silently skips a row | `pg_advisory_xact_lock` per owner in the trigger (§1) |
