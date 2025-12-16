import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from MCP.core.server_init import content_server
import MCP.tools.gdrive_tools

if __name__ == "__main__":
    content_server.run()
