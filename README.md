# Coding Agent Harness 🛡️🤖

Created by **[Smit Mahajan](https://github.com/smitmahajan210)**

A human-gated AI coding agent harness built with **LangGraph**, **Groq / OpenAI**, and **E2B Ephemeral Sandboxes**. Paste Python or upload a project in the dashboard. The harness checks the code, explains observed failures in plain language, and suggests changes for approval. Approved changes are checked again and can be downloaded. No technical bug ticket or GitHub file edit is required.

---

## 🚀 Key Features

- 📥 **Paste or upload code**: Python files or a ZIP project, with a separate temporary workspace for each analysis. The shopping cart is an optional example.
- 🔎 **Automatic diagnosis**: Syntax checks, discovered pytest tests, and an optional script run happen in E2B before the model proposes changes. Expected behavior can be described optionally.
- 💬 **Understandable review**: Plain-language explanations, current and proposed code side by side, an exact diff, and a ZIP download of the approved working copy.
- 🛡️ **Human-Gated File Edits**: The AI agent **cannot write to disk directly**. It calls `propose_edit`, computing unified diffs for human review. LangGraph's native `interrupt()` pauses execution until you approve or reject the patch.
- 🔄 **Real-Time Feedback Loop**: If you reject a proposed change with specific instructions (e.g., *"preserve the public function signature"*), the feedback is fed back into the coder's prompt for automatic revision.
- 🧩 **Role-Separated Agent Crew**:
  - **Planner Agent**: Analyzes tickets/objectives and drafts a structured implementation strategy.
  - **Explorer Agent**: Inspects workspace files directly with `read_file` and `list_dir` (never guesses code).
  - **Coder Agent**: Proposes precise file diffs via unified patch generation.
  - **Tester Node**: Checks Python syntax, runs existing pytest tests, and optionally executes a selected script in an ephemeral sandbox.
- 🧪 **Sandboxed Execution (E2B)**: The agent's verification tests run inside an isolated [E2B sandbox VM](https://e2b.dev). The CLI also runs a local baseline unless you pass `--skip-baseline`.
- 💻 **Dual Review Interfaces**:
  - **Rich Terminal CLI**: Interactive CLI rendering colored diffs, agent handoffs, and approval prompts.
  - **Streamlit Web UI**: Visual dashboard for inspecting multi-file diffs and submitting feedback.
- ⚙️ **Offline Preview Mode**: Rehearse the review interface with a representative patch using `--preview --skip-baseline`, without API calls or workspace edits.

---

## 🛠️ Tech Stack

- **Framework & Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/), LangChain
- **LLM Engine**: [Groq](https://console.groq.com) (`openai/gpt-oss-120b`) / [OpenAI](https://platform.openai.com)
- **Sandboxed Execution**: [E2B](https://e2b.dev) (Isolated pytest runner)
- **UI & Visualization**: [Streamlit](https://streamlit.io/) & [Rich](https://rich.readthedocs.io/) (Terminal formatting)

---

## 🏗️ Architecture & Workflow

```
Paste/upload → Initial E2B checks → Planner → Explorer → Coder
                                                       │
                             No supported fix → Findings / questions → END
                                                       │ proposals
                                                       ▼
                                         Human review (pause)
                                                       │
                                         Apply approved changes
                                                       │
                                              E2B verification
                                                       │
                           Pass → END      Failure / feedback → Coder
                                           Attempt limit → Report remaining issues
```

If no supported fix is found, the dashboard finishes with its findings and any unanswered questions. It does not keep retrying or silently invent requirements. Infrastructure/setup failures stop the run separately from code failures. The CLI retains its objective-based sample workflow and skips the new initial-check node.

---

## 📦 Getting Started

### Prerequisites

- **Python**: 3.10+
- **LLM API Key**: [Groq API Key](https://console.groq.com) or [OpenAI API Key](https://platform.openai.com)
- **Sandbox Key**: [E2B API Key](https://e2b.dev)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/smitmahajan210/coding_agent_harness.git
   cd coding_agent_harness
   ```

2. **Install dependencies:**
   Using `uv` (recommended):
   ```bash
   uv sync --frozen
   ```
   The committed `.python-version` selects Python 3.14 for local and Render runs.

3. **Configure Environment Variables:**
   Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

   Update `.env` with your API keys:
   ```env
   GROQ_API_KEY="your_groq_api_key"
   OPENAI_MODEL="openai/gpt-oss-120b"
   E2B_API_KEY="your_e2b_api_key"
   MAX_ITERATIONS="4"
   APP_PASSWORD=""
   ```

   Create the model key in [Groq Console](https://console.groq.com/keys) and the sandbox key in the [E2B dashboard](https://console.e2b.dev). Both are required for live runs; preview mode needs neither. Keep `.env` local—it is ignored by Git. `APP_PASSWORD` is optional locally and required for the Render deployment below.

   To use the existing OpenAI adapter instead, remove `GROQ_API_KEY`, set `OPENAI_API_KEY`, and choose an appropriate `OPENAI_MODEL`. Remove any Groq-specific `OPENAI_API_BASE` or `OPENAI_BASE_URL` from an older configuration.

---

## ⚙️ Usage & Execution

### 1. Terminal Mode (Interactive CLI)
Run the agent harness directly in your terminal:
```bash
uv run python cli.py --skip-baseline
```

### 2. Offline Preview Mode (Dry-Run Rehearsal)
Walk through the entire ticket, plan, and diff approval flow without making API calls or modifying files:
```bash
uv run python cli.py --preview --skip-baseline
```

### 3. Streamlit Web Dashboard
Launch the visual review dashboard in your web browser:
```bash
uv run streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501):

1. Choose **Paste code**, **Upload files**, or **Try an example**.
2. Add your Python code. For a ZIP project, preserve relative paths and include existing tests. A root `requirements.txt` can specify dependencies; other file types and hidden files are skipped. Limits: 40 accepted files, 100 KB per file, 500 KB total code, 5 MB per upload.
3. Optionally choose a script to run, or add a plain-language description of the expected behavior. A single uploaded/pasted application file is selected automatically when there are no tests.
4. Click **Analyze code**. Read what failed, why, and which details remain uncertain.
5. Review the explanation and the full current/suggested code. Changed lines are highlighted: green `+` for additions/changes, red `−` for removed/replaced lines. Related fixes are grouped into one proposal per file. Use **Approve all suggested changes** to approve the entire batch, or review files individually and request a different fix. No approval is preselected.
6. Submit your decisions to apply approved edits and run checks again. Download the current code as a ZIP when finished.

Checks and uploaded scripts run in E2B, never on the Streamlit host. Existing tests and the dependency manifest are protected from model edits. The original files on your computer are unchanged. Start a new analysis to discard the temporary working copy and submit another project.

**Verification limits:** Without tests, checks cover syntax and, optionally, one noninteractive script run. A passing result does not prove business logic or all inputs are correct. The AI is instructed to distinguish evidence from hypotheses and ask about unclear intent; its suggestions still require review. Programs requiring keyboard input, server processes, external credentials, or additional data files need an appropriate test setup. This version accepts Python projects only.

Remove `--skip-baseline` from a CLI command if you also want to run the sample tests locally before the terminal workflow starts.

---

## Deploy the dashboard on Render

The repository includes a [Render Blueprint](render.yaml). It installs the exact dependencies in `uv.lock`, starts Streamlit on Render's assigned port, and uses `/_stcore/health` for health checks. No Dockerfile or separate requirements file is needed.

1. Commit and push these files to your GitHub repository, including `render.yaml`, `.python-version`, `.streamlit/config.toml`, `pyproject.toml`, and `uv.lock`.
2. In the [Render dashboard](https://dashboard.render.com), choose **New → Blueprint** and connect this repository. Use the repository root and the `render.yaml` Blueprint.
3. Enter the three prompted values:

   | Variable | Value |
   | --- | --- |
   | `GROQ_API_KEY` | Your Groq API key |
   | `E2B_API_KEY` | Your E2B API key |
   | `APP_PASSWORD` | A password you choose for signing in to the hosted demo |

4. Apply the Blueprint and wait for the build and deployment to finish.
5. Open the service's `onrender.com` URL, sign in with `APP_PASSWORD`, and start a run.

The Blueprint sets `OPENAI_MODEL=openai/gpt-oss-120b` and `MAX_ITERATIONS=4` automatically. API keys belong in Render's environment settings, not in the YAML file.

If creating a **Web Service** manually instead of using a Blueprint, choose the Python runtime and use:

```text
Build command: uv sync --frozen
Start command: .venv/bin/python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT
Health check path: /_stcore/health
```

Set the same environment variables listed above. The Streamlit configuration disables file watching so that applying a code proposal does not trigger an unwanted application reload. CORS and XSRF protections retain their defaults.

### Deployment behavior

- The Blueprint selects Render's free instance type. Free services can sleep when idle; the first visit may take time to start. Groq and E2B usage is billed or limited separately by those providers.
- Dashboard analyses use separate temporary workspaces and graph checkpoints. API quotas remain shared across users.
- Checkpoints are in memory, and uploads/edits are on Render's ephemeral filesystem. A restart, redeployment, or expired session can discard them. Download results before starting a new analysis or leaving the session.
- `APP_PASSWORD` protects access to the hosted demo. Share that password with reviewers instead of sharing API keys.

See [Render Blueprints](https://render.com/docs/infrastructure-as-code), [uv support](https://render.com/docs/uv-version), and [free service limits](https://render.com/docs/free).

### Local verification

```bash
uv run pytest tests -q
uv run python cli.py --preview --skip-baseline --preview-decision approve
```

The harness tests cover uploads, path validation, workspace isolation, approval/rejection, protected tests, check failures, and the dashboard flow without API calls. The separate `workspace/tests` suite targets the optional cart sample; its current result depends on whether the CLI has already fixed it.

---

## 📂 Repository Structure

```
coding_agent_harness/
├── cli.py                  # Rich terminal interactive CLI & offline preview
├── app.py                  # Paste/upload, plain-language diagnosis, approval, downloads
├── uploads.py              # Submission validation and per-run temporary workspaces
├── graph.py                # LangGraph StateGraph nodes (Planner, Explorer, Coder, Tester)
├── tools.py                # Workspace inspection & proposed diff tools
├── sandbox.py              # E2B syntax checks, pytest, and selected-script execution
├── tests/                  # Offline workflow, upload, sandbox, and UI regression tests
├── demo_data.py            # Seeded demo tickets & sample patches
├── workspace/              # Sample target codebase for agent evaluation
│   ├── cart.py             # Buggy shopping cart module (seeded test ticket)
│   └── tests/test_cart.py  # Pytest suite
├── pyproject.toml
└── .env.example
```

---

## 👤 Author

**Smit Mahajan**
- **GitHub**: [@smitmahajan210](https://github.com/smitmahajan210)

---
