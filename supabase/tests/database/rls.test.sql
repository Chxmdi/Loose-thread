begin;

create extension if not exists pgtap with schema extensions;

select plan(13);

select is(
    (
        select count(*)
        from pg_class
        where relnamespace = 'public'::regnamespace
          and relname = any(array[
              'captures', 'thoughts', 'thought_relationships', 'threads', 'thread_memberships',
              'retrievals', 'retrieval_impressions', 'sessions', 'feedback_events',
              'user_calibration', 'jobs', 'agent_runs'
          ])
          and relrowsecurity
    ),
    12::bigint,
    'RLS is enabled on every Loose Thread user-owned table'
);

select has_index(
    'public',
    'thoughts',
    'thoughts_embedding_hnsw_idx',
    'Thought embeddings have an HNSW index'
);
select has_index(
    'public',
    'jobs',
    'jobs_claim_idx',
    'Runnable jobs have a claim index'
);

insert into auth.users (id, email)
values
    ('11111111-1111-4111-8111-111111111111', 'user-a@example.test'),
    ('22222222-2222-4222-8222-222222222222', 'user-b@example.test');

insert into public.captures (
    id,
    user_id,
    device_id,
    idempotency_key,
    capture_mode,
    raw_text,
    client_created_at
)
values
    (
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
        '11111111-1111-4111-8111-111111111111',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01',
        'capture-a',
        'text',
        'User A evidence',
        now()
    ),
    (
        'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2',
        '22222222-2222-4222-8222-222222222222',
        'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb02',
        'capture-b',
        'text',
        'User B evidence',
        now()
    );

set local role authenticated;
set local request.jwt.claims = '{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}';

select is(
    (select count(*) from public.captures),
    1::bigint,
    'User A can only select their own capture'
);

select is(
    (select raw_text from public.captures limit 1),
    'User A evidence',
    'The visible capture belongs to User A'
);

select lives_ok(
    $$
        insert into public.captures (
            user_id,
            device_id,
            idempotency_key,
            capture_mode,
            raw_text,
            client_created_at
        )
        values (
            '11111111-1111-4111-8111-111111111111',
            'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01',
            'capture-a-second',
            'text',
            'A second owned capture',
            now()
        )
    $$,
    'User A can insert an owned capture'
);

select throws_ok(
    $$
        insert into public.captures (
            user_id,
            device_id,
            idempotency_key,
            capture_mode,
            raw_text,
            client_created_at
        )
        values (
            '22222222-2222-4222-8222-222222222222',
            'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01',
            'cross-user-insert',
            'text',
            'Forbidden',
            now()
        )
    $$,
    '42501',
    'new row violates row-level security policy for table "captures"',
    'User A cannot insert a capture for User B'
);

select throws_ok(
    $$
        update public.captures
        set raw_text = 'Changed evidence'
        where id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1'
    $$,
    '22000',
    'capture source evidence is immutable',
    'Raw capture evidence cannot be changed'
);

select lives_ok(
    $$
        update public.captures
        set processing_status = 'processing'
        where id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1'
    $$,
    'Mutable processing metadata can be updated'
);

select throws_ok(
    $$
        insert into public.captures (
            user_id,
            device_id,
            idempotency_key,
            capture_mode,
            raw_text,
            client_created_at
        )
        values (
            '11111111-1111-4111-8111-111111111111',
            'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01',
            'capture-a',
            'text',
            'Duplicate retry',
            now()
        )
    $$,
    '23505',
    null,
    'Capture idempotency key prevents duplicate retries'
);

reset role;

insert into public.jobs (
    user_id,
    job_type,
    entity_type,
    entity_id,
    idempotency_key
)
values
    (
        '11111111-1111-4111-8111-111111111111',
        'interpret_capture',
        'capture',
        'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
        'interpret:a'
    ),
    (
        '22222222-2222-4222-8222-222222222222',
        'interpret_capture',
        'capture',
        'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2',
        'interpret:b'
    );

set local role authenticated;
set local request.jwt.claims = '{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}';

select is(
    (select count(*) from public.jobs),
    1::bigint,
    'Job diagnostics are isolated to the current user'
);

select is(
    (select count(*) from public.agent_runs),
    0::bigint,
    'Agent run diagnostics do not leak rows'
);

select is(
    (select count(*) from public.thoughts),
    0::bigint,
    'Thought reads remain user scoped'
);

select * from finish();

rollback;
