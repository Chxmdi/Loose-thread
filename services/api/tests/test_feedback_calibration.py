from loose_thread_api.feedback_calibration import FeedbackCalibrationRepository


def test_completed_session_produces_positive_bounded_signals() -> None:
    signals = FeedbackCalibrationRepository._signals(
        "session_completed",
        {"outcome": "done", "fit": "right"},
    )

    assert signals.kind == 1.0
    assert signals.duration == 1.0
    assert signals.context == 1.0
    assert FeedbackCalibrationRepository._bounded(1.5, lower=0.1, upper=0.9) == 0.9


def test_not_now_is_not_misread_as_dislike() -> None:
    signals = FeedbackCalibrationRepository._signals(
        "retrieval_action",
        {"action": "not_now"},
    )

    assert signals.kind == 0.0
    assert signals.duration == 0.0
    assert signals.context == 0.0
