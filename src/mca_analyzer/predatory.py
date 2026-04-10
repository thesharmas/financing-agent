"""Predatory term detection for MCA offers.

Rule-based detection of red flags in MCA terms.
Each detector returns a finding with severity and explanation.
"""

from dataclasses import dataclass
from enum import Enum

from mca_analyzer.calculations import MCATerms


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
HIGH_APR = 100.0  # percent
SHORT_TERM_MONTHS = 3
DAILY_PAYMENT_FREQUENCY = "daily"


def detect_high_factor_rate(terms: MCATerms) -> RedFlag | None:
    """Flag factor rates above 1.4 as warning, above 1.5 as danger."""
    raise NotImplementedError


def detect_high_apr(terms: MCATerms, effective_apr: float) -> RedFlag | None:
    """Flag effective APR above 100% as danger."""
    raise NotImplementedError


def detect_daily_payments(terms: MCATerms) -> RedFlag | None:
    """Flag daily ACH payments as warning — increases cash flow strain."""
    raise NotImplementedError


def detect_short_term(terms: MCATerms) -> RedFlag | None:
    """Flag terms under 3 months as warning — often indicates stacking."""
    raise NotImplementedError


def detect_high_origination_fee(terms: MCATerms) -> RedFlag | None:
    """Flag origination fees above 3% as warning, above 5% as danger."""
    raise NotImplementedError


def detect_confession_of_judgment(has_coj: bool) -> RedFlag | None:
    """Flag confession of judgment clause as danger.

    COJ clauses waive the borrower's right to defend against collection.
    This is a non-numeric flag — extracted from document text by the LLM.
    """
    raise NotImplementedError


def analyze_predatory(terms: MCATerms, effective_apr: float, has_coj: bool = False) -> PredatoryAnalysis:
    """Run all predatory detectors and return full analysis."""
    raise NotImplementedError
