"""Extraction accuracy evals using DeepEval.

Tests whether the LLM correctly extracts all key terms from MCA offer text.
Uses GEval (LLM-as-judge) to evaluate extraction completeness and accuracy.

These tests require ANTHROPIC_API_KEY or OPENAI_API_KEY to be set.
"""

import json

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from .fixtures import (
    SAMPLE_OFFER_TEXT_1,
    SAMPLE_OFFER_TEXT_1_EXPECTED,
    SAMPLE_OFFER_TEXT_2,
    SAMPLE_OFFER_TEXT_2_EXPECTED,
)

# -- Metrics --

extraction_completeness = GEval(
    name="Extraction Completeness",
    evaluation_steps=[
        "Compare the 'actual output' JSON against the 'expected output' JSON.",
        "Check that every field present in the expected output is also present in the actual output.",
        "Missing fields should be heavily penalized.",
        "Extra fields that are reasonable (e.g., funder name) should not be penalized.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.8,
)

extraction_accuracy = GEval(
    name="Extraction Accuracy",
    evaluation_steps=[
        "Compare each numeric value in 'actual output' against 'expected output'.",
        "Values must match exactly or within 1% relative tolerance.",
        "String values (like payment_frequency) must match semantically (e.g., 'daily' == 'Daily ACH').",
        "Boolean values (like has_confession_of_judgment) must match exactly.",
        "Each incorrect value should be heavily penalized.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.9,
)


# -- Helper --

def _make_extraction_test_case(offer_text: str, expected: dict, actual_output: str) -> LLMTestCase:
    """Create a test case for extraction evaluation.

    In real usage, `actual_output` comes from the agent processing the offer text.
    For now, these tests define the expected interface — the agent will be built to pass them.
    """
    return LLMTestCase(
        input=f"Extract all key financial terms from this MCA offer:\n\n{offer_text}",
        actual_output=actual_output,
        expected_output=json.dumps(expected, indent=2),
    )


# -- Tests --
# These tests use placeholder actual_output for now.
# Once the agent is built, actual_output will come from the agent's response.


class TestExtractionOffer1:
    """Tests for extracting terms from a standard MCA offer."""

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_completeness(self):
        # TODO: Replace with actual agent output
        actual = json.dumps(SAMPLE_OFFER_TEXT_1_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_1, SAMPLE_OFFER_TEXT_1_EXPECTED, actual
        )
        assert_test(test_case, [extraction_completeness])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_accuracy(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_1_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_1, SAMPLE_OFFER_TEXT_1_EXPECTED, actual
        )
        assert_test(test_case, [extraction_accuracy])


class TestExtractionOffer2:
    """Tests for extracting terms from an aggressive MCA offer."""

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_completeness(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_2_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_2, SAMPLE_OFFER_TEXT_2_EXPECTED, actual
        )
        assert_test(test_case, [extraction_completeness])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_accuracy(self):
        actual = json.dumps(SAMPLE_OFFER_TEXT_2_EXPECTED)
        test_case = _make_extraction_test_case(
            SAMPLE_OFFER_TEXT_2, SAMPLE_OFFER_TEXT_2_EXPECTED, actual
        )
        assert_test(test_case, [extraction_accuracy])


# -- Extraction contract: what fields the agent must return --

REQUIRED_EXTRACTION_FIELDS = [
    "advance_amount",
    "factor_rate",
    "total_repayment",
    "term_months",
    "payment_frequency",
    "has_confession_of_judgment",
]


class TestExtractionContract:
    """Ensure the extraction output schema contains all required fields."""

    def test_fixture_1_has_all_required_fields(self):
        for field in REQUIRED_EXTRACTION_FIELDS:
            assert field in SAMPLE_OFFER_TEXT_1_EXPECTED, f"Missing required field: {field}"

    def test_fixture_2_has_all_required_fields(self):
        for field in REQUIRED_EXTRACTION_FIELDS:
            assert field in SAMPLE_OFFER_TEXT_2_EXPECTED, f"Missing required field: {field}"
