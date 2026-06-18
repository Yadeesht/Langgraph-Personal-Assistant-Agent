import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app_tools.core.server_init import communication_server
import app_tools.tools.gmail_tools
# import app_tools.tools.gchat_tools  # Temporarily disabled due to unavailability of gchat API for personal accounts

if __name__ == "__main__":
    communication_server.run()
