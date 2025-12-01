# Project Overview

This project is a Gmail Assistant that allows a user to manage their Gmail account through a command-line interface. It is a Python-based tool that uses a client-server architecture to interact with the Gmail API.

The core of the project is a server that exposes a set of tools for managing emails, labels, drafts, and other Gmail features. A client can connect to this server and call these tools to perform actions on the user's Gmail account.

## Key Technologies

*   **Python:** The project is written entirely in Python.
*   **mcp:** This library is used to create the client-server architecture.
*   **Google API Client Library for Python:** This library is used to interact with the Gmail API.
*   **OAuth 2.0:** The project uses OAuth 2.0 for authentication with the Gmail API.

# Building and Running

## Dependencies

The project requires the following Python libraries:

*   `mcp`
*   `nest_asyncio`
*   `google-api-python-client`
*   `google-auth-httplib2`
*   `google-auth-oauthlib`

These can be installed using pip:

```bash
pip install mcp nest_asyncio google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Running the Project

1.  **Enable the Gmail API:** Before running the project, you need to enable the Gmail API in your Google Cloud Platform project and download the `client_secret.json` file.
2.  **Update Credentials Path:** The path to the `client_secret.json` file is hardcoded in `MCP/server.py` and `MCP/service/gmail_service.py`. You will need to update these paths to point to the correct location of your `client_secret.json` file. after the update you have test run the test-client to get the gmail_token.json just once after it can be reused(***important***)
3.  **Run the server:**
    ```bash
    python MCP/server.py
    ```
4.  **Run the client:**
    ```bash
    python MCP/client-std.py
    ```

# Development Conventions

*   The project uses asynchronous programming with `asyncio`.
*   The `GmailService` class in `MCP/service/gmail_service.py` encapsulates all interactions with the Gmail API.
*   The server in `MCP/server.py` defines the tools that can be called by the client. Each tool is a Python function decorated with `@mcp.tool()`.
*   The client in `MCP/client-std.py` demonstrates how to connect to the server and call the available tools.
