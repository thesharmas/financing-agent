"""Extraction accuracy evals using DeepEval.

Tests whether the LLM correctly extracts key terms from financing offer text.
Uses GEval (LLM-as-judge) to evaluate extraction completeness and accuracy.

HOW DEEPEVAL WORKS HERE:
========================

DeepEval's GEval metric uses an LLM as a judge. Instead of writing hardcoded
assertions ("assert output['factor_rate'] == 1.35"), we describe WHAT to check
in plain English (evaluation_steps), and a judge LLM scores the output.

Why use LLM-as-judge instead of exact matching?
- The agent's output is free-form text or loosely structured JSON
- "daily" vs "Daily ACH" vs "daily_ach" should all be considered correct
- The agent might include extra useful fields we didn't anticipate
- Exact matching is brittle; LLM judging is flexible but principled

The flow:
1. We define evaluation_steps — the rubric for the judge
2. We define evaluation_params — which parts of the test case the judge sees
3. We set a threshold — minimum score (0-1) to pass
4. DeepEval sends the test case + rubric to a judge LLM
5. The judge scores using chain-of-thought + token probability normalization
6. If score >= threshold, the test passes

These tests require OPENAI_API_KEY to be set (for the judge LLM).
"""

import json

import pytest

try:
    from deepeval import assert_test
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    HAS_DEEPEVAL = True
except ImportError:
    HAS_DEEPEVAL = False

pytestmark = pytest.mark.skipif(not HAS_DEEPEVAL, reason="deepeval not installed")

if not HAS_DEEPEVAL:
    pytest.skip("deepeval not installed", allow_module_level=True)

from .fixtures import (
    SAMPLE_OFFER_TEXT_1,
    SAMPLE_OFFER_TEXT_1_EXPECTED,
    SAMPLE_OFFER_TEXT_2,
    SAMPLE_OFFER_TEXT_2_EXPECTED,
    SAMPLE_OFFER_TEXT_3,
    SAMPLE_OFFER_TEXT_3_EXPECTED,
)


# ============================================================================
# METRICS — the rubrics the judge LLM uses to score extraction quality
# ============================================================================

# Metric 1: Did the agent find ALL the fields?
#
# evaluation_params tells the judge which parts of the test case to look at.
# Here it gets actual_output (what the agent extracted) and expected_output
# (the ground truth). It does NOT see the input text — it's only comparing
# two JSON objects.
extraction_completeness = GEval(
    name="Extraction Completeness",
    evaluation_steps=[
        "Compare the 'actual output' JSON against the 'expected output' JSON.",
        "Check that every field present in the expected output is also present "
        "in the actual output.",
        "Missing fields should be heavily penalized.",
        "Extra fields that are reasonable (e.g., funder name, contract type) "
        "should not be penalized.",
    ],
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.8,
)

# Metric 2: Are the extracted VALUES correct?
#
# Higher threshold than completeness — a present but wrong value is worse
# than a missing value. Missing can be asked for; wrong silently corrupts.
extraction_accuracy = GEval(
    name="Extraction Accuracy",
    evaluation_steps=[
        "Compare each numeric value in 'actual output' against 'expected output'.",
        "Values must match exactly or within 1% relative tolerance.",
        "String values (like payment_frequency, repayment_type) must match "
        "semantically — e.g., 'daily' matches 'Daily ACH', 'percentage' matches "
        "'Percentage of sales'.",
        "Boolean values (like has_confession_of_judgment) must match exactly.",
        "Each incorrect value should be heavily penalized.",
    ],
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.9,
)

# Metric 3: Did the agent identify the product type correctly?
#
# This is important because the same fields mean different things in
# different product types. Getting the product type wrong cascades errors.
product_type_identification = GEval(
    name="Product Type Identification",
    evaluation_steps=[
        "Check if the 'actual output' correctly identifies the financing product type.",
        "MCA / Merchant Cash Advance: factor rate, daily/weekly ACH, holdback percentage.",
        "Receivables Purchase: purchase of receivables/invoices, discount amount, "
        "specified percentage of sales.",
        "PO Financing: purchase order financing, lump sum repayment, tied to specific "
        "purchase orders from named retailers.",
        "The product type must match the 'expected output'.",
        "Using different but equivalent terminology is acceptable — e.g., "
        "'revenue-based financing' for MCA, 'invoice factoring' for receivables.",
    ],
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.9,
)

