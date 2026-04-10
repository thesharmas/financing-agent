"""Entry point for running the MCP server as a module.

Usage:
    python -m financing_mcp                           # stdio (local)
    python -m financing_mcp --transport sse --port 8000  # SSE (remote)
"""

from financing_mcp.server import mcp

mcp.run()
