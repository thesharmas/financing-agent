"""Math correctness evals for financing calculations.

These are deterministic tests — no LLM involved.
They define the interface and expected behavior of the calculation functions.
All must pass at 100% accuracy. Math errors destroy trust.
"""

import pytest

from financing_mcp.calculations import (
    FinancingTerms,
    analyze_financing,
    calculate_cents_on_dollar,
    calculate_effective_apr,
    calculate_escalated_cost,
    calculate_num_payments,
    calculate_payment_amount,
    calculate_total_cost,
    calculate_total_repayment,
    calculate_worst_case_apr,
    resolve_effective_advance,
    resolve_factor_rate,
    resolve_origination_fee,
    resolve_term_months,
)

from .fixtures import (
    AGGRESSIVE_MCA,
    AGGRESSIVE_MCA_EXPECTED,
    FEE_MCA,
    FEE_MCA_EXPECTED,
    FIXED_WEEKLY_TERM_LOAN,
    FIXED_WEEKLY_TERM_LOAN_EXPECTED,
    INCOMPLETE_MCA,
    INCOMPLETE_MCA_EXPECTED,
    LUMP_SUM_PO_FINANCING,
    LUMP_SUM_PO_FINANCING_EXPECTED,
    NO_FACTOR_MCA,
    NO_FACTOR_MCA_EXPECTED,
    PERCENTAGE_60DAY_MINIMUM,
    PERCENTAGE_60DAY_MINIMUM_EXPECTED,
    PERCENTAGE_MCA,
    PERCENTAGE_MCA_EXPECTED,
    PERCENTAGE_MIN_MCA,
    PERCENTAGE_MIN_MCA_EXPECTED,
    PERCENTAGE_RECEIVABLES,
    PERCENTAGE_RECEIVABLES_EXPECTED,
    PERCENTAGE_WITH_STATED_TERM,
    PERCENTAGE_WITH_STATED_TERM_EXPECTED,
    PREDATORY_MCA,
    PREDATORY_MCA_EXPECTED,
    REASONABLE_MCA,
    REASONABLE_MCA_EXPECTED,
    STANDARD_MCA,
    STANDARD_MCA_EXPECTED,
    STATED_COST_MCA,
    STATED_COST_MCA_EXPECTED,
)

# All fixtures with full payment info (excludes incomplete)
FIXED_FIXTURES = [
    ("standard", STANDARD_MCA, STANDARD_MCA_EXPECTED),
    ("aggressive", AGGRESSIVE_MCA, AGGRESSIVE_MCA_EXPECTED),
    ("predatory", PREDATORY_MCA, PREDATORY_MCA_EXPECTED),
    ("reasonable", REASONABLE_MCA, REASONABLE_MCA_EXPECTED),
    ("with_fee", FEE_MCA, FEE_MCA_EXPECTED),
]

PERCENTAGE_FIXTURES = [
    ("percentage", PERCENTAGE_MCA, PERCENTAGE_MCA_EXPECTED),
    ("percentage_min", PERCENTAGE_MIN_MCA, PERCENTAGE_MIN_MCA_EXPECTED),
]

ALL_COMPLETE_FIXTURES = FIXED_FIXTURES + PERCENTAGE_FIXTURES

# Multi-product fixtures
MULTI_PRODUCT_FIXTURES = [
    ("lump_sum_po", LUMP_SUM_PO_FINANCING, LUMP_SUM_PO_FINANCING_EXPECTED),
    ("pct_receivables", PERCENTAGE_RECEIVABLES, PERCENTAGE_RECEIVABLES_EXPECTED),
    ("fixed_weekly_loan", FIXED_WEEKLY_TERM_LOAN, FIXED_WEEKLY_TERM_LOAN_EXPECTED),
    ("pct_60day_min", PERCENTAGE_60DAY_MINIMUM, PERCENTAGE_60DAY_MINIMUM_EXPECTED),
    ("pct_stated_term", PERCENTAGE_WITH_STATED_TERM, PERCENTAGE_WITH_STATED_TERM_EXPECTED),
]


# --- Step 0: Resolve inputs ---


