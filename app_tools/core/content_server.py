import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app_tools.core.server_init import content_server
import app_tools.tools.gdrive_tools
import app_tools.tools.gslide_tools
import app_tools.tools.gsheet_tools
import app_tools.tools.gform_tools
import app_tools.tools.gdocs_tools

if __name__ == "__main__":
    content_server.run()
