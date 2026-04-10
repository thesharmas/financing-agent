"""CLI for the Financing Agent SDK.

Usage:
    financing-agent register --name "..." --email "..." --company "..."
    financing-agent configure --api-key fin_...
    financing-agent analyze offer.pdf
    financing-agent analyze --text "MCA at 1.35 factor rate..."
    financing-agent usage
"""

import argparse
import json
import os
import sys

CONFIG_DIR = os.path.expanduser("~/.financing-agent")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def _load_api_key() -> str | None:
    """Load API key from env var or config file."""
    key = os.environ.get("FINANCING_API_KEY")
    if key:
        return key
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f).get("api_key")
    return None


def _save_config(api_key: str) -> None:
    """Save API key to config file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"api_key": api_key}, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


def cmd_register(args):
    """Register for an API key."""
    from financing_sdk.client import FinancingAgent

    api_key = FinancingAgent.register(
        name=args.name,
        email=args.email,
        company=args.company,
    )
    print(f"\nYour API key: {api_key}")
    print("\nSave this key — it will not be shown again.")
    print(f"\nTo configure: financing-agent configure --api-key {api_key}")


def cmd_configure(args):
    """Save API key to config."""
    _save_config(args.api_key)
    print(f"API key saved to {CONFIG_PATH}")


def cmd_analyze(args):
    """Analyze a financing offer."""
    from financing_sdk.client import FinancingAgent

    api_key = args.api_key or _load_api_key()
    if not api_key:
        print("ERROR: No API key. Set FINANCING_API_KEY or run: financing-agent configure")
        sys.exit(1)

    agent = FinancingAgent(api_key=api_key)

    if args.text:
        result = agent.analyze_text(args.text)
        print(result.analysis)
    elif args.pdf:
        if not os.path.exists(args.pdf):
            print(f"ERROR: File not found: {args.pdf}")
            sys.exit(1)
        if args.stream:
            for chunk in agent.analyze_pdf_stream(args.pdf, args.message):
                print(chunk, end="", flush=True)
            print()
        else:
            result = agent.analyze_pdf(args.pdf, args.message)
            print(result.analysis)
    else:
        print("ERROR: Provide a PDF path or --text")
        sys.exit(1)


def cmd_usage(args):
    """Show usage stats."""
    from financing_sdk.client import FinancingAgent

    api_key = args.api_key or _load_api_key()
    if not api_key:
        print("ERROR: No API key. Set FINANCING_API_KEY or run: financing-agent configure")
        sys.exit(1)

    agent = FinancingAgent(api_key=api_key)
    usage = agent.get_usage()
    print(f"Name:        {usage.name}")
    print(f"Company:     {usage.company}")
    print(f"Registered:  {usage.created_at}")
    print(f"Total calls: {usage.total_calls}")
    print(f"Last used:   {usage.last_called_at or 'never'}")


def main():
    parser = argparse.ArgumentParser(
        prog="financing-agent",
        description="Analyze SMB financing offers",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    reg = subparsers.add_parser("register", help="Get an API key")
    reg.add_argument("--name", required=True)
    reg.add_argument("--email", required=True)
    reg.add_argument("--company", required=True)
    reg.set_defaults(func=cmd_register)

    # configure
    conf = subparsers.add_parser("configure", help="Save API key locally")
    conf.add_argument("--api-key", required=True)
    conf.set_defaults(func=cmd_configure)

    # analyze
    ana = subparsers.add_parser("analyze", help="Analyze a financing offer")
    ana.add_argument("pdf", nargs="?", help="Path to PDF")
    ana.add_argument("--text", "-t", help="Describe offer terms as text")
    ana.add_argument("--message", "-m",
        default="Analyze this financing offer. Extract all key terms, calculate the effective APR, check for predatory terms, and compare to market benchmarks.",
        help="Custom analysis prompt")
    ana.add_argument("--stream", "-s", action="store_true", help="Stream output")
    ana.add_argument("--api-key", help="API key (overrides saved key)")
    ana.set_defaults(func=cmd_analyze)

    # usage
    usg = subparsers.add_parser("usage", help="Show usage stats")
    usg.add_argument("--api-key", help="API key (overrides saved key)")
    usg.set_defaults(func=cmd_usage)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
