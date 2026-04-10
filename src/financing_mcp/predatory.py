"""Predatory term detection for SMB financing offers.

Rule-based detection of red flags in financing terms.
Each detector checks one specific concern and returns a RedFlag
with a severity level and a plain English explanation, or None if clean.

Severity levels:
- WARNING: concerning but not necessarily predatory on its own
- DANGER: a serious red flag that may indicate a predatory offer
"""

from dataclasses import dataclass
from enum import Enum

from financing_mcp.calculations import FinancingTerms, resolve_factor_rate, resolve_origination_fee


class Severity(Enum):
    WARNING = "warning"
    DANGER = "danger"


@dataclass
class RedFlag:
    """A detected predatory term or red flag."""

    name: str
    severity: Severity
    description: str  # Plain English explanation of why this is bad


@dataclass
class PredatoryAnalysis:
    """Full predatory analysis result."""

    red_flags: list[RedFlag]
    is_predatory: bool  # True if any DANGER-level flags
    risk_score: float  # 0.0 (safe) to 1.0 (highly predatory)


# Thresholds
HIGH_FACTOR_RATE = 1.4
VERY_HIGH_FACTOR_RATE = 1.5
HIGH_APR = 100.0
HIGH_ORIGINATION_FEE_PCT = 0.03
VERY_HIGH_ORIGINATION_FEE_PCT = 0.05
SHORT_TERM_MONTHS = 3

# Risk score weights — how much each flag contributes to the overall score
RISK_WEIGHTS = {
    "high_factor_rate_warning": 0.15,
    "high_factor_rate_danger": 0.25,
    "high_apr": 0.25,
    "daily_payments": 0.10,
    "short_term": 0.15,
    "high_fee_warning": 0.10,
    "high_fee_danger": 0.20,
    "minimum_payment": 0.10,
    "confession_of_judgment": 0.30,
}


def detect_high_factor_rate(terms: FinancingTerms) -> RedFlag | None:
    """Flag factor rates above 1.4 as warning, above 1.5 as danger."""
    factor = resolve_factor_rate(terms)

    if factor > VERY_HIGH_FACTOR_RATE:
        return RedFlag(
            name="high_factor_rate",
            severity=Severity.DANGER,
            description=(
                f"Factor rate of {factor:.2f} is very high. "
                f"You are paying back ${factor:.2f} for every $1 borrowed. "
                f"Most reasonable MCAs have factor rates below 1.4."
            ),
        )

    if factor > HIGH_FACTOR_RATE:
        return RedFlag(
            name="high_factor_rate",
            severity=Severity.WARNING,
            description=(
                f"Factor rate of {factor:.2f} is above average. "
                f"You are paying back ${factor:.2f} for every $1 borrowed. "
                f"Consider whether you can find a lower rate."
            ),
        )

    return None


def detect_high_apr(terms: FinancingTerms, effective_apr: float) -> RedFlag | None:
    """Flag effective APR above 100% as danger."""
    if effective_apr > HIGH_APR:
        return RedFlag(
            name="high_apr",
            severity=Severity.DANGER,
            description=(
                f"Effective APR of {effective_apr:.1f}% is extremely high. "
                f"For comparison, credit cards typically charge 20-30% APR "
                f"and even high-risk term loans rarely exceed 50% APR."
            ),
        )
    return None


def detect_daily_payments(terms: FinancingTerms) -> RedFlag | None:
    """Flag daily ACH payments as warning — increases cash flow strain.

    Only applies to fixed repayment types. Percentage-based MCAs pull
    from sales naturally, so the frequency is less of a concern.
    """
    if terms.repayment_type == "fixed" and terms.payment_frequency == "daily":
        return RedFlag(
            name="daily_payments",
            severity=Severity.WARNING,
            description=(
                "Daily ACH payments put constant strain on your cash flow. "
                "Every business day, money leaves your account regardless of "
                "how sales went that day. Weekly payments give more breathing room."
            ),
        )
    return None


