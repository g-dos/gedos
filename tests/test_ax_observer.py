from unittest.mock import MagicMock, patch

from core import ax_observer


def test_unavailable_start_is_noop() -> None:
    callback = MagicMock()
    with patch.object(ax_observer, "AX_OBSERVER_AVAILABLE", False):
        observer = ax_observer.AXObserver(callback)
        observer.start()
    callback.assert_not_called()


def test_on_change_callback_called() -> None:
    callback = MagicMock()
    with patch.object(ax_observer, "AX_OBSERVER_AVAILABLE", True):
        observer = ax_observer.AXObserver(callback)
        observer._current_pid = 1234
        observer._ax_callback(None, None, "AXFocusedWindowChanged", None)
    callback.assert_called_once_with("AXFocusedWindowChanged", 1234)


def test_ax_callback_exception_does_not_crash() -> None:
    callback = MagicMock(side_effect=RuntimeError("boom"))
    with patch.object(ax_observer, "AX_OBSERVER_AVAILABLE", True):
        observer = ax_observer.AXObserver(callback)
        observer._current_pid = 4321
        observer._ax_callback(None, None, "AXFocusedWindowChanged", None)


def test_get_frontmost_app_name_unavailable() -> None:
    with patch.object(ax_observer, "AX_OBSERVER_AVAILABLE", False):
        assert ax_observer.get_frontmost_app_name() == ""


def test_stop_cleans_up() -> None:
    callback = MagicMock()
    fake_thread = MagicMock()
    fake_thread.start = MagicMock()

    with patch.object(ax_observer, "AX_OBSERVER_AVAILABLE", True), patch.object(
        ax_observer.threading, "Thread", return_value=fake_thread
    ), patch.object(ax_observer.AXObserver, "_teardown_observer") as teardown_mock:
        observer = ax_observer.AXObserver(callback)
        observer.start()
        observer.stop()

    assert observer._running is False
    teardown_mock.assert_called()
