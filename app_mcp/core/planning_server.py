import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from app_mcp.core.server_init import planning_server
import app_mcp.tools.calendar_tools
import app_mcp.tools.gtask_tools

if __name__ == "__main__":
    planning_server.run()