class TestResolveInputs:
    def test_factor_rate_used_directly(self):
        assert resolve_factor_rate(STANDARD_MCA) == 1.35

    def test_factor_rate_from_total_repayment(self):
        result = resolve_factor_rate(NO_FACTOR_MCA)
        assert result == pytest.approx(NO_FACTOR_MCA_EXPECTED["factor_rate"])

    def test_factor_rate_from_stated_cost(self):
        result = resolve_factor_rate(STATED_COST_MCA)
        assert result == pytest.approx(STATED_COST_MCA_EXPECTED["factor_rate"])

    def test_raises_if_no_pricing(self):
        terms = FinancingTerms(advance_amount=10_000, repayment_type="fixed")
        with pytest.raises(ValueError):
            resolve_factor_rate(terms)

    def test_origination_fee_flat(self):
        assert resolve_origination_fee(FEE_MCA) == 1_200.0

    def test_origination_fee_pct(self):
        assert resolve_origination_fee(PREDATORY_MCA) == 1_250.0

    def test_origination_fee_none(self):
        assert resolve_origination_fee(STANDARD_MCA) == 0.0

    def test_effective_advance_no_fee(self):
        assert resolve_effective_advance(STANDARD_MCA) == 50_000.0

    def test_effective_advance_fee_deducted(self):
        result = resolve_effective_advance(PREDATORY_MCA)
        assert result == pytest.approx(PREDATORY_MCA_EXPECTED["effective_advance"])

    def test_effective_advance_fee_separate(self):
        result = resolve_effective_advance(FEE_MCA)
        assert result == pytest.approx(FEE_MCA_EXPECTED["effective_advance"])


# --- Step 1: Total Repayment ---


class TestTotalRepayment:
    @pytest.mark.parametrize("name,terms,expected", ALL_COMPLETE_FIXTURES + MULTI_PRODUCT_FIXTURES)
    def test_total_repayment(self, name, terms, expected):
        result = calculate_total_repayment(terms)
        assert result == pytest.approx(expected["total_repayment"], rel=1e-4), (
            f"[{name}] total_repayment: got {result}, expected {expected['total_repayment']}"
        )

    def test_factor_rate_of_1_means_no_cost(self):
        terms = FinancingTerms(
            advance_amount=10_000, repayment_type="fixed", factor_rate=1.0,
        )
        assert calculate_total_repayment(terms) == 10_000.0

    def test_from_total_repayment_input(self):
        result = calculate_total_repayment(NO_FACTOR_MCA)
        assert result == pytest.approx(67_500.0)

    def test_from_stated_cost_input(self):
        result = calculate_total_repayment(STATED_COST_MCA)
        assert result == pytest.approx(67_500.0)


# --- Step 2: Total Cost of Capital ---


class TestTotalCost:
    @pytest.mark.parametrize("name,terms,expected", ALL_COMPLETE_FIXTURES + MULTI_PRODUCT_FIXTURES)
    def test_total_cost(self, name, terms, expected):
        result = calculate_total_cost(terms)
        assert result == pytest.approx(expected["total_cost"], rel=1e-4), (
            f"[{name}] total_cost: got {result}, expected {expected['total_cost']}"
        )

    def test_fee_deducted_increases_cost(self):
        result_deducted = calculate_total_cost(PREDATORY_MCA)
        assert result_deducted == pytest.approx(15_000.0, rel=1e-4)

    def test_no_fee_means_just_factor_cost(self):
        result = calculate_total_cost(STANDARD_MCA)
        assert result == pytest.approx(17_500.0, rel=1e-4)


# --- Step 3: Term Resolution ---


class TestTermResolution:
    def test_stated_term_used_directly(self):
        assert resolve_term_months(STANDARD_MCA) == 6

    def test_term_from_holdback_and_revenue(self):
        result = resolve_term_months(PERCENTAGE_MCA)
        assert result == pytest.approx(PERCENTAGE_MCA_EXPECTED["estimated_term_months"], rel=1e-2)

    def test_term_from_fixed_payment(self):
        terms = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.35,
            fixed_payment=535.71, payment_frequency="daily",
        )
        result = resolve_term_months(terms)
        assert result == pytest.approx(6.0, rel=1e-2)

    def test_term_none_if_insufficient_data(self):
        assert resolve_term_months(INCOMPLETE_MCA) is None

    def test_term_from_days(self):
        """term_days should convert to months via / 30."""
        result = resolve_term_months(LUMP_SUM_PO_FINANCING)
        assert result == pytest.approx(LUMP_SUM_PO_FINANCING_EXPECTED["estimated_term_months"], rel=1e-2)


# --- Step 3: Number of Payments ---


class TestNumPayments:
    @pytest.mark.parametrize("name,terms,expected", ALL_COMPLETE_FIXTURES)
    def test_num_payments(self, name, terms, expected):
        result = calculate_num_payments(terms)
        assert result == expected["num_payments"], (
            f"[{name}] num_payments: got {result}, expected {expected['num_payments']}"
        )

    def test_lump_sum_is_one_payment(self):
        assert calculate_num_payments(LUMP_SUM_PO_FINANCING) == 1

    def test_daily_uses_21_business_days(self):
        terms = FinancingTerms(
            advance_amount=10_000, repayment_type="fixed", factor_rate=1.2,
            term_months=1, payment_frequency="daily",
        )
        assert calculate_num_payments(terms) == 21

    def test_weekly_uses_4_33_weeks(self):
        terms = FinancingTerms(
            advance_amount=10_000, repayment_type="fixed", factor_rate=1.2,
            term_months=1, payment_frequency="weekly",
        )
        assert calculate_num_payments(terms) == 4

    def test_none_if_no_term(self):
        assert calculate_num_payments(INCOMPLETE_MCA) is None


