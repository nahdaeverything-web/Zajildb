-- ════════════════════════════════════════════════════════════════════════════
-- Zajil — photo storage: bucket, limits and owner-only policies.
-- RUN ON THE LIVE PROJECT ON 2026-11-18 by Samir, in the dashboard SQL Editor,
-- once, without error, after the reviewer read it. Section 3 returned the five
-- expected rows:
--   bucket | photos public=false limit=5242880 types={image/jpeg,image/png,image/webp,application/pdf}
--   policy | photos owner delete DELETE {authenticated}
--   policy | photos owner insert INSERT {authenticated}
--   policy | photos owner select SELECT {authenticated}
--   policy | photos owner update UPDATE {authenticated}
-- The bucket exists and is empty. Do NOT run sections 1-2 again on that project.
-- This is the text as it was PROPOSED (written 2026-11-17, limit ruled 2026-11-18);
-- if the text Samir ran was amended in review, this file must be amended to match.
-- Checked on 2026-11-18 by running the whole file on PGlite (PostgreSQL 18.6 in
-- WebAssembly) against a STUB of the storage schema: it parses, executes, and
-- section 3 returns the five expected rows. That proves the syntax, NOT that
-- Supabase Storage accepts it. The policy shape follows the Supabase docs
-- (Storage → Access Control): "By default Storage does not allow any uploads to
-- buckets without RLS policies", and the folder test
-- `(storage.foldername(name))[1] = (select auth.jwt()->>'sub')`.
-- Run ONCE: a second run stops at the bucket insert (duplicate key) and changes
-- nothing.
--
-- Object path: <owner uuid>/<media id>      (one object per photo or document)
-- ════════════════════════════════════════════════════════════════════════════

-- 1. the bucket: PRIVATE, with a per-file limit and an allow-list of types.
--    5 MiB per file, RULED 2026-11-18 (a 1600 px photo measured
--    0.3–0.5 MB; a PDF document is not downscaled). Types: images and PDF.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('photos', 'photos', false, 5242880,
        array['image/jpeg', 'image/png', 'image/webp', 'application/pdf']);

-- 2. owner-only, on all four verbs. Upload needs INSERT; overwrite (a retried
--    upload) needs SELECT and UPDATE as well; removing a deleted photo needs DELETE.
create policy "photos owner select" on storage.objects
  for select to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.jwt()->>'sub'));

create policy "photos owner insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.jwt()->>'sub'));

create policy "photos owner update" on storage.objects
  for update to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.jwt()->>'sub'))
  with check (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.jwt()->>'sub'));

create policy "photos owner delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = (select auth.jwt()->>'sub'));

-- 3. VERIFICATION — read-only, ONE statement, so the SQL Editor shows all of it
--    (it displays only the last statement's result). Expected, five rows:
--      bucket | photos public=false limit=5242880 types={image/jpeg,image/png,image/webp,application/pdf}
--      policy | photos owner delete DELETE {authenticated}
--      policy | photos owner insert INSERT {authenticated}
--      policy | photos owner select SELECT {authenticated}
--      policy | photos owner update UPDATE {authenticated}
select 'bucket' as what,
       id || ' public=' || public::text || ' limit=' || file_size_limit::text
          || ' types=' || allowed_mime_types::text as found
from storage.buckets where id = 'photos'
union all
select 'policy', policyname || ' ' || cmd || ' ' || roles::text
from pg_policies
where schemaname = 'storage' and tablename = 'objects' and policyname like 'photos owner %'
order by 1, 2;

-- 4. usage, whenever wanted — paste ON ITS OWN, without the lines above
--    (the docs' own query, narrowed to this bucket):
--
-- select bucket_id, count(*) as objects,
--        (sum((metadata->>'size')::bigint) / 1048576.0)::numeric(10, 2) as total_megabytes
-- from storage.objects where bucket_id = 'photos' group by bucket_id;
