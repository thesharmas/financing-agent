"""SMB financing calculations.

Product-agnostic financial math for comparing any financing product.
Different product types (MCA, receivables purchase, PO financing) use
different contract language but resolve to the same core metrics.

The five core calculations (same for every product type):
1. Total repayment — advance × factor_rate
2. Total cost of capital — repayment - effective_advance + fees
3. Payments & term — depends on repayment type (fixed, percentage, lump_sum)
4. Effective APR — (cost / effective_advance) × (12 / term) × 100
5. Cents on dollar — cost / effective_advance
"""

from dataclasses import dataclass, field

# Constants for payment schedule calculations
BUSINESS_DAYS_PER_MONTH = 21  # 252 trading days / 12 months
WEEKS_PER_MONTH = 4.33  # 52 weeks / 12 months
DAYS_PER_MONTH = 30.0  # Calendar days approximation


@dataclass
class CostEscalation:
    """Late fee / additional cost structure that kicks in after a deadline.

    Different products express this differently:
    - MCA: rarely has late fees (factor rate is fixed)
    - PO Financing: "0.16% per 5-day period after Day 247"
    - Receivables: "0.42% additional receivables per 10-day period after Collection Date"
    """

    rate: float  # e.g., 0.0016 for 0.16%
    period_days: int  # e.g., 5 (every 5 days)
    grace_period_days: int = 0  # Days after term before late fees start
    description: str = ""  # Plain English: "0.16% per 5-day period"


@dataclass
class FinancingTerms:
    """Key terms extracted from any SMB financing offer.

    Contracts vary in what they state explicitly. At minimum we need
    advance_amount and one of: factor_rate, total_repayment, or stated_cost.
    Everything else is optional and lets us compute more detailed analysis.
    """

    # --- Always present ---
    advance_amount: float  # Principal approved (e.g., $50,000)
    repayment_type: str  # "fixed", "percentage", or "lump_sum"
    product_type: str = "mca"  # "mca", "receivables_purchase", "po_financing"

    # --- Pricing: at least one must be provided ---
    factor_rate: float | None = None  # e.g., 1.35
    total_repayment: float | None = None  # e.g., $67,500
    stated_cost: float | None = None  # e.g., $17,500

    # --- Fixed repayment fields ---
    fixed_payment: float | None = None  # Exact daily/weekly ACH amount
    payment_frequency: str | None = None  # "daily" or "weekly"

    # --- Percentage (holdback) repayment fields ---
    holdback_pct: float | None = None  # e.g., 0.15 for 15% of sales
    estimated_monthly_revenue: float | None = None  # Lender's projection

    # --- May or may not be stated ---
    term_months: float | None = None  # Explicit term if contract states it
    term_days: int | None = None  # Some contracts state days, not months
    monthly_minimum: float | None = None  # Floor payment (percentage only)

    # --- Fees ---
    origination_fee: float = 0.0  # Flat dollar fee
    origination_fee_pct: float = 0.0  # Fee as percentage of advance
    fee_deducted_from_advance: bool = False  # Was the fee taken from the advance?

    # --- Cost escalation (late fees) ---
    cost_escalation: CostEscalation | None = None

    # --- Third-party payer (PO financing, receivables) ---
    third_party_payer: str | None = None  # e.g., "Target", "Retailer and Distributor"

    def get_term_months(self) -> float | None:
        """Return term in months, converting from days if needed."""
        if self.term_months is not None:
            return self.term_months
        if self.term_days is not None:
            return self.term_days / DAYS_PER_MONTH
        return None


@dataclass
class FinancingAnalysis:
    """Computed analysis of any SMB financing offer."""

    product_type: str  # What kind of product this is

    # --- Always computable (no term needed) ---
    factor_rate: float  # Resolved from inputs
    total_repayment: float  # advance × factor_rate
    origination_fee: float  # Resolved dollar amount
    effective_advance: float  # What cash the business actually received
    total_cost_of_capital: float  # total_repayment - effective_advance
    cents_on_dollar: float  # total_cost / effective_advance

    # --- Requires term (stated or estimated) ---
    effective_apr: float | None  # None if term can't be determined
    estimated_term_months: float | None  # Calculated if not stated
    payment_amount: float | None  # Per-period payment
    num_payments: int | None

    # --- Worst case (only if monthly minimum exists) ---
    worst_case_term_months: float | None
    worst_case_apr: float | None

    # --- Cost escalation ---
    escalation_description: str | None  # Plain English late fee explanation
    escalated_cost_30_days: float | None  # Extra cost if 30 days late
    escalated_cost_90_days: float | None  # Extra cost if 90 days late

    # --- Completeness ---
    is_complete: bool  # True if we could compute everything
    missing_fields: list[str]  # What we'd need for a full analysis


# ---------------------------------------------------------------------------
# Step 0: Resolve inputs — normalize the different ways contracts state pricing
# ---------------------------------------------------------------------------


