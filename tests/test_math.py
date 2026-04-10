"""Math correctness evals for MCA calculations.

These are deterministic tests — no LLM involved.
They define the interface and expected behavior of the calculation functions.
All must pass at 100% accuracy. Math errors destroy trust.
"""

import pytest

from mca_analyzer.calculations import (
    MCATerms,
    analyze_mca,
    calculate_cents_on_dollar,
    calculate_effective_apr,
    calculate_num_payments,
    calculate_payment_amount,
    calculate_total_cost,
    calculate_total_repayment,
)

from .fixtures import (
    AGGRESSIVE_MCA,
    AGGRESSIVE_MCA_EXPECTED,
    FEE_MCA,
    FEE_MCA_EXPECTED,
    PREDATORY_MCA,
    PREDATORY_MCA_EXPECTED,
    REASONABLE_MCA,
    REASONABLE_MCA_EXPECTED,
    STANDARD_MCA,
    STANDARD_MCA_EXPECTED,
)

ALL_FIXTURES = [
    ("standard", STANDARD_MCA, STANDARD_MCA_EXPECTED),
    ("aggressive", AGGRESSIVE_MCA, AGGRESSIVE_MCA_EXPECTED),
    ("predatory", PREDATORY_MCA, PREDATORY_MCA_EXPECTED),
    ("reasonable", REASONABLE_MCA, REASONABLE_MCA_EXPECTED),
    ("with_fee", FEE_MCA, FEE_MCA_EXPECTED),
]


# --- Total Repayment ---


class TestTotalRepayment:
    @pytest.mark.parametrize("name,terms,expected", ALL_FIXTURES)
    def test_total_repayment(self, name, terms, expected):
        result = calculate_total_repayment(terms)
        assert result == pytest.approx(expected["total_repayment"], rel=1e-4), (
            f"[{name}] total_repayment: got {result}, expected {expected['total_repayment']}"
        )

    def test_factor_rate_of_1_means_no_cost(self):
        terms = MCATerms(
            advance_amount=10_000, factor_rate=1.0, term_months=6, payment_frequency="daily"
        )
        assert calculate_total_repayment(terms) == 10_000.0


# --- Total Cost of Capital ---


class TestTotalCost:
    @pytest.mark.parametrize("name,terms,expected", ALL_FIXTURES)
    def test_total_cost(self, name, terms, expected):
        result = calculate_total_cost(terms)
        assert result == pytest.approx(expected["total_cost"], rel=1e-4), (
            f"[{name}] total_cost: got {result}, expected {expected['total_cost']}"
        )

    def test_flat_fee_added_to_cost(self):
        """Flat origination fee should be included in total cost."""
        result = calculate_total_cost(FEE_MCA)
        assert result == pytest.approx(13_200.0, rel=1e-4)

    def test_percentage_fee_calculated_correctly(self):
        """Percentage-based origination fee should be computed from advance amount."""
        result = calculate_total_cost(PREDATORY_MCA)
        # 5% of 25000 = 1250, plus (25000 * 1.55 - 25000) = 13750
        assert result == pytest.approx(15_000.0, rel=1e-4)

    def test_no_fee_means_just_factor_cost(self):
        result = calculate_total_cost(STANDARD_MCA)
        assert result == pytest.approx(17_500.0, rel=1e-4)


# --- Number of Payments ---


class TestNumPayments:
    @pytest.mark.parametrize("name,terms,expected", ALL_FIXTURES)
    def test_num_payments(self, name, terms, expected):
        result = calculate_num_payments(terms)
        assert result == expected["num_payments"], (
            f"[{name}] num_payments: got {result}, expected {expected['num_payments']}"
        )

    def test_daily_uses_21_business_days(self):
        terms = MCATerms(
            advance_amount=10_000, factor_rate=1.2, term_months=1, payment_frequency="daily"
        )
        assert calculate_num_payments(terms) == 21

    def test_weekly_uses_4_33_weeks(self):
        terms = MCATerms(
            advance_amount=10_000, factor_rate=1.2, term_months=1, payment_frequency="weekly"
        )
        # 1 * 4.33 = 4.33, rounded to 4
        assert calculate_num_payments(terms) == 4


# --- Payment Amount ---


class TestPaymentAmount:
    @pytest.mark.parametrize("name,terms,expected", ALL_FIXTURES)
    def test_payment_amount(self, name, terms, expected):
        result = calculate_payment_amount(terms)
        assert result == pytest.approx(expected["payment_amount"], rel=1e-2), (
            f"[{name}] payment_amount: got {result}, expected {expected['payment_amount']}"
        )


# --- Effective APR ---


class TestEffectiveAPR:
    @pytest.mark.parametrize("name,terms,expected", ALL_FIXTURES)
    def test_effective_apr(self, name, terms, expected):
        result = calculate_effective_apr(terms)
        assert result == pytest.approx(expected["effective_apr"], rel=1e-2), (
            f"[{name}] effective_apr: got {result}, expected {expected['effective_apr']}"
        )

    def test_shorter_term_means_higher_apr(self):
        """Same factor rate over shorter term = higher APR."""
        long = MCATerms(
            advance_amount=50_000, factor_rate=1.35, term_months=12, payment_frequency="daily"
        )
        short = MCATerms(
            advance_amount=50_000, factor_rate=1.35, term_months=6, payment_frequency="daily"
        )
        assert calculate_effective_apr(short) > calculate_effective_apr(long)

    def test_higher_factor_means_higher_apr(self):
        """Higher factor rate = higher APR (same term)."""
        low = MCATerms(
            advance_amount=50_000, factor_rate=1.15, term_months=6, payment_frequency="daily"
        )
        high = MCATerms(
            advance_amount=50_000, factor_rate=1.45, term_months=6, payment_frequency="daily"
        )
        assert calculate_effective_apr(high) > calculate_effective_apr(low)

    def test_fees_increase_apr(self):
        """Origination fees should increase the effective APR."""
        no_fee = MCATerms(
            advance_amount=50_000, factor_rate=1.30, term_months=6, payment_frequency="daily"
        )
        with_fee = MCATerms(
            advance_amount=50_000,
            factor_rate=1.30,
            term_months=6,
            payment_frequency="daily",
            origination_fee=2_000,
        )
        assert calculate_effective_apr(with_fee) > calculate_effective_apr(no_fee)


# --- Cents on Dollar ---


class TestCentsOnDollar:
    @pytest.mark.parametrize("name,terms,expected", ALL_FIXTURES)
    def test_cents_on_dollar(self, name, terms, expected):
        result = calculate_cents_on_dollar(terms)
        assert result == pytest.approx(expected["cents_on_dollar"], rel=1e-2), (
            f"[{name}] cents_on_dollar: got {result}, expected {expected['cents_on_dollar']}"
        )


# --- Full Analysis ---


class TestAnalyzeMCA:
    def test_returns_all_fields(self):
        result = analyze_mca(STANDARD_MCA)
        assert result.total_repayment == pytest.approx(67_500.0)
        assert result.total_cost_of_capital == pytest.approx(17_500.0)
        assert result.effective_apr == pytest.approx(70.0, rel=1e-2)
        assert result.num_payments == 126
        assert result.payment_amount == pytest.approx(535.71, rel=1e-2)
        assert result.cents_on_dollar == pytest.approx(0.35, rel=1e-2)
