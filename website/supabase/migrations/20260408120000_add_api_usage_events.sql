-- Orion Website: API usage tracking
--
-- Stores a row per API call to Next.js route handlers.
-- This is used for account usage, debugging, and future billing.

create table if not exists public.api_usage_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  request_id uuid not null,
  user_id uuid,

  action text,
  method text not null,
  path text not null,

  status_code integer not null,
  duration_ms integer,

  ip text,
  user_agent text,
  referer text,

  metadata jsonb not null default '{}'::jsonb
);

create index if not exists api_usage_events_user_created_at_idx
  on public.api_usage_events (user_id, created_at desc);

create index if not exists api_usage_events_created_at_idx
  on public.api_usage_events (created_at desc);

create index if not exists api_usage_events_action_created_at_idx
  on public.api_usage_events (action, created_at desc);

alter table public.api_usage_events enable row level security;

drop policy if exists "Users can read own api usage events" on public.api_usage_events;
create policy "Users can read own api usage events"
  on public.api_usage_events
  for select
  to authenticated
  using (auth.uid() = user_id);

-- Optional: allow clients to insert their own rows when using a user session.
-- (The website server typically writes with service role.)
drop policy if exists "Users can insert own api usage events" on public.api_usage_events;
create policy "Users can insert own api usage events"
  on public.api_usage_events
  for insert
  to authenticated
  with check (auth.uid() = user_id);

-- Security-invoker view for simple per-day counts.
-- NOTE: Views bypass RLS by default unless security_invoker is enabled.
create or replace view public.api_usage_daily
  with (security_invoker = true)
as
  select
    user_id,
    date_trunc('day', created_at) as day,
    count(*)::bigint as requests
  from public.api_usage_events
  where user_id is not null
  group by user_id, date_trunc('day', created_at);