def resolve_origination_fee(terms: FinancingTerms) -> float:
    """Resolve the origination fee to a dollar amount.

    If both flat fee and percentage are set, use whichever is larger.
    """
    flat = terms.origination_fee
    pct = terms.advance_amount * terms.origination_fee_pct
    return max(flat, pct)


def resolve_factor_rate(terms: FinancingTerms) -> float:
    """Resolve factor rate from whichever pricing field is provided.

    Contract may give factor_rate, total_repayment, or stated_cost.
    Returns the factor rate.
    """
    if terms.factor_rate is not None:
        return terms.factor_rate

    if terms.total_repayment is not None:
        return terms.total_repayment / terms.advance_amount

    if terms.stated_cost is not None:
        return (terms.advance_amount + terms.stated_cost) / terms.advance_amount

    raise ValueError("Need at least one of: factor_rate, total_repayment, stated_cost")


def resolve_effective_advance(terms: FinancingTerms) -> float:
    """Calculate what cash the business actually received.

    If the fee was deducted from the advance, effective_advance is lower.
    """
    fee = resolve_origination_fee(terms)
    if terms.fee_deducted_from_advance:
        return terms.advance_amount - fee
    return terms.advance_amount


# ---------------------------------------------------------------------------
# Step 1: Total repayment
# ---------------------------------------------------------------------------


def calculate_total_repayment(terms: FinancingTerms) -> float:
    """advance_amount × factor_rate"""
    factor = resolve_factor_rate(terms)
    return terms.advance_amount * factor


# ---------------------------------------------------------------------------
# Step 2: Total cost of capital
# ---------------------------------------------------------------------------


def calculate_total_cost(terms: FinancingTerms) -> float:
    """total_repayment - effective_advance.

    If fee is deducted from advance, the effective_advance is lower,
    so total_cost is higher (you received less but repay the same).

    If fee is paid separately, we add it on top of the financing cost.
    """
    repayment = calculate_total_repayment(terms)
    effective = resolve_effective_advance(terms)
    fee = resolve_origination_fee(terms)

    if terms.fee_deducted_from_advance:
        # Fee already captured in the lower effective_advance
        return repayment - effective
    else:
        # Fee paid separately, add to financing cost
        return (repayment - terms.advance_amount) + fee


# ---------------------------------------------------------------------------
# Step 3: Number of payments and payment amount
# ---------------------------------------------------------------------------


def calculate_num_payments(terms: FinancingTerms) -> int | None:
    """Calculate total number of payments.

    Fixed daily: term × 21 business days
    Fixed weekly: round(term × 4.33)
    Percentage: estimated from revenue projection
    Lump sum: 1 (single payment)
    Returns None if we can't determine it.
    """
    if terms.repayment_type == "lump_sum":
        return 1

    term = resolve_term_months(terms)
    if term is None:
        return None

    if terms.repayment_type == "fixed":
        if terms.payment_frequency == "daily":
            return round(term * BUSINESS_DAYS_PER_MONTH)
        elif terms.payment_frequency == "weekly":
            return round(term * WEEKS_PER_MONTH)
        return None
    else:
        # Percentage-based: estimate daily payments over the term
        return round(term * BUSINESS_DAYS_PER_MONTH)


def calculate_payment_amount(terms: FinancingTerms) -> float | None:
    """Calculate per-period payment amount.

    Fixed: total_repayment / num_payments
    Percentage: estimated_monthly_revenue × holdback_pct / 21
    Lump sum: total_repayment (single payment)
    Returns None if we can't determine it.
    """
    repayment = calculate_total_repayment(terms)

    if terms.repayment_type == "lump_sum":
        return repayment

    if terms.repayment_type == "fixed":
        if terms.fixed_payment is not None:
            return terms.fixed_payment
        num = calculate_num_payments(terms)
        if num is None:
            return None
        return round(repayment / num, 2)
    else:
        # Percentage-based: estimated daily payment from revenue
        if terms.holdback_pct is not None and terms.estimated_monthly_revenue is not None:
            return round(
                terms.estimated_monthly_revenue * terms.holdback_pct / BUSINESS_DAYS_PER_MONTH,
                2,
            )
        return None


# ---------------------------------------------------------------------------
# Step 3b: Resolve term — from stated value or back-calculated
# ---------------------------------------------------------------------------


def resolve_term_months(terms: FinancingTerms) -> float | None:
    """Determine the term in months from whatever info is available.

    Priority:
    1. Stated term in contract (months or days)
    2. Percentage: total_repayment / (monthly_revenue × holdback_pct)
    3. Fixed: total_repayment / (fixed_payment × payments_per_month)
    4. None — can't determine
    """
    stated = terms.get_term_months()
    if stated is not None:
        return stated

    repayment = calculate_total_repayment(terms)

    # Percentage-based: estimate from revenue projection
    if terms.holdback_pct is not None and terms.estimated_monthly_revenue is not None:
        monthly_payback = terms.estimated_monthly_revenue * terms.holdback_pct
        if monthly_payback > 0:
            return repayment / monthly_payback

    # Fixed: back-calculate from payment amount
    if terms.fixed_payment is not None and terms.fixed_payment > 0:
        if terms.payment_frequency == "daily":
            payments_per_month = BUSINESS_DAYS_PER_MONTH
        elif terms.payment_frequency == "weekly":
            payments_per_month = WEEKS_PER_MONTH
        else:
            return None
        monthly_payback = terms.fixed_payment * payments_per_month
        return repayment / monthly_payback

    return None


