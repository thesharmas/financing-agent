"""Simple API key authentication middleware for the MCP server.

Checks for a valid API key in the X-API-Key header or Authorization header.
The expected key is read from the MCP_API_KEY environment variable.

If MCP_API_KEY is not set, auth is disabled (all requests allowed).
This lets you run locally without auth and deploy with auth.
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates API key on incoming requests."""

    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        self.api_key = api_key or os.environ.get("MCP_API_KEY")

    async def dispatch(self, request: Request, call_next):
        # Skip auth if no key is configured
        if not self.api_key:
            return await call_next(request)

        # Skip health check endpoint
        if request.url.path == "/health":
            return await call_next(request)

        # Check X-API-Key header
        provided_key = request.headers.get("x-api-key")

        # Fall back to Authorization: Bearer <key>
        if not provided_key:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                provided_key = auth_header[7:]

        if provided_key != self.api_key:
            return JSONResponse(
                {"error": "Invalid or missing API key"},
                status_code=401,
            )

        return await call_next(request)
