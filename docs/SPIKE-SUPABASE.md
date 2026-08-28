# Supabase spike — findings

**Status:** steps 1–5 **proven**. Storage (stretch) **blocked, diagnostic pending** —
this document will be amended in a follow-up commit when it resolves.

A throwaway proof, not app code. None of the spike scripts live in this repo;
they ran in `~/zajil-spike/`. What is recorded here is the **contract v1.9 will
implement**, plus the surprises worth knowing before writing real sync code.

The spike ran against a disposable Supabase project whose secret key and
database password are being rotated after completion. Endpoints below use
`{SUPABASE_URL}` rather than that project's host, because the contract is the
deliverable — the project is not.

---

## The central question, answered

**Zajil is dependency-free vanilla JS, so v1.9 must talk to Supabase with plain
`fetch()` — no `supabase-js`.** That works. Auth, token refresh, RLS-enforced
CRUD and deny-by-default all behave correctly over plain `fetch` with no client
library, no build step, and no npm dependency. Nothing in the spike required
`supabase-js` or suggested it would.

---

## 1. Header shapes — v1.9's contract

This project uses Supabase's **new API keys** (`sb_publishable_…` /
`sb_secret_…`), not the legacy `anon` / `service_role` JWTs. The header rules
differ from most tutorials, which still show the old scheme.

**An API key goes in `apikey` ONLY. It is never an `Authorization: Bearer`
value.** `Authorization: Bearer` carries the **user's access token** and
nothing else. Verified empirically on every endpoint used:

| Purpose | Headers |
|---|---|
| Admin (create user) | `{ apikey: <secret> }` — **no `Authorization` header at all** |
| Auth (password / refresh grant) | `{ apikey: <publishable> }` — no `Authorization` |
| Data API, signed out | `{ apikey: <publishable> }` |
| Data API, signed in | `{ apikey: <publishable>, Authorization: Bearer <user access token> }` |
| Storage, signed in | `{ apikey: <publishable>, Authorization: Bearer <user access token> }` |

Key roles:

- **publishable** — low-privilege client key. RLS applies. Takes the `anon`
  role when no user token accompanies it. **Safe in a browser**; that is its
  purpose.
- **secret** — privileged, bypasses RLS. **Server-only, forever.** See the
  standing notes.

---

## 2. Auth

Endpoints (plain `fetch`, JSON bodies):

```
POST {SUPABASE_URL}/auth/v1/token?grant_type=password
     headers { apikey: <publishable>, Content-Type: application/json }
     body    { email, password }

POST {SUPABASE_URL}/auth/v1/token?grant_type=refresh_token
     headers { apikey: <publishable>, Content-Type: application/json }
     body    { refresh_token }

POST {SUPABASE_URL}/auth/v1/admin/users        ← SECRET KEY, server only
     headers { apikey: <secret>, Content-Type: application/json }
     body    { email, password, email_confirm: true }
```

**Token lifetimes**

| | |
|---|---|
| access token | **3600 s (60 min)**, JWT, ~796 chars |
| JWT `exp - iat` | 3600 s — matches `expires_in`, no discrepancy |
| JWT `role` | `authenticated` |
| JWT `sub` | the user id — confirmed equal to the id returned at creation |
| refresh token | short opaque string (~12 chars), rotated on every refresh |

The refresh grant returns **both** a new access token and a **new refresh
token**. v1.9 must store the new refresh token each time; the old one should be
assumed spent.

**Users are created already-confirmed** (`email_confirm: true`). Without it the
password grant fails with "email not confirmed" — the admin API does not
confirm implicitly.

---

## 3. Schema and the deny-by-default posture

The project was created with **"Automatically expose new tables" DISABLED** and
**"Enable automatic RLS" ENABLED**. A new table is therefore invisible to the
Data API until granted explicitly. This is the standing pattern for every
future table.

```sql
create table public.spike_birds (
  id         uuid primary key,                 -- client-generated, as Zajil already does
  owner      uuid not null references auth.users (id) on delete cascade,
  name       text,
  ring       text,
  created_at timestamptz default now()
);

alter table public.spike_birds enable row level security;

-- Data API grants. `authenticated` only — anon is deliberately granted NOTHING.
grant select, insert, update, delete on table public.spike_birds to authenticated;
-- (no grant to anon, by design)

create policy "spike_birds owner select" on public.spike_birds
  for select to authenticated
  using (owner = (select auth.uid()));

create policy "spike_birds owner insert" on public.spike_birds
  for insert to authenticated
  with check (owner = (select auth.uid()));

create policy "spike_birds owner update" on public.spike_birds
  for update to authenticated
  using (owner = (select auth.uid()))
  with check (owner = (select auth.uid()));

create policy "spike_birds owner delete" on public.spike_birds
  for delete to authenticated
  using (owner = (select auth.uid()));
```

