"""Entry point for running the CLI.

Usage:
    python -m financing_agent offer.pdf
    python -m financing_agent --text "I got an MCA offer..."
    python -m financing_agent.setup   # one-time setup
"""

from financing_agent.cli import main

main()
