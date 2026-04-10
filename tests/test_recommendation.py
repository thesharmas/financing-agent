"""Recommendation quality evals using DeepEval.

Tests whether the agent's plain English output meets the brief's non-negotiables:
- Never use jargon without explaining it
- Always convert to APR
- Flag predatory terms explicitly
- Show tradeoffs, not just verdicts

These tests require ANTHROPIC_API_KEY or OPENAI_API_KEY to be set.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

# -- Metrics --

jargon_free = GEval(
    name="Jargon-Free Communication",
    evaluation_steps=[
        "Check if the 'actual output' uses any financial jargon (factor rate, APR, ACH, "
        "holdback, origination fee, confession of judgment, net terms, advance rate).",
        "If jargon is used, check that it is immediately explained in plain English "
        "in the same sentence or the following sentence.",
        "Every technical term must be accompanied by a clear explanation accessible to "
        "someone with no financial background.",
        "Penalize any jargon used without explanation.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.8,
)

apr_included = GEval(
    name="APR Always Included",
    evaluation_steps=[
        "Check if the 'actual output' includes an effective APR (annual percentage rate).",
        "The APR must be presented as a percentage number, not just mentioned conceptually.",
        "If a factor rate is mentioned, the APR must also be shown for comparison.",
        "A factor rate without a corresponding APR is a failure.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.9,
)

predatory_flagging = GEval(
    name="Predatory Terms Flagged",
    evaluation_steps=[
        "Given the 'input' describes a predatory MCA offer, check that the 'actual output' "
        "explicitly identifies and flags the predatory terms.",
        "The output must not soften or downplay predatory terms.",
        "Red flags should be called out clearly with words like 'warning', 'red flag', "
        "'predatory', 'dangerous', or 'high risk'.",
        "The output must explain WHY each flagged term is bad for the business.",
        "Compare against the 'expected output' to ensure all key red flags are mentioned.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.8,
)

shows_tradeoffs = GEval(
    name="Shows Tradeoffs",
    evaluation_steps=[
        "Check if the 'actual output' presents tradeoffs rather than just a verdict.",
        "The output should explain what the borrower gains AND what they give up.",
        "Look for balanced language: 'on one hand / on the other', 'the advantage is / "
        "but the downside is', 'you get X but it costs Y'.",
        "A simple 'this is bad, don't take it' without explaining tradeoffs is a failure.",
        "Even for predatory offers, the output should acknowledge why the borrower might "
        "be considering it (e.g., speed of funding, no credit check).",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.7,
)

explanation_accuracy = GEval(
    name="Explanation Accuracy",
    evaluation_steps=[
        "Compare the financial figures in 'actual output' against 'expected output'.",
        "All dollar amounts, percentages, and payment figures must be correct.",
        "The explanation of what the numbers mean must be factually accurate.",
        "Any mathematical error or misrepresentation is a critical failure.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.9,
)


# -- Test Inputs --

PREDATORY_OFFER_INPUT = (
    "I received an MCA offer. Here are the terms:\n"
    "- Advance amount: $25,000\n"
    "- Factor rate: 1.55\n"
    "- Term: 3 months\n"
    "- Daily ACH payments\n"
    "- 5% origination fee\n"
    "- Contains a confession of judgment clause\n\n"
    "Is this a good deal?"
)

PREDATORY_OFFER_EXPECTED_FLAGS = (
    "This offer has multiple serious red flags:\n"
    "- Factor rate of 1.55 is very high (effective APR ~240%)\n"
    "- 3 month term is extremely short\n"
    "- 5% origination fee ($1,250) is excessive\n"
    "- Daily ACH payments create cash flow strain\n"
    "- Confession of judgment clause waives your legal rights\n"
    "- Total cost of capital: $15,000 on a $25,000 advance (60 cents per dollar borrowed)\n"
)

STANDARD_OFFER_INPUT = (
    "I got this MCA offer:\n"
    "- Advance amount: $50,000\n"
    "- Factor rate: 1.35\n"
    "- Term: 6 months\n"
    "- Daily payments\n"
    "- No origination fee\n\n"
    "Can you explain what this means and whether it's reasonable?"
)

STANDARD_OFFER_EXPECTED = (
    "MCA offer analysis:\n"
    "- Total repayment: $67,500\n"
    "- Total cost of capital: $17,500\n"
    "- Effective APR: approximately 70%\n"
    "- Daily payment: approximately $536\n"
    "- Cost: 35 cents per dollar borrowed\n"
    "- Factor rate of 1.35 is in the moderate range\n"
)


# -- Tests --


class TestRecommendationQuality:
    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_jargon_free_explanation(self):
        test_case = LLMTestCase(
            input=STANDARD_OFFER_INPUT,
            actual_output="PLACEHOLDER — replace with agent output",
        )
        assert_test(test_case, [jargon_free])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_apr_always_included(self):
        test_case = LLMTestCase(
            input=STANDARD_OFFER_INPUT,
            actual_output="PLACEHOLDER — replace with agent output",
        )
        assert_test(test_case, [apr_included])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_predatory_terms_flagged(self):
        test_case = LLMTestCase(
            input=PREDATORY_OFFER_INPUT,
            actual_output="PLACEHOLDER — replace with agent output",
            expected_output=PREDATORY_OFFER_EXPECTED_FLAGS,
        )
        assert_test(test_case, [predatory_flagging])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_shows_tradeoffs(self):
        test_case = LLMTestCase(
            input=STANDARD_OFFER_INPUT,
            actual_output="PLACEHOLDER — replace with agent output",
        )
        assert_test(test_case, [shows_tradeoffs])

    @pytest.mark.skipif(True, reason="Agent not yet built — placeholder test")
    def test_explanation_accuracy(self):
        test_case = LLMTestCase(
            input=STANDARD_OFFER_INPUT,
            actual_output="PLACEHOLDER — replace with agent output",
            expected_output=STANDARD_OFFER_EXPECTED,
        )
        assert_test(test_case, [explanation_accuracy])
