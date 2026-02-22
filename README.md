# 🤖 JARVIS — Advanced Agentic AI OS

<p align="center">
    <picture>
        <img src="https://github.com/Yadeesht/Agentic-AI-EXP/blob/main/docs/images/LOGO.png" alt="JARVIS" width="500">
    </picture>
</p>


<p align="center">
  <strong>AT YOUR SERVICE.</strong><br/>
  Multi-Agent • LangGraph • MCP • RAG + Knowledge Graph • Voice UI
</p>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://github.com/Yadeesht/Agentic-AI-EXP"><img src="https://img.shields.io/badge/Repo-Agentic--AI--EXP-181717?style=for-the-badge&logo=github" alt="GitHub Repo"></a>
  <a href="https://github.com/Yadeesht/Agentic-AI-EXP/blob/main/SYSTEM.md"><img src="https://img.shields.io/badge/System-Architecture-6f42c1?style=for-the-badge" alt="System Docs"></a>
</p>

JARVIS is a personal agentic AI operating system built on a distributed **Multi-Server MCP** architecture and orchestrated with **LangGraph**. It routes tasks across specialized agents, executes code in a sandbox, and supports both text + voice interactions through Chainlit.

---

## ✨ Why this project

- **True multi-agent routing** with a central Supervisor and domain workers.
- **Google Workspace automation** across Gmail, Chat, Calendar, Drive, Docs, Sheets, Slides, Forms, and Tasks.
- **Long-term memory** via Episodic RAG + Knowledge Graph.
- **Voice-enabled UX** with continuous listening controls and optional spoken output.

---

## 🧭 Table of contents

