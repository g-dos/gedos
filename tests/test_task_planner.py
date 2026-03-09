from unittest.mock import Mock

from core.task_planner import (
    _extract_json_from_response,
    _is_multi_step_task,
    plan_task,
)


def test_is_multi_step_task_detects_indicator_words() -> None:
    assert _is_multi_step_task("open VS Code then run tests")


def test_is_multi_step_task_detects_multiple_action_words() -> None:
    assert _is_multi_step_task("open project run tests")


def test_is_multi_step_task_detects_long_task() -> None:
    assert _is_multi_step_task("one two three four five six seven eight nine")


def test_is_multi_step_task_returns_false_for_simple_task() -> None:
    assert not _is_multi_step_task("status")


def test_plan_task_returns_single_step_for_simple_task(monkeypatch) -> None:
    llm_mock = Mock(return_value='[{"agent":"terminal","action":"echo hi"}]')
    monkeypatch.setattr("core.llm.complete", llm_mock)

    plan = plan_task("status")

    assert plan.is_multi_step is False
    assert plan.steps == []
    llm_mock.assert_not_called()


def test_plan_task_generates_multi_step_and_filters_invalid_steps(monkeypatch) -> None:
    response = """[
      {"agent":"terminal","action":"git status","expected_result":"clean"},
      {"agent":"invalid","action":"noop"},
      {"agent":"web"},
      "not-a-dict"
    ]"""
    llm_mock = Mock(return_value=response)
    monkeypatch.setattr("core.llm.complete", llm_mock)

    plan = plan_task("open project and run tests")

    assert plan.is_multi_step is True
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.agent == "terminal"
    assert step.action == "git status"
    assert step.expected_result == "clean"
    llm_mock.assert_called_once()


def test_plan_task_falls_back_when_no_json_steps(monkeypatch) -> None:
    llm_mock = Mock(return_value="I cannot provide a plan")
    monkeypatch.setattr("core.llm.complete", llm_mock)

    plan = plan_task("open and build app")

    assert plan.is_multi_step is False
    assert plan.steps == []


def test_plan_task_falls_back_when_all_steps_invalid(monkeypatch) -> None:
    llm_mock = Mock(
        return_value='[{"agent":"bad","action":"x"},{"agent":"web"},{"foo":"bar"}]'
    )
    monkeypatch.setattr("core.llm.complete", llm_mock)

    plan = plan_task("open and run")

    assert plan.is_multi_step is False
    assert plan.steps == []


def test_plan_task_handles_llm_exception(monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr("core.llm.complete", _raise)

    plan = plan_task("open and run")

    assert plan.is_multi_step is False
    assert plan.steps == []


def test_extract_json_from_response_parses_direct_array() -> None:
    parsed = _extract_json_from_response('[{"agent":"terminal","action":"pwd"}]')
    assert isinstance(parsed, list)
    assert parsed[0]["action"] == "pwd"


def test_extract_json_from_response_parses_embedded_array() -> None:
    response = 'Here is plan: [{"agent":"web","action":"open example.com"}] done.'
    parsed = _extract_json_from_response(response)
    assert isinstance(parsed, list)
    assert parsed[0]["agent"] == "web"


def test_extract_json_from_response_parses_object_list_fallback() -> None:
    response = '{"agent":"terminal","action":"pwd"}\n{"agent":"terminal","action":"ls"}'
    parsed = _extract_json_from_response(response)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[1]["action"] == "ls"


def test_extract_json_from_response_returns_none_when_unparseable() -> None:
    assert _extract_json_from_response("no json here") is None
