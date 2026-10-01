from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import graph
from tools import build_file_diff

ORIGINAL = "print(missing_name)\n"
FIXED = 'print("Hello")\n'


def check_result(passed=False, infrastructure_error=False):
    return {"passed": passed, "summary": "Checks passed" if passed else "Program failed",
            "stdout": "OK" if passed else "NameError: missing_name is not defined",
            "returncode": 0 if passed else 1, "scope": "script", "checks": [],
            "infrastructure_error": infrastructure_error, "limitations": "No behavioral tests supplied."}


@pytest.fixture
def fake_agents(monkeypatch):
    model = SimpleNamespace(invoke=lambda *a, **k: AIMessage(content="Read the file and diagnose the failure."))
    model.bind_tools = lambda *a, **k: model
    monkeypatch.setattr(graph, "_llm", lambda: model)
    briefings = []
    def tool_loop(llm, messages, handlers):
        briefings.append(messages[-1].content)
        if "propose_edit" not in handlers:
            return "What happened: the program used a name before assigning it a value."
        handlers["propose_edit"]({"file_path": "main.py", "new_content": FIXED,
                                  "rationale": "Replace the missing name with the greeting to prevent the crash."})
        return "This suggestion prevents the missing-name error. Please review the intended greeting."
    monkeypatch.setattr(graph, "_run_tool_loop", tool_loop)
    monkeypatch.setattr(graph, "run_checks_in_sandbox", lambda root, entry: check_result((root / "main.py").read_text() == FIXED))
    return briefings


def initial_state(tmp_path):
    (tmp_path / "main.py").write_text(ORIGINAL)
    return {"objective": graph.AUTO_OBJECTIVE, "automatic": True, "workspace_root": str(tmp_path),
            "entrypoint": "main.py", "iteration": 0, "max_iterations": 3}


def test_diagnosis_and_approval_apply_only_to_run_workspace(tmp_path, fake_agents):
    flow = graph.build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "one"}}
    paused = flow.invoke(initial_state(tmp_path), config)
    assert "NameError" in fake_agents[0]
    assert paused["diagnosis"].startswith("What happened")
    assert (tmp_path / "main.py").read_text() == ORIGINAL
    diff = paused["__interrupt__"][0].value["diffs"][0]
    assert diff["old_content"] == ORIGINAL
    assert diff["new_content"] == FIXED
    done = flow.invoke(Command(resume={"decisions": {diff["diff_id"]: {"action": "approve"}}}), config)
    assert done["status"] == "done"
    assert done["last_test_passed"]
    assert (tmp_path / "main.py").read_text() == FIXED


def test_rejection_preserves_code_and_returns_feedback(tmp_path, fake_agents):
    flow = graph.build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "two"}}
    paused = flow.invoke(initial_state(tmp_path), config)
    diff = paused["__interrupt__"][0].value["diffs"][0]
    revised = flow.invoke(Command(resume={"decisions": {diff["diff_id"]: {"action": "reject", "reason": "Keep the output format"}}}), config)
    assert revised["__interrupt__"]
    assert "Keep the output format" in fake_agents[-1]
    assert (tmp_path / "main.py").read_text() == ORIGINAL


def test_rejection_is_not_ignored_when_checks_pass():
    assert graph.route_after_tester({"last_test_passed": True, "review_feedback": "Revise this", "iteration": 1, "max_iterations": 3}) == "coder"


def test_no_proposals_finishes_without_claiming_behavior_is_verified(tmp_path, fake_agents, monkeypatch):
    monkeypatch.setattr(graph, "_run_tool_loop", lambda *a, **k: "The expected output is unclear. What should this print?")
    flow = graph.build_graph(InMemorySaver())
    result = flow.invoke(initial_state(tmp_path), {"configurable": {"thread_id": "three"}})
    assert result["status"] == "needs_attention"
    assert not result["last_test_passed"]
    assert not result.get("test_results")
    assert (tmp_path / "main.py").read_text() == ORIGINAL


def test_infrastructure_failure_does_not_trigger_code_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(graph, "run_checks_in_sandbox", lambda *a: check_result(infrastructure_error=True))
    monkeypatch.setattr(graph, "_llm", lambda: pytest.fail("Should not ask the model to fix unavailable infrastructure"))
    result = graph.build_graph(InMemorySaver()).invoke(initial_state(tmp_path), {"configurable": {"thread_id": "blocked"}})
    assert result["status"] == "blocked"
    assert (tmp_path / "main.py").read_text() == ORIGINAL


def test_stale_file_is_not_overwritten(tmp_path):
    initial_state(tmp_path)
    diff = build_file_diff("main.py", FIXED, "Reason", 0, tmp_path)
    (tmp_path / "main.py").write_text("another user's edit")
    with pytest.raises(ValueError, match="changed since review"):
        graph.apply_diffs_node({"workspace_root": str(tmp_path), "diffs_to_apply": [diff]})
    assert (tmp_path / "main.py").read_text() == "another user's edit"


def test_coder_cannot_modify_tests(tmp_path, fake_agents, monkeypatch):
    def loop(llm, messages, handlers):
        with pytest.raises(ValueError, match="protected"):
            handlers["propose_edit"]({"file_path": "tests/test_main.py", "new_content": "assert True", "rationale": "cheat"})
        return "No proposal"
    monkeypatch.setattr(graph, "_run_tool_loop", loop)
    result = graph.coder_node(initial_state(tmp_path))
    assert result["pending_diffs"] == []
