-- ════════════════════════════════════════════════════════════════════════════
-- Zajil — photo diagnostic (ORDERED 2026-11-20: written, NOT run by the builder).
-- Tells, for a photo the PC cannot show, whether the stored mark never reached the server or the download fails.
-- Checked on 2026-11-20 on PGlite (PostgreSQL in WebAssembly) against sync-schema.sql PART 1 and a stub of
-- storage.objects (name, metadata, created_at): it parses, returns the three kinds below, and leaves the row
-- counts of both tables as they were (log: ~/zajil-gate-logs/photo-diagnostic-pglite.log). That proves the
-- syntax and the join, NOT the column names of the real storage schema — `metadata->>'size'` and `created_at`
-- are the ones the Supabase docs' own usage query reads; `metadata->>'mimetype'` shows empty if absent.
--
-- EXPECTED, for a phone photo whose upload AND stored mark both reached the server — one row of kind A:
--   object_name             <owner uuid>/<media id>
--   object_bytes            the uploaded size (Samir's phone photo: 251267)
--   object_created_at       the upload (2026-11-19 18:51:35+00)
--   owner, record_id        the two halves of object_name
--   updated_at              at or just after the upload (the mark is written once storage acknowledges; the row
--                           carries that operation's time, by the phone's clock) — later only if the record was
--                           changed again since
--   deleted                 false
--   device_id               the phone's device id
--   has_stored_mark         true
--   stored_mark             {"at": "<just after the upload>", "size": 251267, "type": "<the photo's type>"}
--   mark_size_equals_object true
--
-- READING IT:
--   kind A, has_stored_mark true, sizes equal   the server is right; a PC that still says «الصورة على جهاز آخر ولم
--                                               تُرفع بعد» has not pulled the mark; one that says «تعذّر تنزيل الصورة»
--                                               has the mark and the DOWNLOAD fails
--   kind A, has_stored_mark false               the bytes arrived, the mark did not (not pushed yet — or replaced by a
--                                               later write without it: look at updated_at and device_id)
--   kind A, mark_size_equals_object false       the PC refuses the download: an answer of another length is not
--                                               this photo (src/db/photos.js)
--   kind B, deleted false, no mark              the bytes are only on the device that took the photo
--   kind C                                      an object no media row names (path and row disagree, or the row
--                                               was never pushed)
-- ════════════════════════════════════════════════════════════════════════════
-- READ-ONLY, ONE statement: paste all of it into the SQL Editor and run it.
-- Each object in the private bucket `photos` beside the media row in sync_records with the same
-- owner and id (object path = <owner uuid>/<media id>), and every media row that has no object.
-- It changes nothing: a SELECT over storage.objects and public.sync_records, no function called
-- that writes. The editor runs as postgres, so it sees every account's rows; the owner column
-- says whose each row is.
select
  case
    when r.record_id is null then 'C object, no media row'
    when o.name is null      then 'B media row, no object'
    else                          'A object and media row'
  end                                              as kind,
  o.name                                           as object_name,
  (o.metadata->>'size')::bigint                    as object_bytes,
  o.metadata->>'mimetype'                          as object_type,
  o.created_at                                     as object_created_at,
  r.owner,
  r.record_id,
  r.updated_at,
  r.deleted,
  r.device_id,
  case when r.record_id is not null
       then (r.data->'stored') is not null end     as has_stored_mark,
  r.data->'stored'                                 as stored_mark,
  (r.data->'stored'->>'size')::bigint
    = (o.metadata->>'size')::bigint                as mark_size_equals_object
from (select name, metadata, created_at
        from storage.objects where bucket_id = 'photos') o
full outer join (select owner, record_id, data, deleted, updated_at, device_id
                 from public.sync_records where store = 'media') r
  on o.name = r.owner::text || '/' || r.record_id
order by kind, coalesce(o.created_at, r.updated_at);
