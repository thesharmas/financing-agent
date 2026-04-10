"""Recommendation quality evals using DeepEval.

Tests whether the agent's plain English output meets quality standards
across all product types.

HOW THESE EVALS WORK:
=====================

Unlike test_math.py (deterministic: does 1.35 × 50000 = 67500?) or
test_extraction.py (structured: did you find all the fields?), these
tests evaluate FREE-FORM TEXT quality. There's no single right answer.

"Explain this MCA offer" has infinite correct responses. We can't assert
on exact wording. Instead, we define PROPERTIES the response must have:
- Jargon is explained (jargon_free)
- APR is shown as a number (apr_included)
- Bad terms are called out (predatory_flagging)
- Pros AND cons are discussed (shows_tradeoffs)
- Numbers are correct (explanation_accuracy)
- Product type is explained correctly (product_explanation)

Each property becomes a GEval metric with its own rubric and threshold.
The judge LLM reads the agent's response and scores each property
independently. A test can apply multiple metrics to the same response.

EVALUATION_PARAMS EXPLAINED:
============================

Each metric declares which parts of the test case the judge sees:

- ACTUAL_OUTPUT only:
    Judge just reads the response. Used for style/quality checks.
    Example: "is jargon explained?" — doesn't need to know the input.

- ACTUAL_OUTPUT + EXPECTED_OUTPUT:
    Judge compares response against ground truth. Used for accuracy.
    Example: "are the numbers correct?" — needs the right answers.

- INPUT + ACTUAL_OUTPUT + EXPECTED_OUTPUT:
    Judge sees everything. Used when context matters.
    Example: "given this predatory offer, did the agent flag it?"

THRESHOLD EXPLAINED:
====================

GEval scores are 0.0 to 1.0. The threshold is the minimum to pass.

- 0.9 = strict. Must be nearly perfect. Used for factual accuracy.
- 0.8 = solid. Some minor issues OK. Used for completeness checks.
- 0.7 = lenient. Allows stylistic variation. Used for subjective qualities.

These tests require OPENAI_API_KEY to be set (for the judge LLM).
"""

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


# ============================================================================
# METRICS — each checks one quality property of the agent's response
# ============================================================================

