"""MCA financial calculations.

All math functions for converting MCA terms to comparable metrics.
These functions are the source of truth for financial math —
the LLM must never do these calculations itself.

The five core calculations:
1. Total repayment — advance × factor_rate
2. Total cost of capital — repayment - effective_advance + fees
3. Payments & term — depends on repayment type (fixed vs percentage)
4. Effective APR — (cost / effective_advance) × (12 / term) × 100
5. Cents on dollar — cost / effective_advance
"""

from dataclasses import dataclass, field

# Constants for payment schedule calculations
BUSINESS_DAYS_PER_MONTH = 21  # 252 trading days / 12 months
WEEKS_PER_MONTH = 4.33  # 52 weeks / 12 months


@dataclass
class MCATerms:
    """Key terms extracted from an MCA offer.

    Contracts vary in what they state explicitly. At minimum we need
    advance_amount and one of: factor_rate, total_repayment, or stated_cost.
    Everything else is optional and lets us compute more detailed analysis.
    """

    # --- Always present ---
    advance_amount: float  # Principal approved (e.g., $50,000)
    repayment_type: str  # "fixed" or "percentage"

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
    monthly_minimum: float | None = None  # Floor payment (percentage only)

    # --- Fees ---
    origination_fee: float = 0.0  # Flat dollar fee
    origination_fee_pct: float = 0.0  # Fee as percentage of advance
    fee_deducted_from_advance: bool = False  # Was the fee taken from the advance?


@dataclass
class MCAAnalysis:
    """Computed analysis of an MCA offer."""

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

    # --- Completeness ---
    is_complete: bool  # True if we could compute everything
    missing_fields: list[str]  # What we'd need for a full analysis


# ---------------------------------------------------------------------------
# Step 0: Resolve inputs — normalize the different ways contracts state pricing
# ---------------------------------------------------------------------------


def resolve_origination_fee(terms: MCATerms) -> float:
    """Resolve the origination fee to a dollar amount.

    If both flat fee and percentage are set, use whichever is larger.
    """
    flat = terms.origination_fee
    pct = terms.advance_amount * terms.origination_fee_pct
    return max(flat, pct)


def resolve_factor_rate(terms: MCATerms) -> float:
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


def resolve_effective_advance(terms: MCATerms) -> float:
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


def calculate_total_repayment(terms: MCATerms) -> float:
    """advance_amount × factor_rate"""
    factor = resolve_factor_rate(terms)
    return terms.advance_amount * factor


# ---------------------------------------------------------------------------
# Step 2: Total cost of capital
# ---------------------------------------------------------------------------


def calculate_total_cost(terms: MCATerms) -> float:
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


def calculate_num_payments(terms: MCATerms) -> int | None:
    """Calculate total number of payments.

    Fixed daily: term × 21 business days
    Fixed weekly: round(term × 4.33)
    Percentage: estimated from revenue projection
    Returns None if we can't determine it.
    """
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


def calculate_payment_amount(terms: MCATerms) -> float | None:
    """Calculate per-period payment amount.

    Fixed: total_repayment / num_payments
    Percentage: estimated_monthly_revenue × holdback_pct / 21
    Returns None if we can't determine it.
    """
    if terms.repayment_type == "fixed":
        if terms.fixed_payment is not None:
            return terms.fixed_payment
        num = calculate_num_payments(terms)
        if num is None:
            return None
        repayment = calculate_total_repayment(terms)
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


def resolve_term_months(terms: MCATerms) -> float | None:
    """Determine the term in months from whatever info is available.

    Priority:
    1. Stated term in contract
    2. Percentage: total_repayment / (monthly_revenue × holdback_pct)
    3. Fixed: total_repayment / (fixed_payment × payments_per_month)
    4. None — can't determine
    """
    if terms.term_months is not None:
        return terms.term_months

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


def calculate_effective_apr(terms: MCATerms) -> float | None:
    """APR = (total_cost / effective_advance) × (12 / term_months) × 100

    Returns None if term can't be determined.
    """
    term = resolve_term_months(terms)
    if term is None or term == 0:
        return None

    cost = calculate_total_cost(terms)
    effective = resolve_effective_advance(terms)
    return (cost / effective) * (12 / term) * 100


def calculate_worst_case_apr(terms: MCATerms) -> float | None:
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


def calculate_cents_on_dollar(terms: MCATerms) -> float:
    """Cost per dollar the business actually received."""
    cost = calculate_total_cost(terms)
    effective = resolve_effective_advance(terms)
    return cost / effective


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------


def _find_missing_fields(terms: MCATerms) -> list[str]:
    """Determine what fields are missing for a complete analysis."""
    missing = []

    # Check pricing
    if terms.factor_rate is None and terms.total_repayment is None and terms.stated_cost is None:
        missing.append("factor_rate or total_repayment or stated_cost")

    # Check term resolvability
    if resolve_term_months(terms) is None:
        if terms.repayment_type == "fixed":
            missing.append("term_months or fixed_payment + payment_frequency")
        else:
            missing.append("term_months or holdback_pct + estimated_monthly_revenue")

    return missing


def analyze_mca(terms: MCATerms) -> MCAAnalysis:
    """Run full analysis on MCA terms. Returns all computed metrics."""
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

    return MCAAnalysis(
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
        is_complete=len(missing) == 0,
        missing_fields=missing,
    )