def detect_short_term(terms: FinancingTerms) -> RedFlag | None:
    """Flag terms under 3 months as warning — often indicates stacking."""
    if terms.term_months is not None and terms.term_months <= SHORT_TERM_MONTHS:
        return RedFlag(
            name="short_term",
            severity=Severity.WARNING,
            description=(
                f"A {terms.term_months}-month term is very short. "
                f"Short terms mean higher daily payments and can indicate "
                f"'stacking' — taking a new advance to pay off an existing one, "
                f"which creates a dangerous debt cycle."
            ),
        )
    return None


def detect_high_origination_fee(terms: FinancingTerms) -> RedFlag | None:
    """Flag origination fees above 3% as warning, above 5% as danger."""
    fee = resolve_origination_fee(terms)
    if fee == 0:
        return None

    fee_pct = fee / terms.advance_amount

    if fee_pct >= VERY_HIGH_ORIGINATION_FEE_PCT:
        return RedFlag(
            name="high_origination_fee",
            severity=Severity.DANGER,
            description=(
                f"Origination fee of {fee_pct:.0%} (${fee:,.0f}) is excessive. "
                f"This fee is either deducted from your advance (so you receive less cash) "
                f"or paid upfront. Either way, it increases your real cost of borrowing."
            ),
        )

    if fee_pct > HIGH_ORIGINATION_FEE_PCT:
        return RedFlag(
            name="high_origination_fee",
            severity=Severity.WARNING,
            description=(
                f"Origination fee of {fee_pct:.0%} (${fee:,.0f}) is above average. "
                f"Typical origination fees are 1-3% of the advance amount."
            ),
        )

    return None


def detect_minimum_payment(terms: FinancingTerms) -> RedFlag | None:
    """Flag minimum payment on percentage-based products.

    A minimum payment undercuts the main advantage of percentage-based
    repayment — that payments flex down when sales are slow.
    """
    if terms.minimum_payment is not None and terms.minimum_payment > 0:
        period = terms.minimum_payment_period_days
        period_label = "month" if period == 30 else f"{period} days"
        return RedFlag(
            name="minimum_payment",
            severity=Severity.WARNING,
            description=(
                f"Minimum payment of ${terms.minimum_payment:,.0f} every {period_label} "
                f"removes the flexibility that makes percentage-based repayment attractive. "
                f"In slow periods, you still owe this amount regardless of sales."
            ),
        )
    return None


def detect_confession_of_judgment(has_coj: bool) -> RedFlag | None:
    """Flag confession of judgment clause as danger.

    COJ clauses waive the borrower's right to defend against collection.
    This is a non-numeric flag — extracted from document text by the LLM.
    """
    if has_coj:
        return RedFlag(
            name="confession_of_judgment",
            severity=Severity.DANGER,
            description=(
                "This contract contains a Confession of Judgment clause. "
                "By signing, you waive your right to defend yourself in court "
                "if the lender decides to collect. The lender can seize your assets "
                "without giving you a chance to dispute the claim. "
                "Several states have banned this practice because it is so harmful."
            ),
        )
    return None


def analyze_predatory(
    terms: FinancingTerms, effective_apr: float, has_coj: bool = False
) -> PredatoryAnalysis:
    """Run all predatory detectors and return full analysis.

    is_predatory is True if any DANGER-level flag is found.
    risk_score is a weighted sum of all flags, capped at 1.0.
    """
    detectors = [
        detect_high_factor_rate(terms),
        detect_high_apr(terms, effective_apr),
        detect_daily_payments(terms),
        detect_short_term(terms),
        detect_high_origination_fee(terms),
        detect_minimum_payment(terms),
        detect_confession_of_judgment(has_coj),
    ]

    red_flags = [f for f in detectors if f is not None]
    has_danger = any(f.severity == Severity.DANGER for f in red_flags)

    # Calculate risk score from weights
    score = 0.0
    for flag in red_flags:
        if flag.severity == Severity.DANGER:
            weight_key = f"{flag.name}_danger" if f"{flag.name}_danger" in RISK_WEIGHTS else flag.name
        else:
            weight_key = f"{flag.name}_warning" if f"{flag.name}_warning" in RISK_WEIGHTS else flag.name
        score += RISK_WEIGHTS.get(weight_key, 0.10)

    score = min(score, 1.0)

    return PredatoryAnalysis(
        red_flags=red_flags,
        is_predatory=has_danger,
        risk_score=score,
    )
