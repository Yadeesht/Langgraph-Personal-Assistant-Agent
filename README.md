 # 🤖 JARVIS — Advanced Agentic AI OS

<p align="center">
    <picture>
        <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/yourusername/jarvis-agentic-os/main/docs/assets/jarvis-logo-light.png">
        <img src="https://raw.githubusercontent.com/yourusername/jarvis-agentic-os/main/docs/assets/jarvis-logo-dark.png" alt="JARVIS AI OS" width="500">
    </picture>
</p>

<p align="center">
  <strong>AT YOUR SERVICE.</strong>
</p>

<p align="center">
  <a href="https://github.com/yourusername/jarvis-agentic-os/actions"><img src="https://img.shields.io/github/actions/workflow/status/yourusername/jarvis-agentic-os/ci.yml?branch=main&style=for-the-badge" alt="CI status"></a>
  <a href="https://github.com/yourusername/jarvis-agentic-os/releases"><img src="https://img.shields.io/github/v/release/yourusername/jarvis-agentic-os?include_prereleases&style=for-the-badge" alt="GitHub release"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-success.svg?style=for-the-badge" alt="MIT License"></a>
</p>

**JARVIS** is a _personal Agentic AI operating system_ built on a distributed **Multi-Server MCP (Model Context Protocol)** architecture and orchestrated via **LangGraph**. It goes beyond simple chatbot interactions by functioning as a proactive, context-aware agent capable of executing complex workflows across Google Workspace, managing long-term semantic memory, and rendering a live Voice UI via Chainlit. 

If you want a multi-agent orchestration system that feels local, infinitely scalable, and incredibly fast, this is it.

[Docs](./SYSTEM.md) · [Architecture](./SYSTEM.md#architecture) · [Report Bug](https://github.com/yourusername/jarvis-agentic-os/issues) · [Request Feature](https://github.com/yourusername/jarvis-agentic-os/issues)

## ⚡ Quick start (TL;DR)

Runtime: **Python ≥3.11**. We strongly recommend using [`uv`](https://github.com/astral-sh/uv) for lightning-fast dependency resolution.

```bash
# 1. Clone the repository
git clone [https://github.com/yourusername/jarvis-agentic-os.git](https://github.com/yourusername/jarvis-agentic-os.git)
cd jarvis-agentic-os

# 2. Install dependencies
uv pip install -r requirements.txt

# 3. Set up your environment variables
cp .env.example .env

# 4. Launch the Voice-Enabled UI!
chainlit run frontend/chainlit_app.py -w
✨ Highlights
Turnstile Routing — A strict hierarchical LangGraph architecture where a Main Supervisor routes tasks to specialized sub-agents without context bloat.

Enterprise Workspace — 50+ specialized Google Workspace tools intelligently split across domain-specific workers (document_agent, data_agent, presentation_agent).

Episodic RAG Memory — Automatically chunks, embeds, and stores daily conversational logs using a sliding token window for deep temporal recall.

Knowledge Graph — Extracts and formalizes entities and relationships into a KuzuDB graph, allowing JARVIS to "learn" over time.

Code Sandbox — Dynamic Python execution environment where the agent can write, test, and run code.

Chainlit Voice UI — A sleek, modern web interface supporting real-time text chat, microphone audio streaming, and configurable voice TTS output.

🏗️ How it works (Architecture)
JARVIS utilizes a highly efficient "One-Way Turnstile" sub-graph pattern. Instead of a massive monolithic agent drowning in 50+ tool schemas, the Main Supervisor distributes tasks to specialized workers.

Plaintext
User (Text / Voice via Chainlit)
               │
               ▼
┌───────────────────────────────┐
│        Main Supervisor        │
│       (LangGraph Core)        │
└──────────────┬────────────────┘
               │
               ├─ Communication Agent
               ├─ Planning Agent
               ├─ Code Execution Sandbox
               └─ Content Supervisor (The Turnstile)
                         │
                         ├─ Document Agent (Drive / Docs)
                         ├─ Data Agent (Sheets / Forms)
                         └─ Presentation Agent (Slides)
(For a deep dive into the routing logic, database schemas, and tool definitions, please see SYSTEM.md).

🌟 Star History
🤝 Community & Contributors
JARVIS is built for developers who want to push the boundaries of what local Agentic frameworks can do. Contributions for new MCP servers, RAG optimizations, or UI features are highly encouraged! See CONTRIBUTING.md for guidelines.

Special thanks to all the incredible architects who have contributed to JARVIS:

<p align="left">
<a href="https://www.google.com/search?q=https://github.com/yourusername/jarvis-agentic-os/graphs/contributors">
<img src="https://www.google.com/search?q=https://contrib.rocks/image%3Frepo%3Dyourusername/jarvis-agentic-os" alt="Contributors" />
</a>
</p>

<p align="center">
<i>"Sometimes you gotta run before you can walk."</i>
</p>