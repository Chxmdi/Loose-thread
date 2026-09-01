create schema if not exists private;

revoke all on schema private from public, anon, authenticated;
grant usage on schema private to service_role;

create extension if not exists pgcrypto with schema extensions;
create extension if not exists vector with schema extensions;

create table public.captures (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    device_id uuid not null,
    idempotency_key text not null check (length(idempotency_key) between 1 and 200),
    capture_mode text not null check (capture_mode in ('text', 'audio', 'share')),
    raw_text text,
    audio_storage_path text,
    timezone text not null default 'UTC',
    client_created_at timestamptz not null,
    transcription_status text not null default 'not_required'
        check (transcription_status in ('not_required', 'queued', 'processing', 'succeeded', 'failed')),
    processing_status text not null default 'queued'
        check (processing_status in ('queued', 'processing', 'succeeded', 'failed')),
    sync_version bigint not null default 1 check (sync_version > 0),
    is_deleted boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint captures_source_present check (
        nullif(btrim(raw_text), '') is not null or audio_storage_path is not null
    ),
    constraint captures_user_idempotency_unique unique (user_id, idempotency_key),
    constraint captures_id_user_unique unique (id, user_id)
);

create table public.thoughts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    capture_id uuid not null,
    split_index integer not null default 0 check (split_index >= 0),
    client_created_at timestamptz not null,
    raw_fragment text not null check (length(raw_fragment) > 0),
    refined_text text not null check (length(refined_text) > 0),
    refined_source text not null
        check (refined_source in ('model_inferred', 'user_edited', 'user_raw')),
    kind text not null check (
        kind in (
            'task', 'idea', 'question', 'research', 'unfinished',
            'reminder', 'observation', 'reference', 'feeling'
        )
    ),
    commitment_strength text not null
        check (commitment_strength in ('none', 'curiosity', 'possible', 'intended', 'committed')),
    surface_policy text not null
        check (surface_policy in ('normal', 'resumption_only', 'search_only', 'never_proactive')),
    duration_bucket text not null
        check (duration_bucket in ('spark', 'snack', 'session', 'deep', 'unknown')),
    energy text not null check (energy in ('low', 'medium', 'high', 'unknown')),
    contexts text[] not null default '{}',
    entities jsonb not null default '{}',
    temporal jsonb not null default '{}',
    open_loop jsonb not null default '{}',
    confidence jsonb not null default '{}',
    status text not null default 'active'
        check (status in ('active', 'in_progress', 'done', 'archived', 'dormant', 'deleted')),
    last_surfaced_at timestamptz,
    surface_count integer not null default 0 check (surface_count >= 0),
    snooze_until timestamptz,
    embedding extensions.vector(1536),
    enrichment jsonb not null default '{}',
    enrichment_version text not null default 'interpreter-v1',
    sync_version bigint not null default 1 check (sync_version > 0),
    is_deleted boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint thoughts_capture_owner_fk
        foreign key (capture_id, user_id) references public.captures(id, user_id) on delete cascade,
    constraint thoughts_interpretation_unique
        unique (capture_id, split_index, enrichment_version),
    constraint thoughts_id_user_unique unique (id, user_id)
);

create table public.thought_relationships (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    from_thought_id uuid not null,
    to_thought_id uuid not null,
    relation_type text not null check (
        relation_type in (
            'continues', 'elaborates', 'answers', 'contradicts', 'references',
            'spawned_from', 'same_topic', 'same_person', 'same_project'
        )
    ),
    confidence numeric(5, 4) check (confidence between 0 and 1),
    source text not null check (source in ('user', 'model', 'system')),
    rationale text,
    model_version text,
    created_at timestamptz not null default now(),
    constraint thought_relationships_distinct check (from_thought_id <> to_thought_id),
    constraint thought_relationships_from_owner_fk
        foreign key (from_thought_id, user_id) references public.thoughts(id, user_id) on delete cascade,
    constraint thought_relationships_to_owner_fk
        foreign key (to_thought_id, user_id) references public.thoughts(id, user_id) on delete cascade,
    constraint thought_relationships_unique
        unique (from_thought_id, to_thought_id, relation_type),
    constraint thought_relationships_id_user_unique unique (id, user_id)
);

