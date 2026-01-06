import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from MCP.core.server_init import communication_server
import MCP.tools.gmail_tools
# import MCP.tools.gchat_tools              # Temporarily disabled due to unavailability of gchat API for personal accounts

if __name__ == "__main__":
    communication_server.run()
