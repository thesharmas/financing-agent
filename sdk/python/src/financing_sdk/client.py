"""Financing Agent SDK client.

Thin HTTP client that talks to the Financing Proxy API.
Handles PDF encoding, streaming, and response parsing.
"""

import base64
import json
import os
from collections.abc import Generator

import httpx

from financing_sdk.types import AnalysisResult, UsageInfo

DEFAULT_BASE_URL = "https://financing-proxy-259728300238.us-central1.run.app"
DEFAULT_MESSAGE = (
    "Analyze this financing offer. Extract all key terms, calculate the "
    "effective APR, check for predatory terms, and compare to market "
    "benchmarks. Explain everything in plain English."
)


class FinancingAgent:
    """Client for the Financing Agent API.

    Args:
        api_key: Your API key (fin_...). Falls back to FINANCING_API_KEY env var.
        base_url: Proxy URL. Override for self-hosted deployments.
        timeout: Request timeout in seconds. Analysis can take 30-60s.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ):
        self.api_key = api_key or os.environ.get("FINANCING_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Pass api_key= or set FINANCING_API_KEY env var.\n"
                "Get a key: financing-agent register --name '...' --email '...' --company '...'"
            )
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def _read_pdf(self, pdf_path: str) -> str:
        """Read and base64-encode a PDF file."""
        with open(pdf_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def analyze_pdf(
        self, pdf_path: str, message: str = DEFAULT_MESSAGE
    ) -> AnalysisResult:
        """Analyze a PDF financing offer. Returns the full result.

        Args:
            pdf_path: Path to the PDF file.
            message: Custom analysis prompt.
        """
        pdf_data = self._read_pdf(pdf_path)
        title = os.path.basename(pdf_path)

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/analyze/sync",
                headers=self._headers(),
                json={"pdf": pdf_data, "message": message, "title": title},
            )
            resp.raise_for_status()
            data = resp.json()

        return AnalysisResult(
            analysis=data["analysis"],
            tool_calls=[t["name"] for t in data.get("tool_calls", [])],
        )

    def analyze_pdf_stream(
        self, pdf_path: str, message: str = DEFAULT_MESSAGE
    ) -> Generator[str, None, None]:
        """Analyze a PDF and stream the response text.

        Yields text chunks as they arrive.

        Args:
            pdf_path: Path to the PDF file.
            message: Custom analysis prompt.
        """
        pdf_data = self._read_pdf(pdf_path)
        title = os.path.basename(pdf_path)

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/v1/analyze",
                headers=self._headers(),
                json={"pdf": pdf_data, "message": message, "title": title},
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    if event["type"] == "text":
                        yield event["content"]
                    elif event["type"] == "done":
                        break
                    elif event["type"] == "error":
                        raise RuntimeError(f"Analysis error: {event['content']}")

    def analyze_text(
        self, text: str, message: str | None = None
    ) -> AnalysisResult:
        """Analyze a financing offer described in text (no PDF).

        Args:
            text: Description of the offer terms.
            message: Optional custom prompt. If not provided, the text is used directly.
        """
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/analyze/sync",
                headers=self._headers(),
                json={
                    "pdf": "",
                    "message": message or text,
                    "title": "text-input",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return AnalysisResult(
            analysis=data["analysis"],
            tool_calls=[t["name"] for t in data.get("tool_calls", [])],
        )

    def get_usage(self) -> UsageInfo:
        """Get your usage statistics."""
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(
                f"{self.base_url}/v1/usage",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        return UsageInfo(
            name=data["name"],
            company=data["company"],
            created_at=data["created_at"],
            total_calls=data["total_calls"],
            last_called_at=data.get("last_called_at"),
        )

    @staticmethod
    def register(
        name: str,
        email: str,
        company: str,
        base_url: str | None = None,
    ) -> str:
        """Register for an API key. Returns the key (shown once).

        Args:
            name: Your name.
            email: Your email.
            company: Your company name.
            base_url: Proxy URL override.
        """
        url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{url}/v1/register",
                json={"name": name, "email": email, "company": company},
            )
            resp.raise_for_status()
            return resp.json()["api_key"]
