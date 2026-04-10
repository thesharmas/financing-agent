"""MCA financial calculations.

All math functions for converting MCA terms to comparable metrics.
These functions are the source of truth for financial math —
the LLM must never do these calculations itself.
"""

from dataclasses import dataclass


@dataclass
class MCATerms:
    """Key terms extracted from an MCA offer."""

    advance_amount: float  # Principal amount received
    factor_rate: float  # e.g., 1.35
    term_months: int  # Repayment period in months
    payment_frequency: str  # "daily" or "weekly"
    origination_fee: float = 0.0  # Upfront fee as dollar amount
    origination_fee_pct: float = 0.0  # Upfront fee as percentage


@dataclass
class MCAAnalysis:
    """Computed analysis of an MCA offer."""

    total_repayment: float
    total_cost_of_capital: float  # total_repayment - advance_amount + fees
    effective_apr: float  # Annualized cost as a percentage
    payment_amount: float  # Per-period payment (daily or weekly)
    num_payments: int
    holdback_amount: float  # Same as payment_amount for MCA
    cents_on_dollar: float  # Cost per dollar borrowed


def calculate_total_repayment(terms: MCATerms) -> float:
    """Calculate total amount to be repaid.

    total_repayment = advance_amount * factor_rate
    """
    raise NotImplementedError


def calculate_total_cost(terms: MCATerms) -> float:
    """Calculate total cost of capital including fees.

    total_cost = (advance_amount * factor_rate) - advance_amount + origination_fee
    If origination_fee_pct is set, origination_fee = advance_amount * origination_fee_pct
    """
    raise NotImplementedError


def calculate_payment_amount(terms: MCATerms) -> float:
    """Calculate per-period payment amount.

    For daily: total_repayment / (term_months * 21 business days)
    For weekly: total_repayment / (term_months * 4.33 weeks)
    """
    raise NotImplementedError


def calculate_num_payments(terms: MCATerms) -> int:
    """Calculate total number of payments.

    For daily: term_months * 21 business days
    For weekly: term_months * 4.33, rounded to nearest int
    """
    raise NotImplementedError


def calculate_effective_apr(terms: MCATerms) -> float:
    """Calculate effective APR from MCA terms.

    Uses the simple interest annualization:
        APR = (total_cost / advance_amount) * (12 / term_months) * 100

    Where total_cost = (advance_amount * factor_rate) - advance_amount + fees

    Returns APR as a percentage (e.g., 85.6 for 85.6%).
    """
    raise NotImplementedError


def calculate_cents_on_dollar(terms: MCATerms) -> float:
    """Calculate cost per dollar borrowed.

    cents_on_dollar = total_cost / advance_amount
    e.g., 0.35 means 35 cents per dollar borrowed
    """
    raise NotImplementedError


def analyze_mca(terms: MCATerms) -> MCAAnalysis:
    """Run full analysis on MCA terms. Returns all computed metrics."""
    raise NotImplementedError