# --- Step 3: Payment Amount ---


class TestPaymentAmount:
    @pytest.mark.parametrize("name,terms,expected", ALL_COMPLETE_FIXTURES)
    def test_payment_amount(self, name, terms, expected):
        result = calculate_payment_amount(terms)
        assert result == pytest.approx(expected["payment_amount"], rel=1e-2), (
            f"[{name}] payment_amount: got {result}, expected {expected['payment_amount']}"
        )

    def test_lump_sum_payment_is_total(self):
        result = calculate_payment_amount(LUMP_SUM_PO_FINANCING)
        assert result == pytest.approx(LUMP_SUM_PO_FINANCING_EXPECTED["payment_amount"])

    def test_fixed_payment_used_directly(self):
        terms = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.35,
            fixed_payment=600.0, payment_frequency="daily",
        )
        assert calculate_payment_amount(terms) == 600.0

    def test_percentage_payment_from_revenue(self):
        result = calculate_payment_amount(PERCENTAGE_MCA)
        assert result == pytest.approx(571.43, rel=1e-2)

    def test_none_if_insufficient_data(self):
        assert calculate_payment_amount(INCOMPLETE_MCA) is None


# --- Step 4: Effective APR ---


class TestEffectiveAPR:
    @pytest.mark.parametrize("name,terms,expected", ALL_COMPLETE_FIXTURES + MULTI_PRODUCT_FIXTURES)
    def test_effective_apr(self, name, terms, expected):
        result = calculate_effective_apr(terms)
        assert result == pytest.approx(expected["effective_apr"], rel=1e-2), (
            f"[{name}] effective_apr: got {result}, expected {expected['effective_apr']}"
        )

    def test_shorter_term_means_higher_apr(self):
        long = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.35,
            term_months=12, payment_frequency="daily",
        )
        short = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.35,
            term_months=6, payment_frequency="daily",
        )
        assert calculate_effective_apr(short) > calculate_effective_apr(long)

    def test_higher_factor_means_higher_apr(self):
        low = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.15,
            term_months=6, payment_frequency="daily",
        )
        high = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.45,
            term_months=6, payment_frequency="daily",
        )
        assert calculate_effective_apr(high) > calculate_effective_apr(low)

    def test_fee_deducted_increases_apr(self):
        separate = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.30,
            term_months=6, payment_frequency="daily",
            origination_fee=2_500, fee_deducted_from_advance=False,
        )
        deducted = FinancingTerms(
            advance_amount=50_000, repayment_type="fixed", factor_rate=1.30,
            term_months=6, payment_frequency="daily",
            origination_fee=2_500, fee_deducted_from_advance=True,
        )
        assert calculate_effective_apr(deducted) > calculate_effective_apr(separate)

    def test_none_if_no_term(self):
        assert calculate_effective_apr(INCOMPLETE_MCA) is None


class TestWorstCaseAPR:
    def test_worst_case_with_minimum(self):
        result = calculate_worst_case_apr(PERCENTAGE_MIN_MCA)
        assert result == pytest.approx(
            PERCENTAGE_MIN_MCA_EXPECTED["worst_case_apr"], rel=1e-2
        )

    def test_none_without_minimum(self):
        assert calculate_worst_case_apr(STANDARD_MCA) is None

    def test_worst_case_lower_than_estimated(self):
        estimated = calculate_effective_apr(PERCENTAGE_MIN_MCA)
        worst = calculate_worst_case_apr(PERCENTAGE_MIN_MCA)
        assert worst < estimated


# --- Step 5: Cents on Dollar ---


class TestCentsOnDollar:
    @pytest.mark.parametrize("name,terms,expected", ALL_COMPLETE_FIXTURES + MULTI_PRODUCT_FIXTURES)
    def test_cents_on_dollar(self, name, terms, expected):
        result = calculate_cents_on_dollar(terms)
        assert result == pytest.approx(expected["cents_on_dollar"], rel=1e-2), (
            f"[{name}] cents_on_dollar: got {result}, expected {expected['cents_on_dollar']}"
        )

    def test_fee_deducted_increases_cents(self):
        result = calculate_cents_on_dollar(PREDATORY_MCA)
        assert result > 0.60


# --- Cost Escalation ---