jargon_free = GEval(
    name="Jargon-Free Communication",
    evaluation_steps=[
        "Check if the 'actual output' uses any financial jargon (factor rate, APR, ACH, "
        "holdback, origination fee, confession of judgment, net terms, advance rate, "
        "receivables, purchase order financing, discount amount, specified percentage).",
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
        "The APR must be presented as a specific percentage number, not just mentioned "
        "conceptually (e.g., '70% APR' not just 'the APR is high').",
        "If a factor rate or discount amount is mentioned, the APR must also be shown.",
        "A cost metric without APR is a failure — APR enables comparison across products.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.9,
)

predatory_flagging = GEval(
    name="Predatory Terms Flagged",
    evaluation_steps=[
        "Given the 'input' describes a financing offer, check that the 'actual output' "
        "explicitly identifies and flags any predatory or concerning terms.",
        "The output must not soften or downplay predatory terms.",
        "Red flags should be called out clearly with words like 'warning', 'red flag', "
        "'predatory', 'dangerous', 'high risk', or 'concerning'.",
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
        "Look for balanced language: pros and cons, advantages and disadvantages, "
        "what you get versus what it costs.",
        "A simple 'this is bad, don't take it' without explaining tradeoffs is a failure.",
        "Even for predatory offers, the output should acknowledge why the borrower might "
        "be considering it (e.g., speed of funding, no credit check, flexibility).",
        "For reasonable offers, still note downsides — no financing is free.",
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
        "Approximate values are acceptable if clearly marked (e.g., '~70% APR' or "
        "'approximately $536 per day').",
    ],
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.9,
)

product_explanation = GEval(
    name="Product Type Explanation",
    evaluation_steps=[
        "Check if the 'actual output' correctly explains what type of financing product "
        "this is and how it works.",
        "For MCA: should explain factor rate concept, daily/weekly payments, how holdback works.",
        "For PO Financing: should explain it's tied to a specific purchase order, "
        "repayment comes from the retailer, and what happens if the retailer doesn't pay.",
        "For Receivables Purchase: should explain it's a sale of future receivables, "
        "how the holdback percentage works, and what the collection date means.",
        "The explanation must be accurate for the specific product type.",
        "Misidentifying the product type is a critical failure.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
    ],
    threshold=0.8,
)

late_fee_explanation = GEval(
    name="Late Fee / Escalation Explanation",
    evaluation_steps=[
        "If the financing offer includes late fees or cost escalation, check that the "
        "'actual output' explains them clearly.",
        "The explanation should include: when late fees start, how much they are, "
        "and what the projected additional cost would be.",
        "If there is a grace period, it should be mentioned.",
        "If there are no late fees, the output should note this as a positive.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.7,
)


# ============================================================================
# TEST INPUTS — scenarios the agent must handle
# ============================================================================

# --- Scenario 1: Predatory MCA ---
PREDATORY_MCA_INPUT = (
    "I received an MCA offer. Here are the terms:\n"
    "- Advance amount: $25,000\n"
    "- Factor rate: 1.55\n"
    "- Term: 3 months\n"
    "- Daily ACH payments\n"
    "- 5% origination fee (deducted from advance)\n"
    "- Contains a confession of judgment clause\n\n"
    "Is this a good deal?"
)

PREDATORY_MCA_EXPECTED_FLAGS = (
    "This offer has multiple serious red flags:\n"
    "- Factor rate of 1.55 is very high (effective APR ~253%)\n"
    "- 3 month term is extremely short\n"
    "- 5% origination fee ($1,250) deducted from advance — you only receive $23,750\n"
    "- Daily ACH payments create cash flow strain\n"
    "- Confession of judgment clause waives your legal rights\n"
    "- Total cost of capital: $15,000 on $23,750 received (63 cents per dollar)\n"
)

# --- Scenario 2: Standard MCA ---
STANDARD_MCA_INPUT = (
    "I got this MCA offer:\n"
    "- Advance amount: $50,000\n"
    "- Factor rate: 1.35\n"
    "- Term: 6 months\n"
    "- Daily payments\n"
    "- No origination fee\n\n"
    "Can you explain what this means and whether it's reasonable?"
)

STANDARD_MCA_EXPECTED = (
    "MCA offer analysis:\n"
    "- Total repayment: $67,500\n"
    "- Total cost of capital: $17,500\n"
    "- Effective APR: approximately 70%\n"
    "- Daily payment: approximately $536\n"
    "- Cost: 35 cents per dollar borrowed\n"
    "- Factor rate of 1.35 is in the moderate range\n"
)

# --- Scenario 3: PO Financing (Be Amazing style) ---
PO_FINANCING_INPUT = (
    "We got a purchase order financing offer:\n"
    "- We have a $1,000,000 purchase order from Target\n"
    "- The funder will advance $1,000,000 to pay our suppliers\n"
    "- We owe them $1,080,000 total, due in 240 days\n"
    "- The $80,000 difference is a flat financing fee\n"
    "- Target pays the funder directly\n"
    "- If Target doesn't pay by day 240, there's a 7-day grace period,\n"
    "  then late fees of 0.16% per 5-day period on the unpaid balance\n\n"
    "How does this compare to an MCA?"
)

PO_FINANCING_EXPECTED = (
    "PO Financing analysis:\n"
    "- Advance: $1,000,000\n"
    "- Total repayment: $1,080,000\n"
    "- Financing fee: $80,000\n"
    "- Effective APR: approximately 12%\n"
    "- Cost: 8 cents per dollar\n"
    "- This is significantly cheaper than a typical MCA (which averages 40-100% APR)\n"
    "- Risk: if Target doesn't pay, late fees add ~12% annualized on unpaid balance\n"
    "- Late fees start after 7-day grace period\n"
)

# --- Scenario 4: Receivables Purchase (Latin Goodness style) ---
RECEIVABLES_INPUT = (
    "I signed a receivables purchase agreement:\n"
    "- They're buying $151,849.32 of my future receivables\n"
    "- They paid me $150,000 for them\n"
    "- The discount amount is $1,849.32\n"
    "- They take 50% of my daily sales until paid\n"
    "- My daily revenue is about $10,123\n"
    "- Collection date is in 30 days\n"
    "- If not paid by then, 0.42% additional receivables every 10 days\n\n"
    "Is this a good deal? The contract says it's not a loan."
)

RECEIVABLES_EXPECTED = (
    "Receivables purchase analysis:\n"
    "- Amount received: $150,000\n"
    "- Total owed: $151,849.32\n"
    "- Cost: $1,849.32 (about 1.2 cents per dollar)\n"
    "- Effective APR: approximately 15%\n"
    "- 50% holdback means about $5,062/day from your sales\n"
    "- Estimated 30-day term\n"
    "- Whether it's legally called a 'loan' or a 'sale', the financial cost is the same\n"
    "- Late fees: 0.42% per 10 days adds up — 30 days late costs ~$1,913 extra\n"
)


# ============================================================================
# TESTS
# ============================================================================
# All skipped until the agent is built.
# To activate: replace "PLACEHOLDER" with real agent output, remove skipif.


class TestMCARecommendation:
    """Tests for MCA offer analysis quality."""

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_jargon_free(self):
        test_case = LLMTestCase(
            input=STANDARD_MCA_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [jargon_free])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_apr_included(self):
        test_case = LLMTestCase(
            input=STANDARD_MCA_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [apr_included])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_predatory_flagged(self):
        test_case = LLMTestCase(
            input=PREDATORY_MCA_INPUT,
            actual_output="PLACEHOLDER",
            expected_output=PREDATORY_MCA_EXPECTED_FLAGS,
        )
        assert_test(test_case, [predatory_flagging])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_shows_tradeoffs(self):
        test_case = LLMTestCase(
            input=STANDARD_MCA_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [shows_tradeoffs])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_explanation_accuracy(self):
        test_case = LLMTestCase(
            input=STANDARD_MCA_INPUT,
            actual_output="PLACEHOLDER",
            expected_output=STANDARD_MCA_EXPECTED,
        )
        assert_test(test_case, [explanation_accuracy])


class TestPOFinancingRecommendation:
    """Tests for PO financing analysis quality."""

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_product_explanation(self):
        test_case = LLMTestCase(
            input=PO_FINANCING_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [product_explanation])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_late_fee_explanation(self):
        test_case = LLMTestCase(
            input=PO_FINANCING_INPUT,
            actual_output="PLACEHOLDER",
            expected_output=PO_FINANCING_EXPECTED,
        )
        assert_test(test_case, [late_fee_explanation])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_explanation_accuracy(self):
        test_case = LLMTestCase(
            input=PO_FINANCING_INPUT,
            actual_output="PLACEHOLDER",
            expected_output=PO_FINANCING_EXPECTED,
        )
        assert_test(test_case, [explanation_accuracy])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_apr_included(self):
        test_case = LLMTestCase(
            input=PO_FINANCING_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [apr_included])


class TestReceivablesRecommendation:
    """Tests for receivables purchase analysis quality."""

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_product_explanation(self):
        test_case = LLMTestCase(
            input=RECEIVABLES_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [product_explanation])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_late_fee_explanation(self):
        test_case = LLMTestCase(
            input=RECEIVABLES_INPUT,
            actual_output="PLACEHOLDER",
            expected_output=RECEIVABLES_EXPECTED,
        )
        assert_test(test_case, [late_fee_explanation])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_explanation_accuracy(self):
        test_case = LLMTestCase(
            input=RECEIVABLES_INPUT,
            actual_output="PLACEHOLDER",
            expected_output=RECEIVABLES_EXPECTED,
        )
        assert_test(test_case, [explanation_accuracy])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_jargon_free(self):
        """Receivables language is especially jargon-heavy — 'discount amount',
        'specified percentage', 'additional receivables percentage' all need explaining."""
        test_case = LLMTestCase(
            input=RECEIVABLES_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [jargon_free])

    @pytest.mark.skipif(True, reason="Agent not yet built")
    def test_loan_vs_sale_framing(self):
        """The user asked 'the contract says it's not a loan' — the agent must address this."""
        loan_framing = GEval(
            name="Loan vs Sale Framing",
            evaluation_steps=[
                "The user's input mentions the contract claims to be 'not a loan'.",
                "Check that the 'actual output' addresses this framing directly.",
                "The output should explain that regardless of legal classification, "
                "the financial cost to the business is the same.",
                "The output should NOT simply accept the 'not a loan' framing at face value.",
                "The output should explain what the distinction means (or doesn't mean) "
                "for the business owner in practical terms.",
            ],
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            threshold=0.8,
        )
        test_case = LLMTestCase(
            input=RECEIVABLES_INPUT,
            actual_output="PLACEHOLDER",
        )
        assert_test(test_case, [loan_framing])
