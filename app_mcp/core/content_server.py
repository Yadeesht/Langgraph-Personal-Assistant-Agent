import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from app_mcp.core.server_init import content_server
import app_mcp.tools.gdrive_tools
import app_mcp.tools.gslide_tools
import app_mcp.tools.gsheet_tools
import app_mcp.tools.gform_tools
import app_mcp.tools.gdocs_tools

if __name__ == "__main__":
    content_server.run()
