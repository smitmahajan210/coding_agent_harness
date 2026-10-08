"""Offline checks for provider configuration and hosted-demo access."""
from argparse import Namespace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import dotenv
import pytest
from rich.console import Console
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    # Never load a developer's real API keys or contact a provider in these tests.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    for name in (
        "GROQ_API_KEY", "OPENAI_API_KEY", "NEBIUS_API_KEY", "E2B_API_KEY",
        "APP_PASSWORD", "RENDER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_cli_accepts_groq_key_without_openai_key(monkeypatch):
    import cli

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("E2B_API_KEY", "test-e2b-key")
    graph = SimpleNamespace(
        get_state=lambda config: SimpleNamespace(
            values={"last_test_passed": True, "iteration": 1}
        )
    )
    monkeypatch.setattr(cli, "build_graph", lambda **kwargs: graph)
    monkeypatch.setattr(cli, "stream_until_pause", lambda *args: None)
    args = Namespace(skip_baseline=True, objective="Test startup", max_iterations=4)

    assert cli.run_live(Console(file=StringIO()), args) == 0


def test_groq_adapter_can_be_constructed(monkeypatch):
    from graph import _llm
    from langchain_groq import ChatGroq

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-120b")
    model = _llm()

    assert isinstance(model, ChatGroq)
    assert model.model_name == "openai/gpt-oss-120b"


def test_dashboard_accepts_groq_key_without_openai_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("E2B_API_KEY", "test-e2b-key")
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=20)

    assert not app.exception
    app.radio[0].set_value("Try an example").run()
    start = next(button for button in app.button if button.label == "Analyze code")
    assert not start.disabled


@pytest.mark.parametrize("legacy_password", [None, "old-demo-password"])
def test_render_opens_dashboard_directly(monkeypatch, legacy_password):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("E2B_API_KEY", "test-e2b-key")
    if legacy_password is not None:
        monkeypatch.setenv("APP_PASSWORD", legacy_password)
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=20)

    assert not app.exception
    assert any(title.value == "Understand and fix your code" for title in app.title)
    assert not any(field.label == "Demo password" for field in app.text_input)
    assert not any(button.label == "Sign in" for button in app.button)
    app.radio[0].set_value("Try an example").run()
    start = next(button for button in app.button if button.label == "Analyze code")
    assert not start.disabled
