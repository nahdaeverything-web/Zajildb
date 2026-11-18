-- Zajil — READ-ONLY check of the live project against supabase/sync-schema.sql.
-- ONE statement (the SQL Editor shows only the last statement's result), built
-- from the same catalogs as PART 2 and PART 3 of that file. It changes nothing.
-- Expected: 17 rows; `ok` is true on rows 1–16; row 17 is information only.
with t as (select to_regclass('public.sync_records') as rel),
checks(n, what, found, expected, ok) as (
  select 1, 'trigger sync_records_seq fires before insert or update',
         coalesce(string_agg(pg_get_triggerdef(g.oid), ' | '), 'NO TRIGGER'),
         'one trigger, BEFORE INSERT OR UPDATE … sync_assign_server_seq()',
         count(*) = 1 and bool_and(pg_get_triggerdef(g.oid) like '%BEFORE INSERT OR UPDATE%sync_assign_server_seq()%')
  from pg_trigger g, t where g.tgrelid = t.rel and not g.tgisinternal
  union all
  select 1 + row_number() over (order by c.cmd)::int, 'policy for ' || c.cmd,
         coalesce(p.policyname || ' ' || p.roles::text, 'MISSING'),
         'sync_records owner ' || lower(c.cmd) || ' {authenticated}',
         coalesce(p.policyname = 'sync_records owner ' || lower(c.cmd) and p.roles::text = '{authenticated}', false)
  from (values ('DELETE'), ('INSERT'), ('SELECT'), ('UPDATE')) c(cmd)
  left join pg_policies p on p.schemaname = 'public' and p.tablename = 'sync_records' and p.cmd = c.cmd
  union all
  select 6, 'number of policies on the table', count(*)::text, '4', count(*) = 4
  from pg_policies where schemaname = 'public' and tablename = 'sync_records'
  union all
  select 7, 'table privileges of authenticated',
         coalesce(string_agg(privilege_type, ', ' order by privilege_type), 'none'),
         'INSERT, SELECT, UPDATE',
         coalesce(string_agg(privilege_type, ', ' order by privilege_type), 'none') = 'INSERT, SELECT, UPDATE'
  from information_schema.role_table_grants
  where table_schema = 'public' and table_name = 'sync_records' and grantee = 'authenticated'
  union all
  select 8, 'table privileges of anon',
         coalesce(string_agg(privilege_type, ', ' order by privilege_type), 'none'), 'none', count(*) = 0
  from information_schema.role_table_grants
  where table_schema = 'public' and table_name = 'sync_records' and grantee = 'anon'
  union all
  select 9, 'row-level security is on', coalesce((select relrowsecurity::text from pg_class, t where oid = t.rel), 'NO TABLE'),
         'true', coalesce((select relrowsecurity from pg_class, t where oid = t.rel), false)
  union all
  select 10, 'authenticated may use the sequence',
         coalesce(has_sequence_privilege('authenticated', to_regclass('public.sync_server_seq')::oid, 'USAGE')::text, 'NO SEQUENCE'), 'true',
         coalesce(has_sequence_privilege('authenticated', to_regclass('public.sync_server_seq')::oid, 'USAGE'), false)
  union all
  select 11, 'anon may NOT use the sequence',
         coalesce(has_sequence_privilege('anon', to_regclass('public.sync_server_seq')::oid, 'USAGE')::text, 'NO SEQUENCE'), 'false',
         coalesce(not has_sequence_privilege('anon', to_regclass('public.sync_server_seq')::oid, 'USAGE'), false)
  union all
  select 11 + row_number() over (order by e.col)::int, 'column ' || e.col,
         coalesce(c.data_type, 'MISSING'), e.typ, coalesce(c.data_type = e.typ, false)
  from (values ('data', 'jsonb'), ('device_id', 'uuid'), ('record_id', 'text'),
               ('updated_at', 'timestamp with time zone')) e(col, typ)
  left join information_schema.columns c
    on c.table_schema = 'public' and c.table_name = 'sync_records' and c.column_name = e.col
  union all
  select 16, 'trigger function: per-owner lock, last-write-wins guard, not security definer',
         coalesce(string_agg('lock=' || (pg_get_functiondef(p.oid) like '%pg_advisory_xact_lock%')::text
           || ' guard=' || (pg_get_functiondef(p.oid) like '%new := old%')::text
           || ' security_definer=' || p.prosecdef::text, ' | '), 'NO FUNCTION'),
         'lock=true guard=true security_definer=false',
         count(*) = 1 and bool_and(pg_get_functiondef(p.oid) like '%pg_advisory_xact_lock%'
           and pg_get_functiondef(p.oid) like '%new := old%' and not p.prosecdef)
  from pg_proc p join pg_namespace s on s.oid = p.pronamespace
  where s.nspname = 'public' and p.proname = 'sync_assign_server_seq'
  union all
  select 17, 'information only: table privileges of service_role',
         coalesce(string_agg(privilege_type, ', ' order by privilege_type), 'none'), '(not judged)', null
  from information_schema.role_table_grants
  where table_schema = 'public' and table_name = 'sync_records' and grantee = 'service_role'
)
select n, what, found, expected, ok from checks order by n;
