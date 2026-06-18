import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app_tools.core.server_init import supervisor_server
import app_tools.tools.gsearch_tools
import app_tools.tools.rag_tools

if __name__ == "__main__":
    supervisor_server.run()
