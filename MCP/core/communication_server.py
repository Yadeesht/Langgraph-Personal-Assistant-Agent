import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from MCP.core.server_init import communication_server
import MCP.tools.gmail_tools
import MCP.tools.gchat_tools

if __name__ == "__main__":
    communication_server.run()