create table public.threads (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text,
    summary text,
    summary_version integer not null default 0 check (summary_version >= 0),
    last_activity_at timestamptz not null default now(),
    status text not null default 'active' check (status in ('active', 'dormant', 'archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint threads_id_user_unique unique (id, user_id)
);

create table public.thread_memberships (
    user_id uuid not null references auth.users(id) on delete cascade,
    thread_id uuid not null,
    thought_id uuid not null,
    confidence numeric(5, 4) check (confidence between 0 and 1),
    source text not null check (source in ('user', 'model', 'system')),
    created_at timestamptz not null default now(),
    primary key (thread_id, thought_id),
    constraint thread_memberships_thread_owner_fk
        foreign key (thread_id, user_id) references public.threads(id, user_id) on delete cascade,
    constraint thread_memberships_thought_owner_fk
        foreign key (thought_id, user_id) references public.thoughts(id, user_id) on delete cascade
);

create table public.retrievals (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    requested_at timestamptz not null default now(),
    window_label text not null check (window_label in ('5', '15', '30', '60', 'a_while')),
    contexts jsonb not null default '{}',
    candidate_count integer check (candidate_count >= 0),
    result_thought_ids uuid[] not null default '{}',
    ranking_version text not null,
    reshuffle_of uuid,
    created_at timestamptz not null default now(),
    constraint retrievals_id_user_unique unique (id, user_id),
    constraint retrievals_reshuffle_owner_fk
        foreign key (reshuffle_of, user_id) references public.retrievals(id, user_id),
    constraint retrievals_not_self_reshuffle check (reshuffle_of is null or reshuffle_of <> id)
);

create unique index retrievals_one_reshuffle_idx
    on public.retrievals (reshuffle_of)
    where reshuffle_of is not null;

create table public.retrieval_impressions (
    user_id uuid not null references auth.users(id) on delete cascade,
    retrieval_id uuid not null,
    thought_id uuid not null,
    rank_position integer not null check (rank_position >= 1),
    score numeric,
    score_components jsonb not null default '{}',
    selected boolean not null default false,
    action text check (action in ('start', 'not_now', 'done_with_this', 'none_of_these')),
    created_at timestamptz not null default now(),
    primary key (retrieval_id, thought_id),
    constraint retrieval_impressions_retrieval_owner_fk
        foreign key (retrieval_id, user_id) references public.retrievals(id, user_id) on delete cascade,
    constraint retrieval_impressions_thought_owner_fk
        foreign key (thought_id, user_id) references public.thoughts(id, user_id) on delete cascade
);

create table public.sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    thought_id uuid not null,
    retrieval_id uuid,
    window_minutes integer check (window_minutes is null or window_minutes > 0),
    window_label text not null check (window_label in ('5', '15', '30', '60', 'a_while')),
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    outcome text check (outcome in ('done', 'partial', 'stopped', 'spawned_new')),
    fit_feedback text check (fit_feedback in ('shorter', 'right', 'longer')),
    actual_minutes integer check (actual_minutes is null or actual_minutes >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint sessions_thought_owner_fk
        foreign key (thought_id, user_id) references public.thoughts(id, user_id),
    constraint sessions_retrieval_owner_fk
        foreign key (retrieval_id, user_id) references public.retrievals(id, user_id),
    constraint sessions_end_after_start check (ended_at is null or ended_at >= started_at),
    constraint sessions_id_user_unique unique (id, user_id)
);

create table public.feedback_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    session_id uuid,
    retrieval_id uuid,
    thought_id uuid,
    event_type text not null,
    event_data jsonb not null default '{}',
    idempotency_key text not null check (length(idempotency_key) between 1 and 200),
    created_at timestamptz not null default now(),
    constraint feedback_events_session_owner_fk
        foreign key (session_id, user_id) references public.sessions(id, user_id),
    constraint feedback_events_retrieval_owner_fk
        foreign key (retrieval_id, user_id) references public.retrievals(id, user_id),
    constraint feedback_events_thought_owner_fk
        foreign key (thought_id, user_id) references public.thoughts(id, user_id),
    constraint feedback_events_user_idempotency_unique unique (user_id, idempotency_key)
);

create table public.user_calibration (
    user_id uuid primary key references auth.users(id) on delete cascade,
    duration_calibration jsonb not null default '{}',
    kind_affinity jsonb not null default '{}',
    context_affinity jsonb not null default '{}',
    observation_count integer not null default 0 check (observation_count >= 0),
    updated_at timestamptz not null default now()
);

create table public.jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_type text not null check (
        job_type in (
            'transcribe_capture', 'interpret_capture', 'embed_thought', 'link_thought',
            'build_resumption_context', 'apply_feedback_calibration', 'cleanup_expired_audio'
        )
    ),
    entity_type text not null,
    entity_id uuid not null,
    status text not null default 'queued'
        check (status in ('queued', 'running', 'succeeded', 'retry_wait', 'dead_letter')),
    priority integer not null default 100,
    attempts integer not null default 0 check (attempts >= 0),
    max_attempts integer not null default 5 check (max_attempts > 0),
    run_after timestamptz not null default now(),
    locked_at timestamptz,
    locked_by text,
    lease_expires_at timestamptz,
    idempotency_key text not null check (length(idempotency_key) between 1 and 300),
    payload jsonb not null default '{}',
    payload_version integer not null default 1 check (payload_version > 0),
    correlation_id uuid not null default gen_random_uuid(),
    last_error_code text,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint jobs_user_idempotency_unique unique (user_id, idempotency_key),
    constraint jobs_attempts_within_bound check (attempts <= max_attempts),
    constraint jobs_lease_consistent check (
        (status = 'running' and locked_at is not null and locked_by is not null and lease_expires_at is not null)
        or status <> 'running'
    ),
    constraint jobs_id_user_unique unique (id, user_id)
);

