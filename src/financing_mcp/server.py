"""SMB Financing Analysis MCP Server.

Exposes financial calculation and predatory detection tools via MCP protocol.
The Managed Agent (or Claude Desktop) calls these tools to get precise math
instead of doing LLM arithmetic.

Run locally (stdio):
    python -m financing_mcp.server

Run remotely (SSE for Managed Agent):
    python -m financing_mcp.server --transport sse --port 8000
"""

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from financing_mcp.benchmarks import classify_offer, get_benchmarks
from financing_mcp.calculations import (
    CostEscalation,
    FinancingAnalysis,
    FinancingTerms,
    analyze_financing,
    calculate_effective_apr,
    calculate_total_cost,
    resolve_effective_advance,
)
from financing_mcp.predatory import analyze_predatory

mcp = FastMCP(
    "financing-analyzer",
    instructions=(
        "SMB financing analysis tools. Use these for precise financial math — "
        "never do APR calculations, cost projections, or payment math yourself. "
        "Always call analyze_financing first to get the numbers, then "
        "detect_predatory to check for red flags, then get_market_benchmarks "
        "to contextualize the offer."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: Full financing analysis
# ---------------------------------------------------------------------------


@mcp.tool()
def analyze_offer(
    advance_amount: float,
    repayment_type: str,
    product_type: str = "mca",
    factor_rate: float | None = None,
    total_repayment: float | None = None,
    stated_cost: float | None = None,
    fixed_payment: float | None = None,
    payment_frequency: str | None = None,
    holdback_pct: float | None = None,
    estimated_monthly_revenue: float | None = None,
    term_months: float | None = None,
    term_days: int | None = None,
    minimum_payment: float | None = None,
    minimum_payment_period_days: int = 30,
    origination_fee: float = 0.0,
    origination_fee_pct: float = 0.0,
    fee_deducted_from_advance: bool = False,
    late_fee_rate: float | None = None,
    late_fee_period_days: int | None = None,
    late_fee_grace_days: int = 0,
    late_fee_description: str = "",
    third_party_payer: str | None = None,
) -> dict:
    """Analyze a financing offer and return all computed metrics.

    Provide the terms extracted from the contract. At minimum you need
    advance_amount and one of: factor_rate, total_repayment, or stated_cost.

    Returns: total_repayment, total_cost_of_capital, effective_apr,
    cents_on_dollar, payment_amount, num_payments, and completeness info.
    If data is missing, tells you which fields are needed.

    Args:
        advance_amount: The principal/funded amount (e.g., 50000)
        repayment_type: "fixed", "percentage", or "lump_sum"
        product_type: "mca", "receivables_purchase", "po_financing", or "term_loan"
        factor_rate: The factor rate if stated (e.g., 1.35)
        total_repayment: Total amount to be repaid if stated
        stated_cost: The financing cost/fee if stated separately
        fixed_payment: Exact daily/weekly payment amount
        payment_frequency: "daily" or "weekly"
        holdback_pct: Percentage of sales taken (0-1, e.g., 0.15 for 15%)
        estimated_monthly_revenue: Projected monthly revenue
        term_months: Term in months
        term_days: Term in days (used if term_months not provided)
        minimum_payment: Minimum payment amount per period
        minimum_payment_period_days: How often minimum is due (30=monthly, 60=bi-monthly)
        origination_fee: Flat fee amount
        origination_fee_pct: Fee as percentage of advance (0-1)
        fee_deducted_from_advance: Whether fee was taken from the advance
        late_fee_rate: Late fee rate per period (e.g., 0.0016 for 0.16%)
        late_fee_period_days: How often late fees apply (e.g., 5 for every 5 days)
        late_fee_grace_days: Grace period before late fees start
        late_fee_description: Plain English description of late fees
        third_party_payer: Who pays (e.g., "Target") for PO/receivables
    """
    cost_escalation = None
    if late_fee_rate is not None and late_fee_period_days is not None:
        cost_escalation = CostEscalation(
            rate=late_fee_rate,
            period_days=late_fee_period_days,
            grace_period_days=late_fee_grace_days,
            description=late_fee_description,
        )

    terms = FinancingTerms(
        advance_amount=advance_amount,
        repayment_type=repayment_type,
        product_type=product_type,
        factor_rate=factor_rate,
        total_repayment=total_repayment,
        stated_cost=stated_cost,
        fixed_payment=fixed_payment,
        payment_frequency=payment_frequency,
        holdback_pct=holdback_pct,
        estimated_monthly_revenue=estimated_monthly_revenue,
        term_months=term_months,
        term_days=term_days,
        minimum_payment=minimum_payment,
        minimum_payment_period_days=minimum_payment_period_days,
        origination_fee=origination_fee,
        origination_fee_pct=origination_fee_pct,
        fee_deducted_from_advance=fee_deducted_from_advance,
        cost_escalation=cost_escalation,
        third_party_payer=third_party_payer,
    )

    analysis = analyze_financing(terms)
    return _analysis_to_dict(analysis)


# ---------------------------------------------------------------------------
# Tool 2: Predatory detection
# ---------------------------------------------------------------------------


@mcp.tool()
def detect_predatory_terms(
    advance_amount: float,
    repayment_type: str,
    effective_apr: float,
    has_confession_of_judgment: bool = False,
    product_type: str = "mca",
    factor_rate: float | None = None,
    total_repayment: float | None = None,
    stated_cost: float | None = None,
    term_months: float | None = None,
    payment_frequency: str | None = None,
    minimum_payment: float | None = None,
    minimum_payment_period_days: int = 30,
    origination_fee: float = 0.0,
    origination_fee_pct: float = 0.0,
    fee_deducted_from_advance: bool = False,
) -> dict:
    """Detect predatory terms in a financing offer.

    Returns a list of red flags with severity (WARNING or DANGER),
    whether the offer is predatory (any DANGER flag), and a risk score (0-1).

    Always call analyze_offer first to get the effective_apr, then pass it here.

    Args:
        advance_amount: The principal/funded amount
        repayment_type: "fixed", "percentage", or "lump_sum"
        effective_apr: The APR from analyze_offer (required)
        has_confession_of_judgment: Whether the contract has a COJ clause
        product_type: Product type
        factor_rate: Factor rate if known
        total_repayment: Total repayment if known
        stated_cost: Stated cost if known
        term_months: Term in months if known
        payment_frequency: "daily" or "weekly"
        minimum_payment: Minimum payment amount
        minimum_payment_period_days: Minimum payment period
        origination_fee: Flat fee amount
        origination_fee_pct: Fee as percentage
        fee_deducted_from_advance: Whether fee was deducted
    """
    terms = FinancingTerms(
        advance_amount=advance_amount,
        repayment_type=repayment_type,
        product_type=product_type,
        factor_rate=factor_rate,
        total_repayment=total_repayment,
        stated_cost=stated_cost,
        term_months=term_months,
        payment_frequency=payment_frequency,
        minimum_payment=minimum_payment,
        minimum_payment_period_days=minimum_payment_period_days,
        origination_fee=origination_fee,
        origination_fee_pct=origination_fee_pct,
        fee_deducted_from_advance=fee_deducted_from_advance,
    )

    result = analyze_predatory(terms, effective_apr, has_coj=has_confession_of_judgment)

    return {
        "is_predatory": result.is_predatory,
        "risk_score": round(result.risk_score, 2),
        "num_red_flags": len(result.red_flags),
        "red_flags": [
            {
                "name": flag.name,
                "severity": flag.severity.value,
                "description": flag.description,
            }
            for flag in result.red_flags
        ],
    }


# ---------------------------------------------------------------------------
# Tool 3: Quick APR calculation
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_apr(
    advance_amount: float,
    total_cost: float,
    term_months: float,
    fee_deducted_from_advance: bool = False,
    origination_fee: float = 0.0,
) -> dict:
    """Calculate the effective APR for a financing offer.

    A lightweight tool for quick APR checks without a full analysis.

    Args:
        advance_amount: The principal/funded amount
        total_cost: Total cost of capital (total_repayment - advance + fees)
        term_months: Term in months
        fee_deducted_from_advance: Whether fee was deducted from advance
        origination_fee: Fee amount (used to compute effective advance if deducted)
    """
    effective_advance = advance_amount
    if fee_deducted_from_advance:
        effective_advance = advance_amount - origination_fee

    if term_months <= 0:
        return {"error": "term_months must be greater than 0"}

    apr = (total_cost / effective_advance) * (12 / term_months) * 100

    return {
        "effective_apr": round(apr, 2),
        "effective_advance": effective_advance,
        "total_cost": total_cost,
        "term_months": term_months,
    }


# ---------------------------------------------------------------------------
# Tool 4: Market benchmarks
# ---------------------------------------------------------------------------


@mcp.tool()
def get_market_benchmarks(
    product_type: str,
    effective_apr: float | None = None,
    factor_rate: float | None = None,
    cents_on_dollar: float | None = None,
) -> dict:
    """Get market benchmark ranges for a financing product type.

    Optionally pass the offer's metrics to classify where it falls
    relative to the market (below_market, competitive, typical,
    above_market, or high).

    Args:
        product_type: "mca", "receivables_purchase", "po_financing", or "term_loan"
        effective_apr: The offer's APR to classify (optional)
        factor_rate: The offer's factor rate to classify (optional)
        cents_on_dollar: The offer's cost per dollar to classify (optional)
    """
    benchmarks = get_benchmarks(product_type)

    if effective_apr is not None or factor_rate is not None or cents_on_dollar is not None:
        classification = classify_offer(
            product_type,
            effective_apr=effective_apr,
            factor_rate=factor_rate,
            cents_on_dollar=cents_on_dollar,
        )
        benchmarks["offer_classification"] = classification

    return benchmarks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analysis_to_dict(analysis: FinancingAnalysis) -> dict:
    """Convert FinancingAnalysis to a clean dict for JSON serialization."""
    result = {
        "product_type": analysis.product_type,
        "factor_rate": round(analysis.factor_rate, 5),
        "total_repayment": round(analysis.total_repayment, 2),
        "origination_fee": round(analysis.origination_fee, 2),
        "effective_advance": round(analysis.effective_advance, 2),
        "total_cost_of_capital": round(analysis.total_cost_of_capital, 2),
        "cents_on_dollar": round(analysis.cents_on_dollar, 4),
        "is_complete": analysis.is_complete,
        "missing_fields": analysis.missing_fields,
    }

    if analysis.effective_apr is not None:
        result["effective_apr"] = round(analysis.effective_apr, 2)
    else:
        result["effective_apr"] = None

    if analysis.estimated_term_months is not None:
        result["estimated_term_months"] = round(analysis.estimated_term_months, 2)

    if analysis.payment_amount is not None:
        result["payment_amount"] = round(analysis.payment_amount, 2)

    if analysis.num_payments is not None:
        result["num_payments"] = analysis.num_payments

    if analysis.worst_case_term_months is not None:
        result["worst_case_term_months"] = round(analysis.worst_case_term_months, 2)
        result["worst_case_apr"] = round(analysis.worst_case_apr, 2) if analysis.worst_case_apr else None

    if analysis.escalation_description is not None:
        result["late_fees"] = {
            "description": analysis.escalation_description,
            "extra_cost_if_30_days_late": round(analysis.escalated_cost_30_days, 2) if analysis.escalated_cost_30_days else None,
            "extra_cost_if_90_days_late": round(analysis.escalated_cost_90_days, 2) if analysis.escalated_cost_90_days else None,
        }

    return result


# ---------------------------------------------------------------------------
# Health check (skips auth)
# ---------------------------------------------------------------------------


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "service": "financing-mcp"})
