"""Managed Agent session wrapper.

Creates sessions, sends PDFs, and streams responses from the
Managed Agent. The proxy calls this — clients never talk to
Anthropic directly.
"""

import base64
from collections.abc import Generator
from dataclasses import dataclass, field

from anthropic import Anthropic

from financing_proxy.config import get_agent_id, get_environment_id, get_vault_id

_client = None


def _get_client() -> Anthropic:
    """Lazy-initialize Anthropic client."""
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


@dataclass
class AnalysisResult:
    """Structured result from a financing analysis."""

    full_text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


def analyze_pdf_stream(
    pdf_base64: str, message: str, title: str = "offer.pdf"
) -> Generator[dict, None, None]:
    """Create a session, send PDF, yield streaming events.

    Yields dicts with:
      {"type": "text", "content": "..."}
      {"type": "tool_use", "name": "analyze_offer"}
      {"type": "done", "input_tokens": N, "output_tokens": N}
    """
    client = _get_client()

    # Create session
    session = client.beta.sessions.create(
        agent=get_agent_id(),
        environment_id=get_environment_id(),
        vault_ids=[get_vault_id()],
        title="Financing analysis",
    )

    input_tokens = 0
    output_tokens = 0

    with client.beta.sessions.events.stream(session.id) as stream:
        # Send PDF + message
        client.beta.sessions.events.send(
            session.id,
            events=[{
                "type": "user.message",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64,
                        },
                        "title": title,
                    },
                    {"type": "text", "text": message},
                ],
            }],
        )

        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        if hasattr(block, "text"):
                            yield {"type": "text", "content": block.text}
                case "agent.mcp_tool_use":
                    yield {"type": "tool_use", "name": event.name}
                case "agent.tool_use":
                    yield {"type": "tool_use", "name": event.name}
                case "span.model_request_end":
                    if hasattr(event, "model_usage") and event.model_usage:
                        input_tokens += getattr(event.model_usage, "input_tokens", 0)
                        output_tokens += getattr(event.model_usage, "output_tokens", 0)
                case "session.status_idle":
                    yield {
                        "type": "done",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    }
                    break
                case "session.error":
                    yield {"type": "error", "content": str(event.error)}
                case "session.status_terminated":
                    yield {"type": "error", "content": "Session terminated"}
                    break


def analyze_pdf_sync(
    pdf_base64: str, message: str, title: str = "offer.pdf"
) -> AnalysisResult:
    """Run a full analysis and return the complete result."""
    result = AnalysisResult()

    for event in analyze_pdf_stream(pdf_base64, message, title):
        match event["type"]:
            case "text":
                result.full_text += event["content"]
            case "tool_use":
                result.tool_calls.append({"name": event["name"]})
            case "done":
                result.input_tokens = event["input_tokens"]
                result.output_tokens = event["output_tokens"]
            case "error":
                result.full_text += f"\n[Error: {event['content']}]"

    return result