create table public.agent_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_id uuid,
    agent_name text not null,
    model text not null,
    schema_version text not null,
    prompt_version text not null,
    status text not null check (status in ('running', 'succeeded', 'failed')),
    input_entity_ids jsonb not null default '[]',
    output_entity_ids jsonb not null default '[]',
    openai_trace_id text,
    correlation_id uuid not null,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    latency_ms integer check (latency_ms is null or latency_ms >= 0),
    usage jsonb not null default '{}',
    error_code text,
    error_message text,
    created_at timestamptz not null default now(),
    constraint agent_runs_job_owner_fk
        foreign key (job_id, user_id) references public.jobs(id, user_id) on delete set null,
    constraint agent_runs_completion_consistent check (
        (status = 'running' and completed_at is null)
        or (status in ('succeeded', 'failed') and completed_at is not null)
    )
);

create index captures_user_created_idx on public.captures (user_id, created_at desc);
create index thoughts_user_status_created_idx on public.thoughts (user_id, status, created_at desc);
create index thoughts_user_capture_idx on public.thoughts (user_id, capture_id);
create index thoughts_embedding_hnsw_idx
    on public.thoughts using hnsw (embedding extensions.vector_cosine_ops)
    where embedding is not null;
create index thought_relationships_user_from_idx
    on public.thought_relationships (user_id, from_thought_id);
create index thought_relationships_user_to_idx
    on public.thought_relationships (user_id, to_thought_id);
create index threads_user_activity_idx on public.threads (user_id, last_activity_at desc);
create index thread_memberships_user_thought_idx
    on public.thread_memberships (user_id, thought_id);
create index retrievals_user_requested_idx on public.retrievals (user_id, requested_at desc);
create index sessions_user_started_idx on public.sessions (user_id, started_at desc);
create index feedback_events_user_created_idx on public.feedback_events (user_id, created_at desc);
create index jobs_claim_idx
    on public.jobs (priority desc, run_after, created_at)
    where status in ('queued', 'retry_wait', 'running');
create index jobs_user_created_idx on public.jobs (user_id, created_at desc);
create index agent_runs_user_created_idx on public.agent_runs (user_id, created_at desc);
create index agent_runs_job_idx on public.agent_runs (job_id) where job_id is not null;

create function private.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create function private.preserve_capture_evidence()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if new.capture_mode is distinct from old.capture_mode
        or new.raw_text is distinct from old.raw_text
        or new.audio_storage_path is distinct from old.audio_storage_path
        or new.device_id is distinct from old.device_id
        or new.client_created_at is distinct from old.client_created_at
    then
        raise exception 'capture source evidence is immutable' using errcode = '22000';
    end if;
    return new;