- [1) Prerequisites](#1-prerequisites)
- [2) Installation](#2-installation)
- [3) Environment and credentials setup](#3-environment-and-credentials-setup)
- [4) Run modes](#4-run-modes)
- [5) Chainlit frontend controls](#5-chainlit-frontend-controls)
- [6) How to use (interactive examples)](#6-how-to-use-interactive-examples)
- [7) Architecture overview](#7-architecture-overview)
- [8) Project structure](#8-project-structure)
- [9) Troubleshooting](#9-troubleshooting)

---

## 1) Prerequisites

<details open>
<summary><strong>Required before first run</strong></summary>

- Python **3.11+** (project metadata allows 3.10+, but 3.11+ is recommended).
- A virtual environment (`.venv`) activated.
- API keys for at least one LLM provider (OpenRouter recommended).
- Google OAuth credentials file (`setup_cred.json`) for Workspace tools.
- Model folders present in `models/` (Has TTS, STT and embedding models).

</details>

<details>
<summary><strong>Optional but recommended</strong></summary>

- `uv` for fast installation.
- `honcho` for running multiple MCP servers from `Procfile needed when running in terminal.
- Working microphone + speakers for voice loop.

</details>

---

## 2) Installation

### Windows (PowerShell)

```powershell
git clone https://github.com/Yadeesht/Agentic-AI-EXP.git
cd Agentic-AI-EXP

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### With `uv` (faster)

```powershell
uv pip install -r requirements.txt
```

---

## 3) Environment and credentials setup

### 3.1 Environment file

This repository currently includes `.env,example` (comma in the name). Copy it to `.env`:

```powershell
Copy-Item .env,example .env
```

Fill values in `.env` (minimum):

- `OPENROUTER_API_KEY` (recommended provider)
- `GROQ_API_KEY` (optional)
- `HF_TOKEN` (optional)
- `GOOGLE_PSE_API_KEY` + `GOOGLE_PSE_ENGINE_ID` (if using Google search tools)
- `DEFAULT_THREAD_ID` (for terminal mode)
- `TRANSPORT_MODE=stdio`

### 3.2 Google OAuth files

Place your Google OAuth app credential JSON as:

- `app_mcp/cred/setup_cred.json`

On first use, token files are created under:

- `app_mcp/cred/gmail_token.json`
- `app_mcp/cred/calendar_token.json`
- `app_mcp/cred/gdocs_token.json`
- `app_mcp/cred/gchat_token.json`
- `app_mcp/cred/gtask_token.json`

> Keep credential and token files private. Never commit real secrets.

---

### 3.3 Local models structure

All models are bundled locally under `models/` — no internet connection required at runtime.

```
models/
├── bge-small/              # Embedding model — Knowledge Graph semantic search
│
├── gte-base/               # Embedding model — Episodic RAG vector storage
│
├── stt/                    # Speech-to-Text — faster-whisper (base.en)
│   └── models--Systran--faster-whisper-base.en/
│
└── tts/                    # Text-to-Speech — Piper TTS (ONNX, high quality)
    ├── jarvis-high.onnx
    └── jarvis-high.onnx.json
```

| Folder | Model | Used for |
|---|---|---|
| `bge-small` | BAAI/bge-small-en | Knowledge Graph entity search |
| `gte-base` | thenlper/gte-base | Episodic RAG chunk embedding |
| `stt` | Systran/faster-whisper-base.en | Voice input transcription |
| `tts` | Piper jarvis-high | Spoken response output |

> All four model folders must be present before starting. They are included in this repository.

---

## 4) Run modes

### A) Chainlit web UI (recommended)

```powershell
chainlit run frontend/chainlit_app.py -w
```

Open the URL shown in terminal (typically `http://localhost:8000`).

### B) Terminal mode (`main.py`)

```powershell
python main.py
```

Use `exit`, `quit`, or `bye` to stop.

### C) Start MCP servers manually (advanced)

```powershell
honcho start
```

`Procfile` starts:
- Communication server
- Planning server
- Content server
- Supervisor server

---

## 5) Chainlit frontend controls

From `frontend/chainlit_app.py`, these commands and UI actions are available:

| Action | Purpose |
|---|---|
| `Start Voice Listening` | Starts continuous local listening loop |
| `Stop Voice Listening` | Stops continuous listening |
| `Voice Output On` | Enables spoken responses (TTS) |
| `Voice Output Off` | Disables spoken responses |
| `/voice` | Upload audio file (wav/mp3/m4a/webm) for transcription |
| `/controls` | Re-display voice control buttons |

Session behavior:
- A unique thread ID is generated per Chainlit session.
- If browser audio hooks are available, streamed audio can be transcribed.
- Voice session timeout is managed internally and resumes via wake-word flow.

---

## 6) How to use (interactive examples)

Use these prompts directly after startup:

### Communication
- “Send an email to `john.doe@example.com` with subject `Project Update` and summarize today’s outcomes.”

### Planning
- “Create a 1-hour meeting tomorrow at 2 PM called `Q1 Planning` and add Alice + Bob.”

### Content
- “Create a Google Doc named `Weekly Notes` and add bullet points for priorities, blockers, and actions.”

### Code automation
- “Read CSV files in my Drive folder `Sales Data`, compute monthly totals, and write results to a Sheet called `Monthly Sales Summary`.”

### Voice-first workflow
1. Click **Start Voice Listening**.
2. Speak naturally (or use wake word behavior when idle).
3. Enable **Voice Output On** for spoken responses.
4. Stop with **Stop Voice Listening** when done.

---

## 7) Architecture overview

<p align="center">
  <img src="docs/images/agent_structure_graph.png" alt="JARVIS Agent Graph" width="900">
</p>

JARVIS is built around a **stateful LangGraph** where every node is a purposeful participant — not just a tool-caller.

### Entry and routing

- **`__start__`** is the graph entry point. Each incoming message first passes through `route_start`, which decides whether to update memory, summarize the conversation, or proceed directly to the Supervisor.
- **`supervisor`** is the central decision node. It reads the conversation state and routes to the right domain agent, calls its own tools, or terminates with `FINISH`.

### Domain agents

| Agent | Tools | Handles |
|---|---|---|
| `communication_agent` | `communication_tools` | Gmail, Google Chat |
| `planning_agent` | `planning_tools` | Calendar, Google Tasks |
| `code_agent` | Docker sandbox | Python code generation + execution |
| `content_supervisor` → `document_agent` | `document_tools` | Google Drive, Docs |
| `content_supervisor` → `data_agent` | `data_tools` | Google Sheets, Forms |
| `content_supervisor` → `presentation_agent` | `presentation_tools` | Google Slides |

Each agent runs autonomously in a loop: call tools → return to supervisor with a `FINAL ANSWER` or `TALK TO USER` signal → route to `__end__`.

### Memory and maintenance nodes

- **`summerizer_node`** — condenses long conversation histories before the token limit is hit; routes back to the supervisor seamlessly.
- **`memory_update_node`** — triggered at session boundaries or when context grows stale; writes to both the Episodic RAG and the Knowledge Graph, then returns to the supervisor.

### Flow summary

```
__start__
    │
    ├── [memory needed?]  → memory_update_node → supervisor
    ├── [too long?]       → summerizer_node    → supervisor
    └── [default]         ──────────────────── → supervisor
                                                      │
               ┌──────────────────┬─────────────┬────┴────────────────┐
               ▼                  ▼             ▼                     ▼
      communication_agent   planning_agent  code_agent       content_supervisor
               │                  │                           ┌────┴──────────┐
        communication_tools planning_tools            data_agent  document_agent  presentation_agent
               │                  │                      │            │                │
               └──────────────────┴──────────────────────┴────────────┴────────────────┘
                                                     __end__
```

For full routing logic and state schema, see [SYSTEM.md](./SYSTEM.md).

---

## 8) Project structure

Key runtime files:

- `main.py` — terminal interaction loop
- `frontend/chainlit_app.py` — Chainlit text + voice frontend
- `frontend/chainlit_runtime.py` — frontend runtime bridge to graph backend
- `core/graph.py` — LangGraph orchestration
- `config/settings.py` — model/provider/runtime configuration
- `app_mcp/core/*.py` — MCP server entrypoints
- `rag/` — Episodic RAG + Knowledge Graph logic

---

## 9) Troubleshooting

<details>
<summary><strong>Chainlit starts but no responses</strong></summary>

- Verify `.env` keys are set correctly.
- Check that selected provider key is valid (OpenRouter/Groq/HF).
- Confirm `TRANSPORT_MODE=stdio` and Python environment is active.

</details>

<details>
<summary><strong>Google tools fail with auth errors</strong></summary>

- Ensure `app_mcp/cred/setup_cred.json` is valid OAuth client JSON.
- Delete expired token files in `app_mcp/cred/` and re-authenticate.

</details>

<details>
<summary><strong>Voice input/output issues</strong></summary>

- Test with `/voice` audio upload first.
- Check microphone permissions in browser.
- Ensure local audio dependencies are installed and accessible.

</details>

---

## Docs

- System Deep Dive: [SYSTEM.md](./SYSTEM.md)

<p align="center">
  <i>"Sometimes you gotta run before you can walk."</i>
</p>