`id` has **no default** — the client supplies the uuid. That matches how Zajil
already mints ids, so v1.9 can push its own without round-tripping for them.

### 3a. REQUIRED after every `create table`: revoke the implicit grants

**Postgres default privileges granted `TRUNCATE`, `TRIGGER` and `REFERENCES` on
the new table to both `anon` and `authenticated`, despite the deny-by-default
posture.** The dashboard toggle does not prevent this.

**`TRUNCATE` is the dangerous one: RLS does not apply to it.** A role holding
`TRUNCATE` can empty the table regardless of any policy.

Standing pattern for **all** future tables, immediately after creation:

```sql
revoke truncate, trigger, references on table public.<name> from anon, authenticated;
```

Then verify `authenticated` holds exactly `SELECT, INSERT, UPDATE, DELETE` and
`anon` holds nothing. This was found and corrected during the spike.

### 3b. `service_role` holds no DML on new tables either

With "Automatically expose new tables" disabled, **`service_role` also receives
no DML grants** on a newly created table — only `TRIGGER` / `TRUNCATE` /
`REFERENCES`. Harmless for the data tests (they all run as users), but it means
**an admin-side operation using the secret key against a new table will fail
with `42501`**. That is the cause to check first, and it must not be granted
around silently.

Scope note: this applies to `public`. The `storage` schema was unaffected — the
secret key created a storage bucket without issue.

---

## 4. RLS — deny-by-default proof

All plain `fetch` against `{SUPABASE_URL}/rest/v1/spike_birds`. **15 assertions,
all passing.**

| Case | Result |
|---|---|
| **4a** publishable key, **no user token** | `GET` → **HTTP 401**, `{"code":"42501","message":"permission denied for table spike_birds"}`. `POST` → **401**, same code. |
| **4b** user A inserts 3 | `201`, then `GET` returns **exactly 3**, all `owner = A` |
| **4c** user B inserts 1 | `201`, then `GET` returns **exactly 1**, **none of A's** |
| **4d** B updates/deletes A's row | `PATCH` → **200, 0 rows affected**. `DELETE` → **200, 0 rows affected**. A's data verified unchanged. |
| **4e** A inserts with `owner = B` | **HTTP 403**, `{"code":"42501","message":"new row violates row-level security policy for table \"spike_birds\""}` |
| **4f** `POST /auth/v1/signup`, fresh email | **HTTP 422**, `{"error_code":"signup_disabled","msg":"Signups not allowed for this instance"}` |

### 4a is refused, not merely empty — and that is stronger

Because `anon` holds **no grant at all**, an unauthenticated request is refused
at the **grant layer** with `42501`, rather than passing RLS and returning an
empty set. Denial before the query even runs is a stronger guarantee than
filtering, and it is what the posture in §3 buys.

Note the response `hint` helpfully suggests `GRANT SELECT ON public.spike_birds
TO anon`. **Do not.** That advice would convert this refusal into an empty set
and weaken the model.

### 4d — THE CONTRACT RULE v1.9 MUST FOLLOW

**A write blocked by RLS returns `HTTP 200` with `0` rows affected, not an
error.** RLS filters the target row out before the write, so the statement
succeeds against nothing.

> **v1.9 must check the affected-row count, never the status code, to decide
> whether a write happened.** A `200` from `PATCH` or `DELETE` does not mean the
> record changed.

Use `Prefer: return=representation` and inspect the returned array's length.
Getting this wrong would make Zajil report successful syncs that silently wrote
nothing — the exact class of failure the v1.7 and v1.8 passes were built to
prevent.

### 4f — `signup_disabled` is REQUIRED in production

Public signup was disabled in the dashboard before the test. `POST
/auth/v1/signup` is then rejected outright. This proves the invite-only pilot
model end to end: **we create accounts through the admin API; the public door is
shut.**

> **Required setting for the production project at pilot: public signups
> disabled.** Without it, anyone with the publishable key — which ships in the
> client and is meant to — could create an account.

---

## 5. Latency baseline — Amman → Supabase