end;
$$;

create trigger captures_set_updated_at
before update on public.captures
for each row execute function private.set_updated_at();

create trigger captures_preserve_evidence
before update on public.captures
for each row execute function private.preserve_capture_evidence();

create trigger thoughts_set_updated_at
before update on public.thoughts
for each row execute function private.set_updated_at();

create trigger threads_set_updated_at
before update on public.threads
for each row execute function private.set_updated_at();

create trigger sessions_set_updated_at
before update on public.sessions
for each row execute function private.set_updated_at();

create trigger jobs_set_updated_at
before update on public.jobs
for each row execute function private.set_updated_at();

create trigger user_calibration_set_updated_at
before update on public.user_calibration
for each row execute function private.set_updated_at();

create function private.claim_jobs(
    p_worker_id text,
    p_limit integer default 1,
    p_lease_seconds integer default 120
)
returns setof public.jobs
language sql
security invoker
set search_path = ''
as $$
    with terminal_expired as (
        update public.jobs as expired
        set
            status = 'dead_letter',
            locked_at = null,
            locked_by = null,
            lease_expires_at = null,
            last_error_code = 'lease_expired_at_max_attempts',
            last_error = 'Worker lease expired after the final allowed attempt'
        where expired.status = 'running'
          and expired.lease_expires_at <= now()
          and expired.attempts >= expired.max_attempts
        returning expired.id
    ),
    claimable as (
        select j.id
        from public.jobs as j
        where (
            (j.status in ('queued', 'retry_wait') and j.run_after <= now())
            or (j.status = 'running' and j.lease_expires_at <= now())
        )
        and j.attempts < j.max_attempts
        order by j.priority desc, j.run_after, j.created_at
        for update skip locked
        limit greatest(1, least(p_limit, 100))
    )
    update public.jobs as j
    set
        status = 'running',
        attempts = j.attempts + 1,
        locked_at = now(),
        locked_by = p_worker_id,
        lease_expires_at = now() + make_interval(secs => greatest(1, p_lease_seconds)),
        last_error_code = null,
        last_error = null
    from claimable
    where j.id = claimable.id
    returning j.*;
$$;

create function private.match_thoughts(
    p_user_id uuid,
    p_embedding extensions.vector(1536),
    p_limit integer default 12,
    p_max_distance double precision default 0.45
)
returns table (
    thought_id uuid,
    distance double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
    select
        t.id,
        (t.embedding operator(extensions.<=>) p_embedding)::double precision
    from public.thoughts as t
    where t.user_id = p_user_id
      and t.status = 'active'
      and not t.is_deleted
      and t.embedding is not null
      and (t.embedding operator(extensions.<=>) p_embedding) <= p_max_distance
    order by t.embedding operator(extensions.<=>) p_embedding, t.id
    limit greatest(1, least(p_limit, 100));
$$;

create function private.complete_job(
    p_job_id uuid,
    p_worker_id text
)
returns public.jobs
language sql
security invoker
set search_path = ''
as $$
    update public.jobs as j
    set
        status = 'succeeded',
        locked_at = null,
        locked_by = null,
        lease_expires_at = null,
        last_error_code = null,
        last_error = null
    where j.id = p_job_id
      and j.status = 'running'
      and j.locked_by = p_worker_id
    returning j.*;
$$;

create function private.fail_job(
    p_job_id uuid,
    p_worker_id text,
    p_error_code text,
    p_error_message text,
    p_retry_delay_seconds integer,
    p_retryable boolean default true
)
returns public.jobs
language sql
security invoker
set search_path = ''
as $$
    update public.jobs as j
    set
        status = case
            when not p_retryable or j.attempts >= j.max_attempts then 'dead_letter'
            else 'retry_wait'
        end,
        run_after = case
            when not p_retryable or j.attempts >= j.max_attempts then j.run_after
            else now() + make_interval(secs => greatest(0, p_retry_delay_seconds))
        end,
        locked_at = null,
        locked_by = null,
        lease_expires_at = null,
        last_error_code = left(p_error_code, 100),
        last_error = left(p_error_message, 1000)
    where j.id = p_job_id
      and j.status = 'running'
      and j.locked_by = p_worker_id
    returning j.*;
$$;

create function private.renew_job_lease(
    p_job_id uuid,
    p_worker_id text,
    p_lease_seconds integer
)
returns public.jobs
language sql
security invoker
set search_path = ''
as $$
    update public.jobs as j
    set lease_expires_at = now() + make_interval(secs => greatest(1, p_lease_seconds))
    where j.id = p_job_id
      and j.status = 'running'
      and j.locked_by = p_worker_id
      and j.lease_expires_at > now()
    returning j.*;
$$;

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'captures', 'thoughts', 'thought_relationships', 'threads', 'thread_memberships',
        'retrievals', 'retrieval_impressions', 'sessions', 'feedback_events',
        'user_calibration', 'jobs', 'agent_runs'
    ]
    loop
        execute format('alter table public.%I enable row level security', table_name);
        execute format(
            'create policy %I on public.%I for select to authenticated using ((select auth.uid()) = user_id)',
            table_name || '_select_own',
            table_name
        );
        execute format(
            'create policy %I on public.%I for insert to authenticated with check ((select auth.uid()) = user_id)',
            table_name || '_insert_own',
            table_name
        );
        execute format(
            'create policy %I on public.%I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)',
            table_name || '_update_own',
            table_name
        );
        execute format(
            'create policy %I on public.%I for delete to authenticated using ((select auth.uid()) = user_id)',
            table_name || '_delete_own',
            table_name
        );
    end loop;
