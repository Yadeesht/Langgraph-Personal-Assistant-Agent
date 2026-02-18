import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"
MEMORY_DB = DATA_DIR / "memory.db"
VECTOR_DB = DATA_DIR / "embeddings"
KNOWLEDGE_GRAPH_DB = DATA_DIR / "knowledge_graph_db" / "knowledge_graph.db"
EPISODIC_RAG_DB = DATA_DIR / "episodic_rag_db"


BASE_DIR = Path(__file__).parent.parent
COMMUNICATION_SERVER = BASE_DIR / "app_mcp" / "core" / "communication_server.py"
PLANNING_SERVER = BASE_DIR / "app_mcp" / "core" / "planning_server.py"
CONTENT_SERVER = BASE_DIR / "app_mcp" / "core" / "content_server.py"
SUPERVISOR_SERVER = BASE_DIR / "app_mcp" / "core" / "supervisor_server.py"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_OPEN_MODEL = "openai/gpt-oss-20b:free"
DEFAULT_OPEN_CODE_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

EMBEDDING_BGE_MODEL_PATH = "D:/Agentic AI/models/bge-small"
EMBEDDING_GTE_MODEL_PATH = "D:/Agentic AI/models/gte-base"

MAX_TOKENS = 2000
TOKEN_STRATEGY = "last"

DEFAULT_THREAD_ID = os.getenv("DEFAULT_THREAD_ID", "default_thread")

WAKE_WORD = "hey_jarvis"
WW_THRESHOLD = 0.7
SILENCE_THRESHOLD = 0.03
VOICE_INPUT_STATUS = False
VOICE_OUTPUT_STATUS = False

communication_config = {
    "communication": {
        "transport": "stdio",
        "command": "python",
        "args": [str(COMMUNICATION_SERVER)],
    }
}

planning_config = {
    "planning": {
        "transport": "stdio",
        "command": "python",
        "args": [str(PLANNING_SERVER)],
    }
}

content_config = {
    "content": {
        "transport": "stdio",
        "command": "python",
        "args": [str(CONTENT_SERVER)],
    }
}
supervisor_config = {
    "supervisor": {
        "transport": "stdio",
        "command": "python",
        "args": [str(SUPERVISOR_SERVER)],
    }
}

TRANSPORT_MODE = os.getenv("TRANSPORT_MODE", "stdio")  # Options: stdio, socket, http
