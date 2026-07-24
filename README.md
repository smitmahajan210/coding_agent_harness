# Coding Agent Harness 🛡️🤖

Created by **[Smit Mahajan](https://github.com/smitmahajan210)**

A deep, human-gated AI coding agent harness built with **LangGraph**, **Groq / OpenAI**, and **E2B Ephemeral Sandboxes**. The harness plans, explores repository structures, proposes code diffs, enforces a human approval gate before modifying any file on disk, and executes test suites in isolated sandboxes.

---

## 🚀 Key Features

- 🛡️ **Human-Gated File Edits**: The AI agent **cannot write to disk directly**. It calls `propose_edit`, computing unified diffs for human review. LangGraph's native `interrupt()` pauses execution until you approve or reject the patch.
- 🔄 **Real-Time Feedback Loop**: If you reject a proposed change with specific instructions (e.g., *"preserve the public function signature"*), the feedback is fed back into the coder's prompt for automatic revision.
- 🧩 **Role-Separated Agent Crew**:
  - **Planner Agent**: Analyzes tickets/objectives and drafts a structured implementation strategy.
  - **Explorer Agent**: Inspects workspace files directly with `read_file` and `list_dir` (never guesses code).
  - **Coder Agent**: Proposes precise file diffs via unified patch generation.
  - **Tester Agent**: Uploads approved code to an ephemeral VM sandbox and executes `pytest`.
- 🧪 **Sandboxed Execution (E2B)**: Tests run inside an isolated [E2B sandbox VM](https://e2b.dev)—zero code is executed directly on your host machine.
- 💻 **Dual Review Interfaces**:
  - **Rich Terminal CLI**: Interactive CLI rendering colored diffs, agent handoffs, and approval prompts.
  - **Streamlit Web UI**: Visual dashboard for inspecting multi-file diffs and submitting feedback.
- ⚙️ **Offline Preview Mode**: Test and demo the entire workflow (`--preview`) with zero API calls or file mutations.

---

## 🛠️ Tech Stack

- **Framework & Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/), LangChain
- **LLM Engine**: [Groq](https://console.groq.com) (`llama-3.3-70b-versatile`) / [OpenAI](https://platform.openai.com)
- **Sandboxed Execution**: [E2B](https://e2b.dev) (Isolated pytest runner)
- **UI & Visualization**: [Streamlit](https://streamlit.io/) & [Rich](https://rich.readthedocs.io/) (Terminal formatting)

---

## 🏗️ Architecture & Workflow

```
START ──▶ Planner ──▶ Explorer ──▶ Coder ──▶ Diff Review ⏸️ (interrupt: Human Gate)
                                    ▲             │
                                    │             ▼ (Approved Diffs Only)
                                    │        Apply Diffs ──▶ Tester (E2B Sandbox)
                                    │                            │
                                    └── (Tests Fail / Rejected) ◀┤
                                        (with Human Feedback)    └── (Tests Pass) ──▶ END
```

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
   uv sync
   ```
   Or standard `pip`:
   ```bash
   pip install -e .
   ```

3. **Configure Environment Variables:**
   Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

   Update `.env` with your API keys:
   ```env
   OPENAI_API_KEY="your_groq_or_openai_api_key"
   OPENAI_API_BASE="https://api.groq.com/openai/v1"
   OPENAI_MODEL="llama-3.3-70b-versatile"
   E2B_API_KEY="your_e2b_api_key"
   MAX_ITERATIONS="4"
   ```

---

## ⚙️ Usage & Execution

### 1. Terminal Mode (Interactive CLI)
Run the agent harness directly in your terminal:
```bash
uv run python cli.py
```

### 2. Offline Preview Mode (Dry-Run Rehearsal)
Walk through the entire ticket, plan, and diff approval flow without making API calls or modifying files:
```bash
uv run python cli.py --preview
```

### 3. Streamlit Web Dashboard
Launch the visual review dashboard in your web browser:
```bash
uv run streamlit run app.py
```

---

## 📂 Repository Structure

```
coding_agent_harness/
├── cli.py                  # Rich terminal interactive CLI & offline preview
├── app.py                  # Streamlit visual dashboard reviewer
├── graph.py                # LangGraph StateGraph nodes (Planner, Explorer, Coder, Tester)
├── tools.py                # Workspace inspection & proposed diff tools
├── sandbox.py              # E2B Sandbox wrapper for isolated pytest runs
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