end;
$$;

revoke all on table
    public.captures,
    public.thoughts,
    public.thought_relationships,
    public.threads,
    public.thread_memberships,
    public.retrievals,
    public.retrieval_impressions,
    public.sessions,
    public.feedback_events,
    public.user_calibration,
    public.jobs,
    public.agent_runs
from anon, authenticated;

grant usage on schema public to authenticated, service_role;
grant select on table
    public.captures,
    public.thoughts,
    public.thought_relationships,
    public.threads,
    public.thread_memberships,
    public.retrievals,
    public.retrieval_impressions,
    public.sessions,
    public.feedback_events,
    public.user_calibration,
    public.jobs,
    public.agent_runs
to authenticated;
grant insert, update, delete on table public.captures, public.thoughts to authenticated;
grant all on table
    public.captures,
    public.thoughts,
    public.thought_relationships,
    public.threads,
    public.thread_memberships,
    public.retrievals,
    public.retrieval_impressions,
    public.sessions,
    public.feedback_events,
    public.user_calibration,
    public.jobs,
    public.agent_runs
to service_role;

revoke all on function private.claim_jobs(text, integer, integer) from public;
revoke all on function private.complete_job(uuid, text) from public;
revoke all on function private.fail_job(uuid, text, text, text, integer, boolean) from public;
revoke all on function private.renew_job_lease(uuid, text, integer) from public;
revoke all on function private.match_thoughts(
    uuid,
    extensions.vector,
    integer,
    double precision
) from public;
grant execute on function private.claim_jobs(text, integer, integer) to service_role;
grant execute on function private.complete_job(uuid, text) to service_role;
grant execute on function private.fail_job(uuid, text, text, text, integer, boolean)
    to service_role;
grant execute on function private.renew_job_lease(uuid, text, integer) to service_role;
grant execute on function private.match_thoughts(
    uuid,
    extensions.vector,
    integer,
    double precision
) to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'capture-audio',
    'capture-audio',
    false,
    52428800,
    array['audio/m4a', 'audio/mp4', 'audio/mpeg', 'audio/wav', 'audio/webm']
)
on conflict (id) do update
set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create policy capture_audio_select_own
on storage.objects for select
to authenticated
using (
    bucket_id = 'capture-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy capture_audio_insert_own
on storage.objects for insert
to authenticated
with check (
    bucket_id = 'capture-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy capture_audio_update_own
on storage.objects for update
to authenticated
using (
    bucket_id = 'capture-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
)
with check (
    bucket_id = 'capture-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy capture_audio_delete_own
on storage.objects for delete
to authenticated
using (
    bucket_id = 'capture-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);
