# Multi-Server Agentic AI Framework

This project is a sophisticated, multi-server agentic AI framework built with Python. It features a modular, graph-based architecture orchestrated by a central supervisor agent. The framework is designed to handle complex tasks by delegating them to specialized agents, each running as a separate server process.

## Key Features

*   **Multi-Agent Architecture:** A supervisor agent coordinates a team of specialized agents for communication, planning, and content management.
*   **Graph-Based Workflows:** Uses `langgraph` to define and execute complex, multi-step workflows.
*   **Tool-Based Agents:** Each agent is equipped with a set of tools to perform its tasks, including integrations with Google Workspace (Gmail, Calendar, Drive, etc.) and Google Search.
*   **Code Generation for Complex Tasks:** A `CodeExecutionAgent` can generate and execute Python code in a sandboxed environment to handle complex, multi-tool workflows.
*   **Persistent State:** Uses an `aiosqlite` database to checkpoint the agent's state, allowing it to resume conversations and workflows.
*   **Interactive CLI:** Provides an interactive command-line interface for users to chat with the agent.
*   **Extensive Logging:** Comprehensive logging for debugging and monitoring agent behavior.

## Architecture

The framework is built around a central **Supervisor Agent** that acts as an orchestrator. The supervisor can:

1.  Answer general questions directly.
2.  Use a Google Search tool to find information.
3.  Route tasks to one of three specialized agents:
    *   **Communication Agent:** Handles email and chat operations (Gmail, Google Chat).
    *   **Planning Agent:** Manages calendar and tasks (Google Calendar, Google Tasks).
    *   **Content Agent:** Manages files and documents (Google Drive, Docs, Sheets, Slides, Forms).

Each of these agents runs as a separate server process using `FastMCP`, a custom server implementation likely based on FastAPI. The servers communicate with each other using standard input/output (stdio), but can also be configured to use sockets or HTTP.

The agent's logic is defined as a graph using `langgraph`. This allows for flexible and powerful workflows, including multi-step chains of tool and agent calls. The project generates a visual representation of this graph in `agent_structure_graph.png`.

## Core Components

*   **`main.py`:** The main entry point of the application. It initializes the servers, builds the agent graph, and starts the interactive CLI.
*   **`config/`:** Contains configuration files for the agent.
    *   **`settings.py`:** Defines server configurations, API keys, and other settings.
    *   **`prompts.py`:** Contains the system prompts for the supervisor and specialized agents, defining their roles and behavior.
*   **`core/`:** Contains the core logic for the agents and the graph.
    *   **`agent.py`:** A factory for creating agent nodes in the graph.
    *   **`codeagent.py`:** The `CodeExecutionAgent` that generates and executes Python code.
    *   **`graph.py`:** Defines the `langgraph` graph that orchestrates the agents and tools.
    *   **`state.py`:** Defines the state object that is passed between nodes in the graph.
*   **`MCP/`:** This directory seems to be a custom implementation of a multi-server agent framework.
    *   **`core/`:** Contains the server initialization and the individual server scripts.
    *   **`tools/`:** Contains the tools that the agents can use, such as `gdocs_tools.py`, `gmail_tools.py`, etc.
*   **`utils/`:** Contains utility functions for logging, checkpointing, and other tasks.
*   **`data/`:** Contains the `memory.db` SQLite database for storing the agent's state.

## Key Dependencies

The project relies on a number of open-source libraries, including:

*   **`langchain`:** The core AI framework.
*   **`langgraph`:** For building the agent graph.
*   **`fastapi` (implied by `uvicorn` and `starlette`):** For the server implementation.
*   **`google-api-python-client` and `google-auth-oauthlib`:** For integrating with Google Workspace.
*   **`aiosqlite`:** For the database.
*   **`numpy`, `pandas`, `matplotlib`:** For data analysis and visualization.

## How to Run

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Set up Environment Variables:**
    Create a `.env` file in the root of the project and add the following:
    ```
    OPENROUTER_API_KEY="your-openrouter-api-key"
    GOOGLE_API_KEY="your-google-api-key"
    DEFAULT_THREAD_ID="some-default-thread-id"
    ```
    You will also need to set up Google Cloud credentials for the Google Workspace tools.
3.  **Run the application:**
    ```bash
    python main.py
    ```
This will start the interactive CLI, and you can start chatting with the agent.