10 iterations each, wall clock, single connection, no warmup excluded.

| Operation | min | median | max |
|---|---|---|---|
| token grant (`POST /auth/v1/token`) | 363 ms | **371 ms** | 472 ms |
| select 3 rows (`GET /rest/v1/…`) | 82 ms | **84 ms** | 279 ms |
| insert 1 row (`POST /rest/v1/…`) | 77 ms | **84 ms** | 106 ms |

Plain numbers, no interpretation. Recorded so a later change of region,
custom domain or network path can be compared against a real baseline rather
than an impression.

---

## 6. Storage — ATTEMPTED, BLOCKED, DIAGNOSTIC PENDING

A stretch goal. **Not proven.** To be amended in a follow-up commit.

What worked: the bucket was created private via the storage API with the secret
key — `POST {SUPABASE_URL}/storage/v1/bucket`, `{ id, name, public: false }` →
**HTTP 200**. (This is what establishes that §3b's missing grants are scoped to
`public`, not `storage`.)

What failed: **every upload is refused, including a user writing into their own
`<user-id>/` prefix**, after the four owner-scoped policies on `storage.objects`
were applied and reported successful.

```
POST {SUPABASE_URL}/storage/v1/object/spike-media/<A-id>/hello.txt
headers { apikey: <publishable>, Authorization: Bearer <A access token>,
          Content-Type: text/plain }

-> HTTP 400
   {"statusCode":"403","error":"Unauthorized",
    "message":"new row violates row-level security policy","code":"AccessDenied"}
```

The error is an **RLS policy violation, never `42501`** — so grants on
`storage.objects` are fine and the *predicate* is the suspect. Both users are
refused their own prefixes, so it is not an ownership-matching subtlety.

Precondition-gated re-run: **1 passed, 2 failed, 5 NOT RUN.**

A read-only diagnostic (`~/zajil-spike/diagnose-storage.sql`) is outstanding:
whether the four policies exist and against which roles, what privileges
`authenticated` holds on `storage.objects`, and whether
`(storage.foldername(name))[1]` evaluates as the policy assumes.

### The ownership decision, for when this resumes

Ownership is expressed by **path prefix** — `spike-media/<user-id>/<file>` —
rather than the `storage.objects.owner` column. `owner` is deprecated in favour
of `owner_id` (text) and which exists varies by project age; a path prefix is
stable and self-evident in a policy. This is a contract decision for v1.9, not
incidental spike detail.

### Lesson worth keeping: storage tests must gate on the upload

The first storage run reported **4 passed** — and every one of those passes was
**vacuous**. The reads returned `404 NoSuchKey` because nothing had been
uploaded, and *an empty bucket denies everyone*. "B is denied" and "anon is
denied" pass against a completely broken policy set exactly as they do against a
working one.

> **Any storage test must treat a successful upload as a hard precondition and
> report the dependent assertions as NOT RUN — never as passed — when it
> fails.** The corrected run makes this explicit and is why the honest result is
> `1 passed, 2 failed, 5 not run` rather than a comfortable `4 passed`.

The same trap applies to any "access is denied" test: confirm the thing being
protected actually exists, or the test proves nothing.

---

## Standing notes

### The secret key is server-only, forever

`sb_secret_…` bypasses RLS entirely. It may appear only in server-side code —
in this spike, only in `admin.js`. **It must never ship in, near, or adjacent to
client code**, and must never be placed in any file the app bundles, precaches
or serves. Zajil's client uses the **publishable** key and a user access token,
which is exactly what §4 proves is sufficient.

### The API must move to a custom domain before Gulf users

**`*.supabase.co` was regionally blocked in the UAE during 2025.** Zajil's
audience is Jordan and the Gulf, so a production deployment reached through the
default `*.supabase.co` host is one regulator decision away from being
unreachable for a substantial part of its users.

> **Before any Gulf pilot: put the API behind a custom domain.** This is a
> distribution requirement, not a nicety, and it should be settled before users
> depend on it rather than during an outage.

---

## What this does not answer

- **Storage** — see §6.
- **Sync semantics.** The spike proves transport and authorisation. How v1.8's
  op log, tombstones and `seq` ordering reconcile against a server is a v1.9
  design question and was deliberately out of scope.
- **The synchronous `getBird` constraint** (BACKLOG D3, HANDOFF §15) is
  untouched by this spike and remains the biggest structural decision: keep a
  full local mirror and sync it, or make the engine async.
