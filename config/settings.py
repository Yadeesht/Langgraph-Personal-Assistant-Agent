import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# -----------------------------------------------------------------------------
# Data and persistence paths
# -----------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"
MEMORY_DB = DATA_DIR / "memory.db"
VECTOR_DB = DATA_DIR / "embeddings"
KNOWLEDGE_GRAPH_DB = DATA_DIR / "knowledge_graph_db" / "knowledge_graph.db"
EPISODIC_RAG_DB = DATA_DIR / "episodic_rag_db"

# -----------------------------------------------------------------------------
# MCP server entrypoints
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
COMMUNICATION_SERVER = BASE_DIR / "app_tools" / "core" / "communication_server.py"
PLANNING_SERVER = BASE_DIR / "app_tools" / "core" / "planning_server.py"
CONTENT_SERVER = BASE_DIR / "app_tools" / "core" / "content_server.py"
SUPERVISOR_SERVER = BASE_DIR / "app_tools" / "core" / "supervisor_server.py"

# -----------------------------------------------------------------------------
# API keys and provider endpoints
# -----------------------------------------------------------------------------
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AZURE_AI_CREDENTIAL = os.getenv("AZURE_AI_CREDENTIAL")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# -----------------------------------------------------------------------------
# Default model and request settings
# -----------------------------------------------------------------------------
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# -----------------------------------------------------------------------------
# Embedding model paths
# -----------------------------------------------------------------------------
EMBEDDING_BGE_MODEL_PATH = BASE_DIR / "models" / "bge-small"
EMBEDDING_GTE_MODEL_PATH = BASE_DIR / "models" / "gte-base"

# -----------------------------------------------------------------------------
# Token and conversation defaults
# -----------------------------------------------------------------------------
MAX_TOKENS = 2000
TOKEN_STRATEGY = "last"

# Default thread for terminal-based sessions
DEFAULT_THREAD_ID = os.getenv("DEFAULT_THREAD_ID", "default_thread")


# -----------------------------------------------------------------------------
# MCP client transport configs
# -----------------------------------------------------------------------------
communication_config = {
    "communication": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(COMMUNICATION_SERVER)],
    }
}

planning_config = {
    "planning": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(PLANNING_SERVER)],
    }
}

content_config = {
    "content": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(CONTENT_SERVER)],
    }
}

supervisor_config = {
    "supervisor": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(SUPERVISOR_SERVER)],
    }
}

# Global transport override: stdio | socket | http
TRANSPORT_MODE = os.getenv("TRANSPORT_MODE", "stdio")
