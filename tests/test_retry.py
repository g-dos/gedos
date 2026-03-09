from unittest.mock import Mock, patch

import pytest

from core.retry import retry_with_backoff


def test_retry_happy_path_succeeds_first_attempt() -> None:
    fn = Mock(return_value="ok")

    with patch("core.retry.time.sleep") as sleep_mock:
        result = retry_with_backoff(fn, max_attempts=3, base_delay=0.1)

    assert result == "ok"
    assert fn.call_count == 1
    sleep_mock.assert_not_called()


def test_retry_retries_then_succeeds() -> None:
    fn = Mock(side_effect=[ValueError("boom-1"), ValueError("boom-2"), "done"])

    with patch("core.retry.time.sleep") as sleep_mock:
        result = retry_with_backoff(fn, max_attempts=4, base_delay=0.5, exceptions=(ValueError,))

    assert result == "done"
    assert fn.call_count == 3
    assert sleep_mock.call_count == 2
    assert sleep_mock.call_args_list[0].args[0] == 0.5
    assert sleep_mock.call_args_list[1].args[0] == 1.0


def test_retry_max_retries_exceeded_raises_last_exception() -> None:
    fn = Mock(side_effect=ValueError("always fails"))

    with patch("core.retry.time.sleep") as sleep_mock:
        with pytest.raises(ValueError, match="always fails"):
            retry_with_backoff(fn, max_attempts=3, base_delay=0.25, exceptions=(ValueError,), label="unit")

    assert fn.call_count == 3
    assert sleep_mock.call_count == 2
    assert sleep_mock.call_args_list[0].args[0] == 0.25
    assert sleep_mock.call_args_list[1].args[0] == 0.5


def test_retry_non_matching_exception_is_not_retried() -> None:
    fn = Mock(side_effect=RuntimeError("unexpected"))

    with patch("core.retry.time.sleep") as sleep_mock:
        with pytest.raises(RuntimeError, match="unexpected"):
            retry_with_backoff(fn, max_attempts=5, exceptions=(ValueError,))

    assert fn.call_count == 1
    sleep_mock.assert_not_called()


def test_retry_zero_attempts_hits_type_checker_fallback_raise() -> None:
    fn = Mock(return_value="never-called")

    with pytest.raises(TypeError):
        retry_with_backoff(fn, max_attempts=0)

    fn.assert_not_called()
