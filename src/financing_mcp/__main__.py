"""Entry point for running the MCP server.

Local development (stdio, no auth):
    python -m financing_mcp

Remote deployment (HTTP with API key auth):
    MCP_API_KEY=your-secret-key python -m financing_mcp --transport streamable-http --port 8080

Cloud Run sets PORT env var automatically:
    MCP_API_KEY=your-secret-key python -m financing_mcp --transport streamable-http
"""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="Financing MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP transport (default: PORT env var or 8080)",
    )
    args = parser.parse_args()

    from financing_mcp.server import mcp

    if args.transport == "stdio":
        # Local mode — no auth needed
        mcp.run(transport="stdio")
    else:
        # Remote mode — add API key auth middleware
        port = args.port or int(os.environ.get("PORT", 8080))

        app = mcp.streamable_http_app()

        # Add auth middleware if MCP_API_KEY is set
        api_key = os.environ.get("MCP_API_KEY")
        if api_key:
            from financing_mcp.auth import APIKeyMiddleware
            app.add_middleware(APIKeyMiddleware, api_key=api_key)
            print(f"Auth enabled — API key required")
        else:
            print("WARNING: No MCP_API_KEY set — server is unauthenticated")

        import uvicorn
        print(f"Starting MCP server on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
