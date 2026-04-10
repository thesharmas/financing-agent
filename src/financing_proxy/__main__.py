"""Entry point for the proxy server.

Usage:
    python -m financing_proxy                    # default port 8080
    python -m financing_proxy --port 9000        # custom port
"""

import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Financing Proxy Server")
    parser.add_argument(
        "--port", type=int, default=None,
        help="Port (default: PORT env var or 8080)",
    )
    args = parser.parse_args()

    port = args.port or int(os.environ.get("PORT", 8080))
    print(f"Starting proxy on port {port}")
    uvicorn.run("financing_proxy.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