# Metric 4: Did the agent catch special clauses and red flags?
#
# This checks extraction of non-numeric terms — legal clauses, collateral,
# late fee structures, third-party payer details. These require reading
# comprehension, not just number extraction.
clause_extraction = GEval(
    name="Clause and Red Flag Extraction",
    evaluation_steps=[
        "Check if the 'actual output' identifies key non-numeric terms from the contract.",
        "These include: confession of judgment (present or absent), collateral/security "
        "interest, late fee structures, arbitration clauses, third-party payer details.",
        "For each clause present in the 'expected output', verify the 'actual output' "
        "captures it correctly.",
        "Getting a clause wrong (saying COJ is absent when it's present) is a critical failure.",
        "Missing a clause is penalized but less severely than getting it wrong.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.8,
)


# ============================================================================
# HELPER
# ============================================================================

def _make_extraction_test_case(
    offer_text: str, expected: dict, actual_output: str
) -> LLMTestCase:
    """Create a test case for extraction evaluation.

    LLMTestCase is DeepEval's container for one evaluation. It holds:
    - input: what the user asked / the source document
    - actual_output: what the agent produced
    - expected_output: the ground truth to compare against

    Not all metrics use all fields — the evaluation_params on each metric
    controls which fields the judge sees.
    """
    return LLMTestCase(
        input=f"Extract all key financial terms from this financing offer:\n\n{offer_text}",
        actual_output=actual_output,
        expected_output=json.dumps(expected, indent=2),
    )


# ============================================================================
# TESTS — MCA offers
# ============================================================================
# These tests use placeholder actual_output for now.
# Once the agent is built, actual_output will come from the agent's response.
#
# To activate these tests:
# 1. Build the agent's extract_terms() function
# 2. Replace the placeholder with: actual = agent.extract_terms(offer_text)
# 3. Remove the skipif decorator


class TestExtractionMCA:
    """Tests for extracting terms from standard MCA offers."""

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer1_completeness(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_1_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_1, SAMPLE_OFFER_TEXT_1_EXPECTED, actual
        )
        assert_test(test_case, [extraction_completeness])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer1_accuracy(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_1_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_1, SAMPLE_OFFER_TEXT_1_EXPECTED, actual
        )
        assert_test(test_case, [extraction_accuracy])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer1_clauses(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_1_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_1, SAMPLE_OFFER_TEXT_1_EXPECTED, actual
        )
        assert_test(test_case, [clause_extraction])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer2_completeness(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_2_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_2, SAMPLE_OFFER_TEXT_2_EXPECTED, actual
        )
        assert_test(test_case, [extraction_completeness])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer2_accuracy(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_2_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_2, SAMPLE_OFFER_TEXT_2_EXPECTED, actual
        )
        assert_test(test_case, [extraction_accuracy])


# ============================================================================
# TESTS — Percentage-based / Receivables (offer text 3)
# ============================================================================


class TestExtractionPercentage:
    """Tests for extracting terms from percentage-based / receivables offers."""

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer3_completeness(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_3_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_3, SAMPLE_OFFER_TEXT_3_EXPECTED, actual
        )
        assert_test(test_case, [extraction_completeness])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer3_accuracy(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_3_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_3, SAMPLE_OFFER_TEXT_3_EXPECTED, actual
        )
        assert_test(test_case, [extraction_accuracy])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_offer3_product_type(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_3_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_3, SAMPLE_OFFER_TEXT_3_EXPECTED, actual
        )
        assert_test(test_case, [product_type_identification])


# ============================================================================
# EXTRACTION CONTRACT — what fields the agent MUST return per product type
# ============================================================================
# These tests run now (no agent needed) — they validate our test fixtures.

# Fields every extraction must include regardless of product type
COMMON_REQUIRED_FIELDS = [
    "advance_amount",
    "origination_fee",
    "has_confession_of_judgment",
]

# Fields required for MCA extraction
MCA_REQUIRED_FIELDS = COMMON_REQUIRED_FIELDS + [
    "factor_rate",
    "total_repayment",
    "term_months",
    "payment_frequency",
    "daily_payment",
]

# Fields required for percentage-based / receivables extraction
PERCENTAGE_REQUIRED_FIELDS = COMMON_REQUIRED_FIELDS + [
    "repayment_type",
    "holdback_pct",
    "estimated_monthly_revenue",
]


class TestExtractionContract:
    """Ensure the extraction output schema contains all required fields.

    These tests validate our test FIXTURES, not the agent.
    They catch mistakes in the ground truth data.
    """

    def test_mca_fixture_1_has_required_fields(self):
        for field in MCA_REQUIRED_FIELDS:
            assert field in SAMPLE_OFFER_TEXT_1_EXPECTED, (
                f"MCA fixture 1 missing required field: {field}"
            )

    def test_mca_fixture_2_has_required_fields(self):
        for field in MCA_REQUIRED_FIELDS:
            assert field in SAMPLE_OFFER_TEXT_2_EXPECTED, (
                f"MCA fixture 2 missing required field: {field}"
            )

    def test_percentage_fixture_3_has_required_fields(self):
        for field in PERCENTAGE_REQUIRED_FIELDS:
            assert field in SAMPLE_OFFER_TEXT_3_EXPECTED, (
                f"Percentage fixture 3 missing required field: {field}"
            )
