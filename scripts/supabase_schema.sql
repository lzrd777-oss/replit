-- HHC-STORE schema for Supabase (Postgres)

create table if not exists public.products (
  id text primary key,
  slug text not null unique,
  title text not null default '',
  category text not null default '',
  price numeric(12,2) not null default 0,
  old_price numeric(12,2),
  member_price numeric(12,2),
  volume text not null default '',
  lab_label text not null default '',
  in_stock boolean not null default true,
  stock_text text not null default '',
  image text not null default '',
  archived boolean not null default false,
  short_description text not null default '',
  full_description text not null default '',
  sku text not null default '',
  tags jsonb not null default '[]'::jsonb,
  specs jsonb not null default '{}'::jsonb,
  flavors jsonb not null default '[]'::jsonb,
  colors jsonb not null default '[]'::jsonb,
  flavor_slots integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.orders (
  id text primary key,
  created_at timestamptz not null default now(),
  customer_name text not null default '',
  first_name text not null default '',
  last_name text not null default '',
  phone text not null default '',
  email text not null default '',
  city text not null default '',
  postal_code text not null default '',
  courier text not null default 'Econt',
  delivery_type text not null default 'office',
  address text not null default '',
  payment text not null default 'cod',
  status text not null default 'new_order'
    check (status in ('new_order', 'in_process', 'shipped', 'declined')),
  items jsonb not null default '[]'::jsonb,
  subtotal numeric(12,2) not null default 0,
  discount numeric(12,2) not null default 0,
  promo_code text not null default '',
  shipping numeric(12,2) not null default 0,
  total numeric(12,2) not null default 0
);

create index if not exists products_archived_idx on public.products (archived);
create index if not exists products_category_idx on public.products (category);
create index if not exists orders_status_idx on public.orders (status);
create index if not exists orders_created_at_idx on public.orders (created_at desc);

alter table public.products enable row level security;
alter table public.orders enable row level security;

-- Public catalog read (publishable / anon)
drop policy if exists "Public read active products" on public.products;
create policy "Public read active products"
  on public.products for select
  to anon, authenticated
  using (archived = false);

-- No public order reads; inserts allowed for checkout
drop policy if exists "Public insert orders" on public.orders;
create policy "Public insert orders"
  on public.orders for insert
  to anon, authenticated
  with check (true);

-- service_role bypasses RLS automatically

grant select on public.products to anon, authenticated;
grant select, insert, update, delete on public.products to service_role;
grant insert on public.orders to anon, authenticated;
grant select, insert, update, delete on public.orders to service_role;
