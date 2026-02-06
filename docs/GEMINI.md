# Gemini Multi-Server Agentic AI Framework

This document provides a detailed overview of the Gemini agentic AI framework, a sophisticated, multi-server system designed for complex task automation.

## Core Concepts

The framework is built on several key concepts that enable its power and flexibility.

### Multi-Agent Architecture

The system uses a supervisor/worker model. A central **Supervisor Agent** acts as an intelligent orchestrator, analyzing user requests and routing them to a team of specialized agents:

*   **Communication Agent:** Handles email and chat operations.
*   **Planning Agent:** Manages calendar events and tasks.
*   **Content Agent:** Works with files and documents in Google Drive, Docs, Sheets, etc.

### Graph-Based Workflows (`langgraph`)

The entire workflow is modeled as a state machine using the `langgraph` library. This graph, defined in `core/graph.py`, consists of:

*   **Nodes:** Each agent and toolset is a node in the graph.
*   **Edges:** The flow of control between nodes is determined by conditional logic, primarily managed by the supervisor.

This architecture allows for complex, multi-step execution paths and loops.

### State Management

The application's state is managed in a `State` object, a `TypedDict` defined in `core/state.py`. This object is passed between each node in the graph and contains:

*   `messages`: The history of the conversation.
*   `summary`: A running summary of the conversation to manage context length.
*   `last_knowledgegraph_timestamp`: Timestamp of the last knowledge graph update.
*   `next`: The next node to transition to.

The state is persisted using a `checkpointer` with an `aiosqlite` backend, allowing the system to resume workflows.

### Dynamic Code Generation (`CodeExecutionAgent`)

For tasks that are too complex for a single tool or require intricate logic, the supervisor can delegate to the **`CodeExecutionAgent`**. This powerful agent, defined in `core/codeagent.py`, can:

1.  Analyze the user's intent (`_resolve_intent`).
2.  Dynamically generate Python code to accomplish the task.
3.  Execute the code in a local environment, with access to all the system's tools.

This feature is used for batch operations, multi-step deterministic flows, and precise data handling, making the system extremely powerful and efficient.

### Prompt-Driven Logic

The "brains" of the agents are not hard-coded but are defined in system prompts within `config/prompts.py`. These prompts instruct the agents on their roles, capabilities, and how to make decisions. The `SUPERVISOR_SYSTEM_PROMPT` is especially critical, as it contains the logic for routing tasks to the other agents.

### Knowledge Graph

The system builds and maintains a knowledge graph (`rag/knowledge_graph.py`) to create a long-term memory. It extracts entities (people, projects, organizations, etc.) and their relationships from conversations, storing them in a graph database. This allows the agent to recall information from past interactions.

## System Architecture

The framework is composed of several key directories and files.

### `main.py` & `Procfile` (Entry Points)

The application can be started in two ways:

1.  **`python main.py`:** The main script can spawn the agent server processes directly.
2.  **`honcho start -f procfile`:** The `Procfile` defines the agent servers as independent processes, which can be managed by `honcho`. `main.py` is then run in a separate terminal to connect to the running servers.

### `config/` (Configuration)

*   **`settings.py`:** Defines server configurations (ports, hosts), API keys, and other system-wide settings.
*   **`prompts.py`:** Contains the system prompts that define the behavior of each agent. This is the core of the agent's "personality" and decision-making logic.

### `core/` (Orchestration Logic)

*   **`graph.py`:** Builds the `langgraph` `StateGraph`. It initializes all agent nodes and tool nodes and defines the conditional edges that control the flow of execution.
*   **`state.py`:** Defines the `State` `TypedDict` and the routing functions (`route_start`, `internal_agent_route`, `route_after_supervisor`) that are used in the graph's conditional edges.
*   **`agent.py`:** Contains the `agent_node_factory` for creating agent nodes, the `summerizer_node` for condensing conversation history, and the `updation_knowledge_graph` function.
*   **`codeagent.py`:** Contains the implementation of the `CodeExecutionAgent`. It has its own internal workflow for generating and executing code.

### `app_mcp/` (Agent Servers & Tools)

This directory contains the implementation of the agent servers.

*   **`core/`:** Contains the server initialization logic and the individual server scripts (`communication_server.py`, `planning_server.py`, etc.).
*   **`tools/`:** Contains the tools available to the agents, organized by category. These are Python functions that interact with external APIs (Google Workspace, Google Search, etc.).
    *   **Communication:** `gmail_tools.py`, `gchat_tools.py`
    *   **Planning:** `calendar_tools.py`, `gtask_tools.py`
    *   **Content:** `gdocs_tools.py`, `gdrive_tools.py`, `gsheet_tools.py`, `gslide_tools.py`, `gform_tools.py`
    *   **Supervisor:** `gsearch_tools.py`

### `rag/` (Retrieval-Augmented Generation)

*   **`knowledge_graph.py`:** Implements the logic for extracting entities and relationships from text, validating them, and adding them to the knowledge graph.

## Request Execution Flow

A user request is processed as follows:

1.  The user input is added to the `State`.
2.  The graph's entry point (`route_start`) directs the flow to the `supervisor` node.
3.  The **Supervisor Agent** analyzes the `State` (including message history and summary).
4.  Based on its system prompt in `config/prompts.py`, the supervisor decides on the next step:
    *   **Direct Answer:** If it can answer directly, it generates a response and the flow ends.
    *   **Tool Use:** If it needs information, it uses its own tools (e.g., Google Search).
    *   **Agent Routing:** If the task requires a specialized agent, it returns a JSON object like `{"step": "planning_agent"}`, and the graph transitions to that agent's node.
    *   **Code Generation:** For complex tasks, it routes to the `code_agent`.
5.  A **Specialized Agent** (e.g., `planning_agent`) receives the state. It uses its tools to perform the requested action (e.g., creating a calendar event). The results of the tool call are added back to the state.
6.  The flow returns to the specialized agent, which formulates a response or decides on the next tool call. Once its task is complete, it returns "FINAL ANSWER" and the flow returns to the supervisor.
7.  The **Supervisor** receives the result from the specialized agent and decides on the next step, which could be routing to another agent, answering the user, or finishing the task.
8.  If routed to the **`CodeExecutionAgent`**, it generates and executes Python code to perform the task, then returns the result to the supervisor.

## How to Run

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Set up Environment Variables:**
    Create a `.env` file in the root of the project and add your API keys.
3.  **Run the application:**
    *   **Using `honcho` (recommended):**
        ```bash
        honcho start -f procfile
        ```
        In a separate terminal, run the client:
        ```bash
        python main.py
        ```
    *   **Spawning servers from the client:**
        ```bash
        python main.py
        ```
This will start the interactive CLI.