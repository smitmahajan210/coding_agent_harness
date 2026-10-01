"""Paste/upload Python, diagnose it, and review explained fixes before applying."""
from __future__ import annotations

import hmac
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from demo_data import DEMO_BUGGY_CART
from graph import AUTO_OBJECTIVE, DEFAULT_MAX_ITERATIONS, build_graph
from review import changed_lines, highlighted_code
from uploads import create_workspace, files_from_uploads, is_test_file, validate_files, workspace_zip

load_dotenv()
st.set_page_config(page_title="Code Harness · Understand and fix your code", page_icon="🛠️", layout="wide")

app_password = os.getenv("APP_PASSWORD", "")
if os.getenv("RENDER") and not app_password:
    st.error("Set APP_PASSWORD in the Render environment settings to enable this demo.")
    st.stop()
if app_password and not st.session_state.get("authenticated", False):
    st.title("Code Harness")
    with st.form("sign_in", clear_on_submit=True):
        password = st.text_input("Demo password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        if hmac.compare_digest(password.encode("utf-8"), app_password.encode("utf-8")):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

st.markdown("""
<style>
.block-container {max-width: 1240px; padding-top: 2.5rem; padding-bottom: 4rem;}
h1 {letter-spacing: -.045em;}
.stButton > button {border-radius: 8px; min-height: 44px;}
[data-testid="stCodeBlock"] {border: 1px solid #8883; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

for key, value in {
    "thread_id": str(uuid.uuid4()), "run_started": False,
    "pending_review": None, "final_state": None, "run_error": None,
    "workspace_handle": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value
if "graph" not in st.session_state:
    st.session_state.graph = build_graph(InMemorySaver())

missing = []
if not (os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("NEBIUS_API_KEY")):
    missing.append("GROQ_API_KEY or OPENAI_API_KEY")
if not os.getenv("E2B_API_KEY"):
    missing.append("E2B_API_KEY")


def graph_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}, "recursion_limit": 100}


def reset_run():
    handle = st.session_state.workspace_handle
    if handle:
        handle.cleanup()
    st.session_state.workspace_handle = None
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.graph = build_graph(InMemorySaver())
    st.session_state.run_started = False
    st.session_state.pending_review = None
    st.session_state.final_state = None
    st.session_state.run_error = None


def drive(invoke_arg):
    st.session_state.run_error = None
    labels = {
        "baseline": "Initial checks complete. Understanding what happened…",
        "planner": "Reading your files and explaining the problem…",
        "explorer": "Preparing a suggested fix for your review…",
        "coder": "Code review complete…",
        "apply_diffs": "Your approved changes are saved. Checking them again…",
        "tester": "Verification complete…",
    }
    try:
        with st.status("Checking your code in an isolated environment…", expanded=True) as progress:
            pending = None
            for update in st.session_state.graph.stream(invoke_arg, graph_config(), stream_mode="updates"):
                if update.get("__interrupt__"):
                    pending = update["__interrupt__"][0].value
                else:
                    for node in update:
                        if node in labels:
                            progress.update(label=labels[node])
            st.session_state.pending_review = pending
            snapshot = st.session_state.graph.get_state(graph_config()).values
            st.session_state.final_state = None if pending else snapshot
            progress.update(label="Ready for your review" if pending else "Analysis complete", state="complete")
    except Exception as exc:
        # A failed API request must not strand the interface or expose a traceback.
        message = str(exc)
        if "429" in message or "rate_limit" in message.lower():
            explanation = "The AI provider's usage limit was reached. Wait a little, then retry this step."
        elif "401" in message or "authentication" in message.lower():
            explanation = "The service could not sign in. Check the configured API keys."
        elif "model_not_found" in message:
            explanation = "The selected AI model is unavailable. Choose an available model in the app configuration."
        else:
            explanation = "The analysis could not finish. Retry this step, or start a new analysis."
        st.session_state.run_error = explanation
        # Keep the checkpoint, workspace, and any completed approvals available.


def render_checks(result: dict, title: str):
    if not result:
        return
    st.markdown(f"**{title}**")
    if result.get("infrastructure_error"):
        st.warning(result["summary"])
    elif result.get("passed"):
        st.success(result["summary"])
    else:
        st.warning(result["summary"])
    if result.get("limitations"):
        st.caption(result["limitations"])
    with st.expander("Check details"):
        st.code(result.get("stdout") or "No output was produced.", language="text")


with st.sidebar:
    st.title("Code Harness")
    st.caption("Understand the problem. Review the fix. Keep control.")
    if missing:
        st.warning("Configure " + ", ".join(missing) + " to analyze code.")
    else:
        st.success("Ready to analyze")
    st.caption("Python projects · up to 40 files / 500 KB of code")
    st.caption("Code is sent to the configured AI provider and E2B for analysis and isolated execution.")
    if st.session_state.run_started:
        if st.button("Start a new analysis", use_container_width=True):
            reset_run()
            st.rerun()
    st.divider()
    st.markdown("**What can be checked?**")
    st.caption("Python syntax, existing tests, and a script you choose to run. Programs requiring interactive input or a running web server need a test suite instead.")
    st.caption("Each analysis has its own temporary workspace. Download your result before starting over or leaving the session.")

st.title("Understand and fix your code")
st.write("Add your Python code. We’ll check it, explain what went wrong in everyday language, and suggest a fix for you to approve.")
st.caption("No bug ticket required. If the intended behavior is unclear, we’ll explain what still needs to be clarified.")

files = {}
entrypoint = ""
context = ""
if not st.session_state.run_started:
    st.subheader("1. Add your code")
    source = st.radio("How would you like to add code?", ["Paste code", "Upload files", "Try an example"], horizontal=True)
    validation_error = None
    if source == "Paste code":
        filename = st.text_input("File name", value="main.py")
        content = st.text_area("Your Python code", height=280, placeholder="Paste your Python code here…")
        if content.strip():
            try:
                files = validate_files({filename: content})
            except ValueError as exc:
                validation_error = str(exc)
    elif source == "Upload files":
        uploaded = st.file_uploader("Python files or a ZIP project", type=["py", "zip", "txt"], accept_multiple_files=True)
        st.caption("Include existing tests if you have them. A root requirements.txt can list extra packages. ZIP folder structure is preserved; other file types and hidden files are skipped.")
        if uploaded:
            try:
                files = files_from_uploads([(item.name, item.getvalue()) for item in uploaded])
            except ValueError as exc:
                validation_error = str(exc)
    else:
        files = {
            "cart.py": DEMO_BUGGY_CART,
            "tests/test_cart.py": (Path(__file__).parent / "workspace/tests/test_cart.py").read_text(),
        }
        st.info("A shopping cart example with existing tests. The app will discover the failures itself.")
        with st.expander("View example code"):
            st.code(DEMO_BUGGY_CART, language="python")
    if validation_error:
        st.error(validation_error)
    if files:
        st.caption(f"{len(files)} file(s) ready: " + ", ".join(files))
        candidates = [name for name in files if name.endswith(".py") and not is_test_file(name) and Path(name).name != "__init__.py"]
        has_tests = any(is_test_file(name) and Path(name).name != "conftest.py" for name in files)
        default = 1 if len(candidates) == 1 and not has_tests else 0
        choice = st.selectbox("Also run a program?", ["Checks only"] + candidates, index=default,
                              help="Existing tests are discovered automatically. A selected script runs once without keyboard input, in E2B.")
        entrypoint = "" if choice == "Checks only" else choice
    with st.expander("Anything else we should know? (optional)"):
        context = st.text_area("What should the program do, or what did you notice?", placeholder="For example: this should add up the prices in my shopping list.")
        st.caption("You don’t need to identify the bug. This context helps only when the intended result cannot be inferred from code or tests.")
    if st.button("Analyze code", type="primary", disabled=not files or bool(missing) or bool(validation_error)):
        try:
            handle = create_workspace(files)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.workspace_handle = handle
            st.session_state.run_started = True
            drive({
                "objective": AUTO_OBJECTIVE + ("\nUser context: " + context if context.strip() else ""),
                "workspace_root": handle.name, "automatic": True, "entrypoint": entrypoint,
                "iteration": 0, "max_iterations": DEFAULT_MAX_ITERATIONS,
            })
            st.rerun()

if st.session_state.run_started:
    state = st.session_state.graph.get_state(graph_config()).values
    if st.session_state.run_error:
        st.error(st.session_state.run_error)
        if st.button("Retry this step"):
            # None resumes from the failed checkpoint without repeating completed nodes.
            drive(None)
            st.rerun()
    st.subheader("2. What we found")
    render_checks(state.get("baseline", {}), "Before any changes")
    if state.get("diagnosis"):
        st.markdown(state["diagnosis"])
    if state.get("proposal_summary"):
        st.markdown("**Suggested next step**")
        st.markdown(state["proposal_summary"])

    review_area = st.empty()
    if st.session_state.pending_review and not st.session_state.run_error:
        with review_area.container():
            st.subheader("3. Review the suggested fix")
            st.info("These are suggestions. Your working copy changes only after you approve. The original upload on your computer stays unchanged.")
            payload = st.session_state.pending_review
            st.caption(f"{len(payload['diffs'])} file(s) to review. Each proposal includes all suggested changes for that file—not one approval per line.")
            decisions = {}
            for diff in payload["diffs"]:
                st.markdown(f"**{diff['file_path']}**")
                st.write(diff["rationale"])
                changes = changed_lines(diff["old_content"], diff["new_content"])
                st.caption(
                    f"{len(changes['after'])} added/changed line(s) · "
                    f"{len(changes['before'])} removed/replaced line(s) · "
                    f"{changes['blocks']} change block(s). Green + = suggested change; red − = replaced or removed."
                )
                before, after = st.columns(2)
                with before:
                    st.caption("Current code")
                    st.html(highlighted_code(diff["old_content"], changes["before"], side="before"))
                with after:
                    st.caption("Suggested code — not applied yet")
                    st.html(highlighted_code(diff["new_content"], changes["after"], side="after"))
                with st.expander("Copy full suggested code"):
                    st.code(diff["new_content"], language="python")
                with st.expander("Show exact differences"):
                    st.code(diff["unified_diff"], language="diff")
                action = st.radio("Your decision", ["Choose an option", "Approve this change", "Request a different fix"],
                                  key=f"decision_{diff['diff_id']}", horizontal=True)
                reason = ""
                if action == "Request a different fix":
                    reason = st.text_input("What would you like done differently?", key=f"reason_{diff['diff_id']}",
                                           placeholder="You can describe this in everyday words.")
                decisions[diff["diff_id"]] = {"action": {"Choose an option": "pending", "Approve this change": "approve", "Request a different fix": "reject"}[action], "reason": reason}
            if st.button("Approve all suggested changes", type="primary"):
                approvals = {d["diff_id"]: {"action": "approve", "reason": ""} for d in payload["diffs"]}
                drive(Command(resume={"decisions": approvals}))
                st.rerun()
            if st.button("Apply my decisions and check again", type="primary", disabled=any(d["action"] == "pending" for d in decisions.values())):
                drive(Command(resume={"decisions": decisions}))
                st.rerun()

    for result in state.get("test_results", []):
        render_checks(result, f"After review {result['iteration']}")

    final = st.session_state.final_state
    if final:
        if final.get("status") == "done":
            st.success("Your approved changes passed the selected checks.")
        elif final.get("status") == "reviewed":
            st.info("Review finished. No additional changes were proposed. Read the findings and check limitations above.")
        elif final.get("status") == "blocked":
            st.warning("Checks could not finish. Review the check details above; this is not a confirmed code defect.")
        else:
            st.warning("Some issues or questions remain. The explanation above describes what still needs attention.")
    handle = st.session_state.workspace_handle
    if handle and (final or state.get("applied_diffs")):
        st.download_button("Download current code (.zip)", data=workspace_zip(Path(handle.name)),
                           file_name="reviewed-code.zip", mime="application/zip")
        st.caption("Includes only the current working copy and changes you approved. Unapproved suggestions are excluded.")
