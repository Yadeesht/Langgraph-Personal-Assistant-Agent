import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from mcp
.core.server_init import planning_server
import mcp
.tools.calendar_tools
import mcp
.tools.gtask_tools

if __name__ == "__main__":
    planning_server.run()
