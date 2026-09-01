from loose_thread_api.orchestration.backoff import retry_delay


def test_retry_delay_is_deterministic_and_bounded() -> None:
    key = "interpret_capture:capture-id:v1"

    assert retry_delay(1, key) == retry_delay(1, key)
    assert 5 <= retry_delay(1, key).total_seconds() <= 10
    assert 10 <= retry_delay(2, key).total_seconds() <= 15
    assert 60 <= retry_delay(3, key).total_seconds() <= 75
    assert 300 <= retry_delay(4, key).total_seconds() <= 360
    assert 300 <= retry_delay(99, key).total_seconds() <= 360
