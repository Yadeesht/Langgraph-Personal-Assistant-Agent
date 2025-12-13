from mcp.server.fastmcp import FastMCP

# Communication Server
communication_server = FastMCP(
    name="Communication Server",
    host="0.0.0.0",
    port=8050,
    stateless_http=True,
)

# Planning Server
planning_server = FastMCP(
    name="Planning Server",
    host="0.0.0.0",
    port=8051,
    stateless_http=True,
)

content_server = FastMCP(
    name="Content Server",
    host="0.0.0.0",
    port=8052,
    stateless_http=True,
)

__all__ = ["communication_server", "planning_server", "content_server"]
