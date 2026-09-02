alter table public.feedback_events
    add column calibration_applied_at timestamptz,
    add column calibration_version text;

comment on column public.feedback_events.calibration_applied_at is
    'Set atomically with user_calibration updates so durable job retries cannot double-count feedback.';

comment on column public.feedback_events.calibration_version is
    'Deterministic calibration algorithm version applied to this immutable feedback event.';
