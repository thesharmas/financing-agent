"""CLI for the Financing Analyzer Managed Agent.

Reads a PDF, sends it to the Managed Agent, and streams the response.

Usage:
    python -m financing_agent.cli offer.pdf
    python -m financing_agent.cli offer.pdf --message "Is this predatory?"
    python -m financing_agent.cli --text "I got an MCA with factor rate 1.35..."
"""

import argparse
import base64
import json
import os
import sys

from anthropic import Anthropic


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    """Load agent/environment/vault IDs from config file."""
    if not os.path.exists(CONFIG_PATH):
        print("ERROR: Config not found. Run setup first:")
        print("  python -m financing_agent.setup")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        return json.load(f)


def read_pdf_as_base64(pdf_path: str) -> str:
    """Read a PDF file and return base64-encoded content."""
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def build_message_content(pdf_path: str | None, text_message: str) -> list[dict]:
    """Build the content array for the user message."""
    content = []

    if pdf_path:
        pdf_data = read_pdf_as_base64(pdf_path)
        filename = os.path.basename(pdf_path)
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_data,
            },
            "title": filename,
        })

    content.append({
        "type": "text",
        "text": text_message,
    })

    return content


def run_session(config: dict, content: list[dict]):
    """Create a session, send the message, and stream the response."""
    client = Anthropic()

    # Create a new session
    session = client.beta.sessions.create(
        agent=config["agent_id"],
        environment_id=config["environment_id"],
        vault_ids=[config["vault_id"]],
        title="Financing analysis",
    )
    print(f"Session: {session.id}\n")

    # Open stream and send message
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{
                "type": "user.message",
                "content": content,
            }],
        )

        # Process events
        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        if hasattr(block, "text"):
                            print(block.text, end="", flush=True)
                case "agent.tool_use":
                    print(f"\n  [Tool: {event.name}]", flush=True)
                case "agent.mcp_tool_use":
                    print(f"\n  [MCP: {event.name}]", flush=True)
                case "agent.mcp_tool_result":
                    pass  # Results are used by the agent, not printed
                case "session.status_idle":
                    print("\n")
                    break
                case "session.error":
                    print(f"\n  [Error: {event.error}]", flush=True)
                case "session.status_terminated":
                    print("\n  [Session terminated]", flush=True)
                    break


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a financing offer using the Managed Agent"
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        help="Path to the financing offer PDF",
    )
    parser.add_argument(
        "--message", "-m",
        default="Analyze this financing offer. Extract all key terms, calculate the effective APR, check for predatory terms, and compare to market benchmarks. Explain everything in plain English.",
        help="Custom message to send with the PDF",
    )
    parser.add_argument(
        "--text", "-t",
        help="Send a text message instead of a PDF (e.g., describe offer terms)",
    )
    args = parser.parse_args()

    if not args.pdf and not args.text:
        parser.error("Provide either a PDF path or --text with offer details")

    config = load_config()

    if args.text:
        content = build_message_content(None, args.text)
    else:
        if not os.path.exists(args.pdf):
            print(f"ERROR: File not found: {args.pdf}")
            sys.exit(1)
        content = build_message_content(args.pdf, args.message)

    run_session(config, content)


if __name__ == "__main__":
    main()
