-- Mia Supabase target schema.
-- Apply this only after connecting a Supabase project and reviewing RLS policies.

create table if not exists public.mia_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'owner',
  created_at timestamptz not null default now()
);

create table if not exists public.mia_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  direction text not null check (direction in ('inbound', 'outbound')),
  message_handle text not null unique,
  linked_message_handle text,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.mia_thought_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  message_handle text,
  run_id text,
  node text not null,
  content text not null,
  active_agent text,
  created_at timestamptz not null default now()
);

create table if not exists public.mia_memories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  tier text not null default 'long_term',
  segment text not null default 'other',
  content text not null,
  importance double precision not null default 0.5,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.mia_profiles enable row level security;
alter table public.mia_messages enable row level security;
alter table public.mia_thought_logs enable row level security;
alter table public.mia_memories enable row level security;

create policy "profiles are user-owned"
  on public.mia_profiles for all
  using (auth.uid() = id)
  with check (auth.uid() = id);

create policy "messages are user-owned"
  on public.mia_messages for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "thought logs are user-owned"
  on public.mia_thought_logs for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "memories are user-owned"
  on public.mia_memories for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create index if not exists mia_messages_user_created_idx
  on public.mia_messages (user_id, created_at desc);

create index if not exists mia_thought_logs_message_created_idx
  on public.mia_thought_logs (message_handle, created_at asc);

create index if not exists mia_memories_user_updated_idx
  on public.mia_memories (user_id, updated_at desc);
