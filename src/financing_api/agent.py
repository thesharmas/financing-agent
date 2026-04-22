"""Managed Agent session wrapper.

Adapted from the deleted financing_proxy.agent. Same contract: given a
PDF and a prompt, create an Anthropic Managed Agent session, stream
back text + tool_use + done events.

Callers get a synchronous generator of dicts. The API layer adapts this
to Server-Sent Events.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field

from anthropic import Anthropic

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


@dataclass
class AnalysisResult:
    full_text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    mcp_tool_inputs: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


def analyze_pdf_stream(
    *,
    agent_id: str,
    environment_id: str,
    vault_id: str,
    pdf_base64: str,
    message: str,
    title: str = "offer.pdf",
) -> Generator[dict, None, None]:
    """Create a session, send the PDF, yield event dicts.

    Event shapes:
        {"type": "text", "content": str}
        {"type": "tool_use", "name": str, "input": dict}
        {"type": "done", "input_tokens": int, "output_tokens": int}
        {"type": "error", "content": str}
    """
    client = _get_client()

    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=environment_id,
        vault_ids=[vault_id],
        title="Financing analysis",
    )

    input_tokens = 0
    output_tokens = 0

    with client.beta.sessions.events.stream(session.id) as stream:
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
                    tool_input = event.input if hasattr(event, "input") else {}
                    yield {
                        "type": "tool_use",
                        "name": event.name,
                        "input": tool_input,
                    }
                case "agent.tool_use":
                    yield {"type": "tool_use", "name": event.name, "input": {}}
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


DEFAULT_PROMPT = (
    "Analyze this financing offer. Extract all key fields (advance amount, "
    "total repayment, term, factor rate or APR, payment frequency, any fees), "
    "detect predatory flags, and give a plain-English recommendation for "
    "whether the small-business owner should accept."
)
