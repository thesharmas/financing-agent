"""Predatory detection evals.

Deterministic tests for rule-based red flag detection.
These test the detection functions directly — no LLM involved.
"""

import pytest

from mca_analyzer.calculations import MCATerms
from mca_analyzer.predatory import (
    Severity,
    analyze_predatory,
    detect_confession_of_judgment,
    detect_daily_payments,
    detect_high_apr,
    detect_high_factor_rate,
    detect_high_origination_fee,
    detect_short_term,
)

from .fixtures import (
    AGGRESSIVE_MCA,
    AGGRESSIVE_MCA_EXPECTED,
    PREDATORY_MCA,
    PREDATORY_MCA_EXPECTED,
    REASONABLE_MCA,
    REASONABLE_MCA_EXPECTED,
    STANDARD_MCA,
    STANDARD_MCA_EXPECTED,
)


# --- High Factor Rate Detection ---


class TestHighFactorRate:
    def test_flags_factor_above_1_4_as_warning(self):
        terms = MCATerms(
            advance_amount=10_000, factor_rate=1.42, term_months=6, payment_frequency="daily"
        )
        flag = detect_high_factor_rate(terms)
        assert flag is not None
        assert flag.severity == Severity.WARNING

    def test_flags_factor_above_1_5_as_danger(self):
        flag = detect_high_factor_rate(PREDATORY_MCA)  # 1.55
        assert flag is not None
        assert flag.severity == Severity.DANGER

    def test_no_flag_for_normal_factor(self):
        flag = detect_high_factor_rate(STANDARD_MCA)  # 1.35
        assert flag is None

    def test_no_flag_at_boundary(self):
        terms = MCATerms(
            advance_amount=10_000, factor_rate=1.40, term_months=6, payment_frequency="daily"
        )
        flag = detect_high_factor_rate(terms)
        assert flag is None  # 1.4 is the threshold, not flagged at exactly 1.4


# --- High APR Detection ---


class TestHighAPR:
    def test_flags_apr_above_100_as_danger(self):
        flag = detect_high_apr(AGGRESSIVE_MCA, AGGRESSIVE_MCA_EXPECTED["effective_apr"])
        assert flag is not None
        assert flag.severity == Severity.DANGER

    def test_no_flag_for_normal_apr(self):
        flag = detect_high_apr(STANDARD_MCA, STANDARD_MCA_EXPECTED["effective_apr"])
        assert flag is None  # 70% APR is high but under 100%

    def test_no_flag_for_low_apr(self):
        flag = detect_high_apr(REASONABLE_MCA, REASONABLE_MCA_EXPECTED["effective_apr"])
        assert flag is None


# --- Daily Payment Detection ---


class TestDailyPayments:
    def test_flags_daily_as_warning(self):
        flag = detect_daily_payments(STANDARD_MCA)  # daily
        assert flag is not None
        assert flag.severity == Severity.WARNING

    def test_no_flag_for_weekly(self):
        flag = detect_daily_payments(REASONABLE_MCA)  # weekly
        assert flag is None


# --- Short Term Detection ---


class TestShortTerm:
    def test_flags_short_term_as_warning(self):
        flag = detect_short_term(PREDATORY_MCA)  # 3 months
        assert flag is not None
        assert flag.severity == Severity.WARNING

    def test_no_flag_for_normal_term(self):
        flag = detect_short_term(STANDARD_MCA)  # 6 months
        assert flag is None


# --- High Origination Fee Detection ---


class TestHighOriginationFee:
    def test_flags_5pct_fee_as_danger(self):
        flag = detect_high_origination_fee(PREDATORY_MCA)  # 5%
        assert flag is not None
        assert flag.severity == Severity.DANGER

    def test_no_flag_for_no_fee(self):
        flag = detect_high_origination_fee(STANDARD_MCA)  # 0%
        assert flag is None

    def test_flags_4pct_as_warning(self):
        terms = MCATerms(
            advance_amount=10_000,
            factor_rate=1.30,
            term_months=6,
            payment_frequency="daily",
            origination_fee_pct=0.04,
        )
        flag = detect_high_origination_fee(terms)
        assert flag is not None
        assert flag.severity == Severity.WARNING


# --- Confession of Judgment ---


class TestConfessionOfJudgment:
    def test_flags_coj_as_danger(self):
        flag = detect_confession_of_judgment(has_coj=True)
        assert flag is not None
        assert flag.severity == Severity.DANGER

    def test_no_flag_without_coj(self):
        flag = detect_confession_of_judgment(has_coj=False)
        assert flag is None


# --- Full Predatory Analysis ---


class TestAnalyzePredatory:
    def test_predatory_offer_detected(self):
        """The predatory fixture should be flagged as predatory with multiple red flags."""
        result = analyze_predatory(
            PREDATORY_MCA, PREDATORY_MCA_EXPECTED["effective_apr"], has_coj=True
        )
        assert result.is_predatory is True
        assert len(result.red_flags) >= 3  # high factor, high APR, short term, high fee, COJ
        assert result.risk_score >= 0.7

        # Must have at least one DANGER flag
        danger_flags = [f for f in result.red_flags if f.severity == Severity.DANGER]
        assert len(danger_flags) >= 1

    def test_reasonable_offer_not_predatory(self):
        """The reasonable fixture should not be flagged as predatory."""
        result = analyze_predatory(
            REASONABLE_MCA, REASONABLE_MCA_EXPECTED["effective_apr"], has_coj=False
        )
        assert result.is_predatory is False
        assert result.risk_score <= 0.3

    def test_standard_offer_has_warnings_but_not_predatory(self):
        """Standard MCA may have warnings (daily ACH) but shouldn't be predatory."""
        result = analyze_predatory(
            STANDARD_MCA, STANDARD_MCA_EXPECTED["effective_apr"], has_coj=False
        )
        assert result.is_predatory is False

    def test_red_flags_have_descriptions(self):
        """Every red flag must include a plain English description."""
        result = analyze_predatory(
            PREDATORY_MCA, PREDATORY_MCA_EXPECTED["effective_apr"], has_coj=True
        )
        for flag in result.red_flags:
            assert flag.description, f"Red flag '{flag.name}' missing description"
            assert len(flag.description) > 20, f"Red flag '{flag.name}' description too short"
