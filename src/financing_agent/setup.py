"""One-time setup for the Managed Agent.

Creates three resources on the Anthropic API:
1. Agent — model, system prompt, MCP server, tools
2. Environment — cloud container with networking for MCP
3. Vault + credential — API key for authenticating to the MCP server

Run once:
    python -m financing_agent.setup

Outputs the IDs to a config file for the CLI to reference.
"""

import json
import os
import sys

from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MCP_SERVER_URL = "https://financing-mcp-259728300238.us-central1.run.app/mcp"
MCP_API_KEY = os.environ.get("MCP_API_KEY")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

SYSTEM_PROMPT = """\
You are a financing analyst that helps small business owners understand \
their financing offers. Users will upload PDF documents of financing \
contracts (MCA, receivables purchase, PO financing, term loans).

YOUR WORKFLOW:
1. Read the uploaded document carefully
2. Extract all key financial terms (advance amount, factor rate or \
stated cost, repayment type, term, payment frequency, holdback \
percentage, fees, late fees, confession of judgment, etc.)
3. Call analyze_offer with the extracted terms to get precise calculations
4. Call detect_predatory_terms with the results to check for red flags
5. Call get_market_benchmarks to contextualize the offer
6. Explain everything to the user in plain English

NON-NEGOTIABLES:
- NEVER do financial math yourself. Always use the MCP tools.
- NEVER present a factor rate without also showing the APR.
- ALWAYS explain jargon immediately when you use it.
- ALWAYS flag predatory terms explicitly — do not soften bad news.
- ALWAYS show tradeoffs, not just a verdict.
- If you can't extract a field, tell the user what's missing and why \
it matters.

PRODUCT TYPES YOU HANDLE:
- MCA (Merchant Cash Advance): factor rate, daily/weekly ACH or \
holdback percentage of sales
- Receivables Purchase: sale of future receivables, discount amount, \
specified percentage
- PO Financing: advance against purchase orders, lump sum repayment \
from a named buyer
- Term Loan: fixed interest/fee, scheduled payments over a defined term

IDENTIFYING PRODUCT TYPE — look for these signals:
- "factor rate" or "purchase of receivables" → MCA
- "discount amount" or "specified percentage" or "receivables sale" \
→ Receivables Purchase
- "purchase order" or "PO advance" or "PO financing fee" → PO Financing
- "loan amount" or "interest rate" or "APR" or "loan fee" → Term Loan

EXTRACTING TERMS — map contract language to tool parameters:
- "Purchase Price" / "Advance Amount" / "Funded Amount" / "Loan Amount" \
→ advance_amount
- "Factor Rate" → factor_rate
- "Total Repayment" / "Total Amount Due" / "Loan Balance" → total_repayment
- "Discount Amount" / "PO Financing Fee" / "Loan Fee" / "Total Interest" \
→ stated_cost
- "Origination Fee" / "Processing Fee" → origination_fee
- "Specified Percentage" / "Holdback" / "Repayment Rate" → holdback_pct \
(convert to decimal: 15% → 0.15)
- "Expected Daily Revenue" × 21 → estimated_monthly_revenue
- "Minimum Payment" / "60-day milestone" → minimum_payment
- "Confession of Judgment" → has_confession_of_judgment (true/false)
- Check if fee is "deducted at time of disbursement" → fee_deducted_from_advance

RESPONSE FORMAT:
Start with a one-line summary ("This is a [product type] with an \
effective APR of X%"), then break down the details, then flag any \
concerns, then give your assessment with tradeoffs.
"""


def setup():
    """Create agent, environment, and vault. Save IDs to config file."""
    if not MCP_API_KEY:
        print("ERROR: MCP_API_KEY environment variable not set")
        print("Set it to the API key configured on your MCP server")
        sys.exit(1)

    client = Anthropic()

    # Check if config already exists
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            existing = json.load(f)
        print(f"Config already exists at {CONFIG_PATH}")
        print(f"  Agent ID: {existing.get('agent_id')}")
        print(f"  Environment ID: {existing.get('environment_id')}")
        print(f"  Vault ID: {existing.get('vault_id')}")
        print()
        response = input("Recreate? (y/N): ").strip().lower()
        if response != "y":
            print("Keeping existing config")
            return

    print("Creating Managed Agent resources...\n")

    # 1. Create agent
    print("1. Creating agent...")
    agent = client.beta.agents.create(
        name="Financing Analyzer",
        model="claude-sonnet-4-6",
        system=SYSTEM_PROMPT,
        mcp_servers=[
            {
                "type": "url",
                "name": "financing",
                "url": MCP_SERVER_URL,
            },
        ],
        tools=[
            {"type": "agent_toolset_20260401"},
            {"type": "mcp_toolset", "mcp_server_name": "financing"},
        ],
    )
    print(f"   Agent ID: {agent.id} (version {agent.version})")

    # 2. Create environment
    print("2. Creating environment...")
    environment = client.beta.environments.create(
        name="financing-analyzer-env",
        config={
            "type": "cloud",
            "networking": {
                "type": "limited",
                "allow_mcp_servers": True,
            },
        },
    )
    print(f"   Environment ID: {environment.id}")

    # 3. Create vault with MCP API key
    print("3. Creating vault...")
    vault = client.beta.vaults.create(
        display_name="Financing MCP Server",
        metadata={"service": "financing-mcp"},
    )
    print(f"   Vault ID: {vault.id}")

    # 4. Add credential to vault
    print("4. Adding MCP API key credential...")
    credential = client.beta.vaults.credentials.create(
        vault_id=vault.id,
        display_name="Financing MCP API Key",
        auth={
            "type": "static_bearer",
            "mcp_server_url": MCP_SERVER_URL,
            "token": MCP_API_KEY,
        },
    )
    print(f"   Credential ID: {credential.id}")

    # Save config
    config = {
        "agent_id": agent.id,
        "agent_version": agent.version,
        "environment_id": environment.id,
        "vault_id": vault.id,
        "credential_id": credential.id,
        "mcp_server_url": MCP_SERVER_URL,
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nConfig saved to {CONFIG_PATH}")
    print("\nSetup complete! Run the CLI with:")
    print("  python -m financing_agent.cli offer.pdf")


if __name__ == "__main__":
    setup()
