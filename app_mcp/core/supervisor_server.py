import sys
from pathlib import Path

# Add project root to Python path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))


from app_mcp.core.server_init import supervisor_server
import app_mcp.tools.gsearch_tools

if __name__ == "__main__":
    supervisor_server.run()
