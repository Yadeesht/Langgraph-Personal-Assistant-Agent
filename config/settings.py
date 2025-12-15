import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "memory.db"
COMMUNICATION_SERVER = BASE_DIR / "MCP" / "core" / "communication_server.py"
PLANNING_SERVER = BASE_DIR / "MCP" / "core" / "planning_server.py"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_MODEL = "openai/gpt-oss-20b:free"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

MAX_TOKENS = 2000
TOKEN_STRATEGY = "last"

DEFAULT_THREAD_ID = "gmail_thread_116"

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