# ---------------------------------------------------------------------------
# Step 4: Effective APR
# ---------------------------------------------------------------------------


def calculate_effective_apr(terms: FinancingTerms) -> float | None:
    """APR = (total_cost / effective_advance) × (12 / term_months) × 100

    Returns None if term can't be determined.
    """
    term = resolve_term_months(terms)
    if term is None or term == 0:
        return None

    cost = calculate_total_cost(terms)
    effective = resolve_effective_advance(terms)
    return (cost / effective) * (12 / term) * 100


def calculate_worst_case_apr(terms: FinancingTerms) -> float | None:
    """APR based on worst-case term (using monthly minimum).

    Only applicable for percentage-based with a monthly minimum.
    """
    if terms.monthly_minimum is None or terms.monthly_minimum == 0:
        return None

    repayment = calculate_total_repayment(terms)
    worst_term = repayment / terms.monthly_minimum
    cost = calculate_total_cost(terms)
    effective = resolve_effective_advance(terms)
    return (cost / effective) * (12 / worst_term) * 100


# ---------------------------------------------------------------------------
# Step 5: Cents on dollar
# ---------------------------------------------------------------------------


def calculate_cents_on_dollar(terms: FinancingTerms) -> float:
    """Cost per dollar the business actually received."""
    cost = calculate_total_cost(terms)
    effective = resolve_effective_advance(terms)
    return cost / effective


# ---------------------------------------------------------------------------
# Cost escalation (late fees)
# ---------------------------------------------------------------------------


def calculate_escalated_cost(terms: FinancingTerms, days_late: int) -> float | None:
    """Calculate additional cost if payment is late by N days.

    Returns the extra cost beyond the base total_cost, or None if
    no escalation structure exists.
    """
    if terms.cost_escalation is None:
        return None

    esc = terms.cost_escalation
    # Days subject to late fees (after grace period)
    billable_days = max(0, days_late - esc.grace_period_days)
    if billable_days == 0:
        return None

    # Number of fee periods
    periods = billable_days / esc.period_days

    # Late fee applied to unpaid balance (total_repayment)
    repayment = calculate_total_repayment(terms)
    return repayment * esc.rate * periods


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------


def _find_missing_fields(terms: FinancingTerms) -> list[str]:
    """Determine what fields are missing for a complete analysis."""
    missing = []

    # Check pricing
    if terms.factor_rate is None and terms.total_repayment is None and terms.stated_cost is None:
        missing.append("factor_rate or total_repayment or stated_cost")

    # Check term resolvability
    if resolve_term_months(terms) is None:
        if terms.repayment_type == "fixed":
            missing.append("term_months or fixed_payment + payment_frequency")
        elif terms.repayment_type == "percentage":
            missing.append("term_months or holdback_pct + estimated_monthly_revenue")
        # lump_sum always needs a stated term
        elif terms.repayment_type == "lump_sum":
            missing.append("term_months or term_days")

    return missing


def analyze_financing(terms: FinancingTerms) -> FinancingAnalysis:
    """Run full analysis on financing terms. Returns all computed metrics."""
    factor = resolve_factor_rate(terms)
    fee = resolve_origination_fee(terms)
    effective = resolve_effective_advance(terms)
    repayment = calculate_total_repayment(terms)
    cost = calculate_total_cost(terms)
    term = resolve_term_months(terms)
    missing = _find_missing_fields(terms)

    worst_term = None
    if terms.monthly_minimum is not None and terms.monthly_minimum > 0:
        worst_term = repayment / terms.monthly_minimum

    # Cost escalation projections
    esc_desc = None
    esc_30 = None
    esc_90 = None
    if terms.cost_escalation is not None:
        esc = terms.cost_escalation
        esc_desc = esc.description or f"{esc.rate:.2%} per {esc.period_days}-day period"
        esc_30 = calculate_escalated_cost(terms, 30)
        esc_90 = calculate_escalated_cost(terms, 90)

    return FinancingAnalysis(
        product_type=terms.product_type,
        factor_rate=factor,
        total_repayment=repayment,
        origination_fee=fee,
        effective_advance=effective,
        total_cost_of_capital=cost,
        cents_on_dollar=calculate_cents_on_dollar(terms),
        effective_apr=calculate_effective_apr(terms),
        estimated_term_months=term,
        payment_amount=calculate_payment_amount(terms),
        num_payments=calculate_num_payments(terms),
        worst_case_term_months=worst_term,
        worst_case_apr=calculate_worst_case_apr(terms),
        escalation_description=esc_desc,
        escalated_cost_30_days=esc_30,
        escalated_cost_90_days=esc_90,
        is_complete=len(missing) == 0,
        missing_fields=missing,
    )
