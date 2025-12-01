import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "memory.db"
MCP_SERVER_PATH = BASE_DIR / "MCP" / "server.py"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_MODEL = "openai/gpt-oss-20b:free"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

MAX_TOKENS = 2000
TOKEN_STRATEGY = "last"

DEFAULT_THREAD_ID = "gmail_thread_002"
