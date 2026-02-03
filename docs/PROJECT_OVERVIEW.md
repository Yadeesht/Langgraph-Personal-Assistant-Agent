# Multi-Server Agentic AI Framework

This project is a sophisticated, multi-server agentic AI framework built with Python. It features a modular, graph-based architecture orchestrated by a central supervisor agent. The framework is designed to handle complex tasks by delegating them to specialized agents, each running as a separate server process. The system is highly flexible, with agent behaviors and routing logic defined in external prompt files.

## Key Features

*   **Multi-Agent Architecture:** A supervisor agent coordinates a team of specialized agents for communication, planning, and content management.
*   **Graph-Based Workflows:** Uses `langgraph` to define a state machine that controls the flow of execution between agents and tools.
*   **Dynamic Code Generation:** A powerful `CodeExecutionAgent` dynamically generates and executes Python code to handle complex, multi-tool workflows that are not possible with the standard toolset.
*   **Tool-Based Agents:** Each agent is equipped with a set of tools to perform its tasks, including integrations with Google Workspace (Gmail, Calendar, Drive, etc.) and Google Search.
*   **Persistent State:** Uses an `aiosqlite` database to checkpoint the agent's state, allowing it to resume conversations and workflows.
*   **Interactive CLI:** Provides an interactive command-line interface for users to chat with the agent.
*   **Flexible Deployment:** Can be run with a process manager like `honcho` using the provided `procfile`, or the main application can spawn the server processes directly.
*   **Extensive Logging:** Comprehensive logging for debugging and monitoring agent behavior.

## Architecture

The framework is built around a central **Supervisor Agent** that acts as an orchestrator. The supervisor's logic is defined in `config/prompts.py` and it can:

1.  Answer general questions directly.
2.  Use a Google Search tool to find information.
3.  Route tasks to one of three specialized agents:
    *   **Communication Agent:** Handles email and chat operations (Gmail, Google Chat).
    *   **Planning Agent:** Manages calendar and tasks (Google Calendar, Google Tasks).
    *   **Content Agent:** Manages files and documents (Google Drive, Docs, Sheets, Slides, Forms).
4.  Delegate complex tasks to the **CodeExecutionAgent**, which can write and execute Python code to accomplish the task.

Each of these agents runs as a separate server process using `MCP` (Multi-Server Agent Framework). The servers communicate with the main client application.

The agent's logic is defined as a graph using `langgraph` in `core/graph.py`. This allows for flexible and powerful workflows, including multi-step chains of tool and agent calls. The project generates a visual representation of this graph in `agent_structure_graph.png`.

## Core Components

*   **`main.py`:** The main entry point of the application. It initializes the clients for the agent servers, builds the agent graph, and starts the interactive CLI. It can also spawn the server processes directly.
*   **`procfile`:** Defines the agent servers as independent processes for use with a process manager like `honcho`.
*   **`config/`:** Contains configuration files for the agent.
    *   **`settings.py`:** Defines server configurations, API keys, and other settings.
    *   **`prompts.py`:** Contains the system prompts for the supervisor and specialized agents, defining their roles and behavior. This is where the core routing logic is defined.
*   **`core/`:** Contains the core logic for the agents and the graph.
    *   **`graph.py`:** Defines the `langgraph` state machine that orchestrates the agents and tools.
    *   **`agent.py`:** A factory for creating agent nodes in the graph.
    *   **`codeagent.py`:** The `CodeExecutionAgent` that generates and executes Python code.
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
*   **`honcho`:** For managing the multi-server processes.
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
    You can run the application in two ways:

    **a) Using `honcho` (recommended for stability):**
    ```bash
    honcho start -f procfile
    ```
    In a separate terminal, run the client:
    ```bash
    python main.py
    ```

    **b) Spawning servers from the client:**
    The `main.py` script can also spawn the server processes directly if they are not already running.
    ```bash
    python main.py
    ```
This will start the interactive CLI, and you can start chatting with the agent.