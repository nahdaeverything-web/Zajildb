-- ════════════════════════════════════════════════════════════════════════════
-- Zajil — sync schema, trigger, grants and row-level security, as ONE file.
--
-- CHECKED AGAINST THE LIVE PROJECT ON 2026-11-18, AND IT MATCHED. Samir ran
-- supabase/sync-schema-check.sql (read-only, one statement) in the SQL Editor of
-- the real project: 17 rows; rows 1-16 ok = true, each found value equal to its
-- expected value; row 17 (information only): service_role holds REFERENCES,
-- TRIGGER, TRUNCATE on sync_records. PART 1 itself has still NOT been executed
-- from this file on Supabase Postgres — the project was built earlier, by Route A;
-- what is established is that the project's catalog is what this file describes.
-- Written 2026-11-17, accepted 2026-11-18. Also checked on 2026-11-18 on PGlite
-- (PostgreSQL 18.6 in WebAssembly) with stubs for the auth schema and the three
-- roles: PART 1 executes; PARTS 2 and 3 return what they say they expect; PART 1
-- a second time stops at "already exists". That is a syntax and catalog check.
-- The same checks as ONE statement, for the SQL Editor: supabase/sync-schema-check.sql.
--
-- SOURCE: docs/SYNC-DESIGN.md §1 «Migration SQL» and «Verification query»
--         (last commit touching that file: 72146c6 2026-11-13).
-- PART 1 and PART 2 below are those two code blocks VERBATIM — extracted by script,
-- not retyped (sha256 of each block is printed beside it so a later edit shows).
-- The two amendments the prose records — record_id as text, and the sequence
-- usage grant — and the last-write-wins guard are already folded into PART 1 by
-- the design document itself; nothing was added to it here.
-- PART 3 is NOT in the design prose. It is three extra read-only checks proposed
-- here, each for a fault the prose says the original four queries could not see.
--
-- WHAT THIS FILE IS FOR
--   · A FRESH project: PART 1 once, in the dashboard SQL Editor, then PART 2 (and
--     PART 3 if accepted), and paste the output.
--   · The EXISTING project (Route A, DF-3: it is production and is upgraded in
--     place): do NOT run PART 1 — `create table` and `create trigger` and the four
--     `create policy` statements have no IF NOT EXISTS and will stop with
--     "already exists". That is deliberate: this file never alters live data.
--     PART 2 and PART 3 are read-only and can be run against it at any time.
--   · Introspection proves objects EXIST, never that a write SUCCEEDS (the SQL
--     Editor runs as postgres). The end-to-end check stays tests/e2e/push_live.py.
-- ════════════════════════════════════════════════════════════════════════════


-- ════════ PART 1 — SCHEMA, TRIGGER, GRANTS, RLS  (verbatim · sha256 6662a4be98ccb940) ════════

-- ── Zajil v1.9 sync table ────────────────────────────────────────────────

create sequence if not exists public.sync_server_seq;

create table public.sync_records (
  owner       uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  store       text        not null,
  -- TEXT, not uuid. Client record ids are OPAQUE STRINGS to the server: it
  -- scopes by `owner`, never parses an id, and never joins on one. Typing this
  -- `uuid` enforced nothing the server relies on and offered exactly one
  -- behaviour — a permanently, silently stalled queue — the moment a client
  -- held an id that was not a uuid. See the amendment below.
  record_id   text        not null,
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

-- server_seq is assigned by a trigger on INSERT **and** UPDATE, which also
-- enforces §4's last-write-wins (see the body).
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

  -- ── §4 LAST-WRITE-WINS, enforced where it can be authoritative ──
  -- A client push is a blind upsert: POST with resolution=merge-duplicates
  -- overwrites whatever is there. So a device that has been offline for
  -- months replaces fresher data simply by pushing, and NO amount of
  -- client-side care can prevent it — the client cannot see what it is about
  -- to overwrite. This is the only place the comparison can be trusted.
  --
  -- The tie-break matches the client's exactly (the lexicographically greater
  -- device_id wins), so both sides reach the same verdict without talking to
  -- each other.
  if TG_OP = 'UPDATE' and (
       new.updated_at < old.updated_at
       or (new.updated_at = old.updated_at and new.device_id <= old.device_id)
     ) then
    new := old;                       -- keep the winner's body
  end if;

  -- Advances on EVERY write, including one whose body was rejected above, so
  -- the loser re-pulls the winner rather than sitting on a version the server
  -- refused.
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

-- REQUIRED, and missing from the first version of this migration. The trigger
-- calls nextval() and is NOT security definer, so it runs as the CALLER. With
-- no usage on the sequence, every insert fails 403 "permission denied for
-- sequence sync_server_seq" and the table accepts nothing at all.
-- Granting usage is safe: a client cannot reach nextval() except through this
-- trigger, and the trigger overwrites any client-supplied server_seq anyway.
grant usage on sequence public.sync_server_seq to authenticated;
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


-- ════════ PART 2 — VERIFICATION QUERY  (verbatim · sha256 f134bd42233476ca) ════════
-- Expected (the design's own words): one trigger `INSERT OR UPDATE`; four policies
-- for `authenticated`; `authenticated` holding exactly `SELECT, INSERT, UPDATE`;
-- no `anon` row at all; `relrowsecurity = true`.

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


-- ════════ PART 3 — PROPOSED ADDITIONS, read-only  (NOT in the design prose) ════════

-- 5. the sequence grant — the fault of v1.9 Phase 3: all four queries above were
--    green while every insert failed 403 "permission denied for sequence".
--    Expected: authenticated = true, anon = false.
select r.rolname,
       has_sequence_privilege(r.rolname, 'public.sync_server_seq', 'USAGE') as can_use_sequence
from pg_roles r
where r.rolname in ('anon', 'authenticated')
order by r.rolname;

-- 6. the column types the two amendments depend on.
--    Expected: record_id = text (opaque client ids), device_id = uuid (the
--    tie-break), data = jsonb, updated_at = timestamp with time zone.
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public' and table_name = 'sync_records'
order by ordinal_position;

-- 7. the trigger function carries the per-owner lock and the last-write-wins
--    guard, and is NOT security definer.
--    Expected: has_owner_lock = true, has_lww_guard = true, security_definer = false.
select p.proname,
       p.prosecdef                                            as security_definer,
       pg_get_functiondef(p.oid) like '%pg_advisory_xact_lock%' as has_owner_lock,
       pg_get_functiondef(p.oid) like '%new := old%'            as has_lww_guard
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.proname = 'sync_assign_server_seq';
