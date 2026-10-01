from pathlib import Path
from types import SimpleNamespace

import dotenv
import pytest
from langchain_core.messages import AIMessage
from streamlit.testing.v1 import AppTest

import graph

APP = str(Path(__file__).resolve().parents[1] / "app.py")
ORIGINAL = 'print("Hello"\n'
FIXED = 'print("Hello")\n'


def button(app, label):
    return next(b for b in app.button if b.label == label)


@pytest.fixture
def configured_app(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("E2B_API_KEY", "test-e2b")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    model = SimpleNamespace(invoke=lambda *a, **kw: AIMessage(content="Inspect the code."))
    model.bind_tools = lambda *a, **kw: model
    monkeypatch.setattr(graph, "_llm", lambda: model)
    def tools(llm, messages, handlers):
        if "propose_edit" in handlers:
            handlers["propose_edit"]({"file_path": "main.py", "new_content": FIXED,
                                      "rationale": "Close the unfinished print instruction so Python can run it."})
            return "Add the missing closing parenthesis."
        return "Python could not run the code because the print instruction was left unfinished."
    monkeypatch.setattr(graph, "_run_tool_loop", tools)
    def checks(root, entrypoint):
        passed = (root / "main.py").read_text() == FIXED
        return {"passed": passed, "summary": "Checks passed" if passed else "Syntax error found",
                "stdout": "Hello" if passed else "SyntaxError: '(' was never closed", "returncode": 0 if passed else 1,
                "infrastructure_error": False, "limitations": "No tests were supplied."}
    monkeypatch.setattr(graph, "run_checks_in_sandbox", checks)
    return AppTest.from_file(APP).run(timeout=20)


def test_paste_diagnose_review_download_and_start_over(configured_app):
    app = configured_app
    assert button(app, "Analyze code").disabled
    app.text_area[0].input(ORIGINAL).run()
    button(app, "Analyze code").click().run(timeout=20)
    assert not app.exception
    root = Path(app.session_state.workspace_handle.name)
    assert (root / "main.py").read_text() == ORIGINAL
    assert app.session_state.pending_review
    assert any("unfinished" in block.value for block in app.markdown)
    assert button(app, "Apply my decisions and check again").disabled
    review = next(r for r in app.radio if r.label == "Your decision")
    review.set_value("Approve this change").run()
    button(app, "Apply my decisions and check again").click().run(timeout=20)
    assert not app.exception
    assert app.session_state.final_state["status"] == "done"
    assert (root / "main.py").read_text() == FIXED
    assert app.get("download_button")
    button(app, "Start a new analysis").click().run()
    assert not app.exception
    assert not root.exists()
    assert not app.session_state.run_started


def test_provider_error_can_retry_failed_checkpoint(configured_app, monkeypatch):
    app = configured_app
    original_planner = graph.planner_node
    attempts = []
    def fail(state):
        if not attempts:
            attempts.append(True)
            raise RuntimeError("429 rate_limit_exceeded")
        return original_planner(state)
    monkeypatch.setattr(graph, "planner_node", fail)
    # Rebuild the graph to bind the controlled failure.
    from langgraph.checkpoint.memory import InMemorySaver
    app.session_state.graph = graph.build_graph(InMemorySaver())
    app.text_area[0].input(ORIGINAL).run()
    button(app, "Analyze code").click().run(timeout=20)
    assert not app.exception
    assert "usage limit" in app.error[0].value
    button(app, "Retry this step").click().run(timeout=20)
    assert not app.exception
    assert app.session_state.run_error is None
    assert app.session_state.pending_review
    button(app, "Start a new analysis").click().run()
    monkeypatch.setattr(graph, "planner_node", original_planner)
    assert not app.exception
    assert not app.session_state.run_started


def test_approve_all_applies_multiple_files_in_one_review(configured_app, monkeypatch):
    app = configured_app
    def propose_batch(llm, messages, handlers):
        if 'propose_edit' in handlers:
            for name, content in [('main.py', FIXED), ('helper.py', 'def one():\n    return 1\n\ndef two():\n    return 2\n')]:
                handlers['propose_edit']({'file_path': name, 'new_content': content,
                                           'rationale': 'Grouped changes for the complete file.'})
            return 'Review both files together.'
        return 'Multiple supported changes are grouped for review.'
    monkeypatch.setattr(graph, '_run_tool_loop', propose_batch)
    app.text_area[0].input(ORIGINAL).run()
    button(app, 'Analyze code').click().run(timeout=20)
    assert not app.exception
    root = Path(app.session_state.workspace_handle.name)
    assert (root / 'main.py').read_text() == ORIGINAL
    assert not (root / 'helper.py').exists()
    assert len(app.session_state.pending_review['diffs']) == 2
    assert len([r for r in app.radio if r.label == 'Your decision']) == 2
    button(app, 'Approve all suggested changes').click().run(timeout=20)
    assert not app.exception
    assert (root / 'main.py').read_text() == FIXED
    assert 'def two():' in (root / 'helper.py').read_text()
    assert len(app.session_state.final_state['applied_diffs']) == 2
    assert app.session_state.final_state['iteration'] == 1
    button(app, 'Start a new analysis').click().run()
