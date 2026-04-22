"""Entry point: `python -m financing_api` boots uvicorn."""

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "financing_api.app:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("RELOAD", "1") == "1",
    )


if __name__ == "__main__":
    main()
