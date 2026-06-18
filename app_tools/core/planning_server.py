import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app_tools.core.server_init import planning_server
import app_tools.tools.calendar_tools
import app_tools.tools.gtask_tools

if __name__ == "__main__":
    planning_server.run()