class TestCostEscalation:
    def test_be_amazing_30_days_late(self):
        result = calculate_escalated_cost(LUMP_SUM_PO_FINANCING, 30)
        assert result == pytest.approx(LUMP_SUM_PO_FINANCING_EXPECTED["escalated_cost_30_days"], rel=1e-2)

    def test_be_amazing_90_days_late(self):
        result = calculate_escalated_cost(LUMP_SUM_PO_FINANCING, 90)
        assert result == pytest.approx(LUMP_SUM_PO_FINANCING_EXPECTED["escalated_cost_90_days"], rel=1e-2)

    def test_latin_goodness_30_days_late(self):
        result = calculate_escalated_cost(PERCENTAGE_RECEIVABLES, 30)
        assert result == pytest.approx(
            PERCENTAGE_RECEIVABLES_EXPECTED["escalated_cost_30_days"], rel=1e-2
        )

    def test_latin_goodness_90_days_late(self):
        result = calculate_escalated_cost(PERCENTAGE_RECEIVABLES, 90)
        assert result == pytest.approx(
            PERCENTAGE_RECEIVABLES_EXPECTED["escalated_cost_90_days"], rel=1e-2
        )

    def test_no_escalation_without_structure(self):
        assert calculate_escalated_cost(STANDARD_MCA, 30) is None

    def test_within_grace_period_no_cost(self):
        """During grace period, no late fees should apply."""
        result = calculate_escalated_cost(LUMP_SUM_PO_FINANCING, 5)  # Within 7-day grace
        assert result is None


# --- Full Analysis ---


class TestAnalyzeFinancing:
    def test_complete_mca_analysis(self):
        result = analyze_financing(STANDARD_MCA)
        assert result.product_type == "mca"
        assert result.total_repayment == pytest.approx(67_500.0)
        assert result.total_cost_of_capital == pytest.approx(17_500.0)
        assert result.effective_apr == pytest.approx(70.0, rel=1e-2)
        assert result.num_payments == 126
        assert result.payment_amount == pytest.approx(535.71, rel=1e-2)
        assert result.cents_on_dollar == pytest.approx(0.35, rel=1e-2)
        assert result.is_complete is True
        assert result.missing_fields == []

    def test_incomplete_analysis(self):
        result = analyze_financing(INCOMPLETE_MCA)
        assert result.total_repayment == pytest.approx(67_500.0)
        assert result.cents_on_dollar == pytest.approx(0.35, rel=1e-2)
        assert result.effective_apr is None
        assert result.num_payments is None
        assert result.is_complete is False
        assert len(result.missing_fields) > 0

    def test_worst_case_populated(self):
        result = analyze_financing(PERCENTAGE_MIN_MCA)
        assert result.worst_case_term_months == pytest.approx(13.5, rel=1e-2)
        assert result.worst_case_apr == pytest.approx(31.11, rel=1e-2)

    def test_worst_case_none_without_minimum(self):
        result = analyze_financing(STANDARD_MCA)
        assert result.worst_case_term_months is None
        assert result.worst_case_apr is None

    def test_shopify_60_day_minimum(self):
        result = analyze_financing(PERCENTAGE_60DAY_MINIMUM)
        assert result.worst_case_term_months == pytest.approx(
            PERCENTAGE_60DAY_MINIMUM_EXPECTED["worst_case_term_months"], rel=1e-2
        )
        assert result.worst_case_apr == pytest.approx(
            PERCENTAGE_60DAY_MINIMUM_EXPECTED["worst_case_apr"], rel=1e-2
        )

    def test_square_60_day_minimum(self):
        result = analyze_financing(PERCENTAGE_WITH_STATED_TERM)
        assert result.worst_case_term_months == pytest.approx(
            PERCENTAGE_WITH_STATED_TERM_EXPECTED["worst_case_term_months"], rel=1e-2
        )
        assert result.worst_case_apr == pytest.approx(
            PERCENTAGE_WITH_STATED_TERM_EXPECTED["worst_case_apr"], rel=1e-2
        )

    def test_ondeck_term_loan(self):
        result = analyze_financing(FIXED_WEEKLY_TERM_LOAN)
        assert result.product_type == "term_loan"
        assert result.effective_apr == pytest.approx(
            FIXED_WEEKLY_TERM_LOAN_EXPECTED["effective_apr"], rel=1e-2
        )
        assert result.payment_amount == FIXED_WEEKLY_TERM_LOAN_EXPECTED["payment_amount"]

    def test_po_financing_analysis(self):
        result = analyze_financing(LUMP_SUM_PO_FINANCING)
        assert result.product_type == "po_financing"
        assert result.effective_apr == pytest.approx(12.0, rel=1e-2)
        assert result.num_payments == 1
        assert result.escalation_description is not None
        assert result.escalated_cost_30_days == pytest.approx(7_948.80, rel=1e-2)

    def test_receivables_purchase_analysis(self):
        result = analyze_financing(PERCENTAGE_RECEIVABLES)
        assert result.product_type == "receivables_purchase"
        assert result.effective_apr == pytest.approx(14.79, rel=1e-2)
        assert result.escalated_cost_90_days == pytest.approx(5_739.90, rel=1e-2)
