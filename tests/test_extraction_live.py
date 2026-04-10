"""Live extraction eval — configurable extractor and judge models.

This test validates the full pipeline:
1. Send contract text to an LLM (extractor) → get extracted terms as JSON
2. Feed the output to a different LLM (judge) → score extraction quality

Configuration via environment variables:
    EXTRACTOR_PROVIDER=openai|anthropic  (default: anthropic)
    EXTRACTOR_MODEL=model-name           (default: claude-sonnet-4-20250514)
    JUDGE_PROVIDER=openai|anthropic      (default: openai)
    JUDGE_MODEL=model-name               (default: gpt-4o)

Or via pytest CLI:
    pytest --extractor-provider=openai --extractor-model=gpt-4o
           --judge-provider=anthropic --judge-model=claude-sonnet-4-20250514

Requires API keys for whichever providers you use.
"""

import json
import os

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from .fixtures import (
    SAMPLE_OFFER_TEXT_1,
    SAMPLE_OFFER_TEXT_1_EXPECTED,
    SAMPLE_OFFER_TEXT_2,
    SAMPLE_OFFER_TEXT_2_EXPECTED,
    SAMPLE_OFFER_TEXT_3,
    SAMPLE_OFFER_TEXT_3_EXPECTED,
)


# ---------------------------------------------------------------------------
# Pytest CLI options
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption("--extractor-provider", default=None)
    parser.addoption("--extractor-model", default=None)
    parser.addoption("--judge-provider", default=None)
    parser.addoption("--judge-model", default=None)


def _get_config(request, name, env_key, default):
    """Get config from pytest CLI, then env var, then default."""
    cli = request.config.getoption(f"--{name}", default=None) if request else None
    if cli:
        return cli
    return os.environ.get(env_key, default)


# ---------------------------------------------------------------------------
# Model wrappers
# ---------------------------------------------------------------------------


class AnthropicModel(DeepEvalBaseLLM):
    """Wrapper for using Anthropic Claude as a DeepEval judge."""

    def __init__(self, model_name="claude-sonnet-4-20250514"):
        import anthropic
        self._model_name = model_name
        self.client = anthropic.Anthropic()

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self._model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return self._model_name


class OpenAIModel(DeepEvalBaseLLM):
    """Wrapper for using OpenAI as a DeepEval judge."""

    def __init__(self, model_name="gpt-4o"):
        import openai
        self._model_name = model_name
        self.client = openai.OpenAI()

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return self._model_name


def _make_model(provider: str, model_name: str) -> DeepEvalBaseLLM:
    """Create a model wrapper from provider + model name."""
    if provider == "anthropic":
        return AnthropicModel(model_name)
    elif provider == "openai":
        return OpenAIModel(model_name)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'anthropic' or 'openai'.")


# ---------------------------------------------------------------------------
# Extraction function — calls the extractor LLM
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
You are a financial document analyst. Extract all key financial terms from the
following financing offer document. Return ONLY a JSON object with these fields.

IMPORTANT: Include ALL fields below. If a field is not present or is zero,
explicitly include it with value 0 or null. Do not omit fields.

Fields:
- advance_amount: numeric, the principal/funded amount
- factor_rate: numeric, the factor rate if stated (null if not stated)
- total_repayment: numeric, total amount to be repaid
- stated_cost: numeric, the financing cost/fee/discount amount if stated separately (null if not stated)
- term_months: numeric, the term in months (null if not stated)
- payment_frequency: string, "daily" or "weekly" (null if not applicable)
- daily_payment: numeric, the per-day payment amount if stated (null if not stated)
- weekly_payment: numeric, the per-week payment amount if stated (null if not stated)
- repayment_type: string, "fixed", "percentage", or "lump_sum"
- holdback_pct: numeric (0-1), percentage of sales taken as repayment (null if not applicable)
- estimated_monthly_revenue: numeric, projected monthly revenue if stated (null if not stated)
- minimum_payment: numeric, minimum payment amount if stated (null if not stated)
- origination_fee: numeric, any origination/processing fee (0 if explicitly no fees)
- has_confession_of_judgment: boolean, whether a COJ clause is present or absent

Return ONLY the JSON object, no markdown formatting, no other text.

DOCUMENT:
{document}
"""


def extract_terms(offer_text: str, provider: str, model: str) -> str:
    """Send contract text to an LLM and get extracted terms as JSON string."""
    prompt = EXTRACTION_PROMPT.format(document=offer_text)

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    elif provider == "openai":
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Fixtures for model configuration
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor_config(request):
    """Returns (provider, model) for the extractor LLM."""
    provider = _get_config(request, "extractor-provider", "EXTRACTOR_PROVIDER", "anthropic")
    model_defaults = {"anthropic": "claude-sonnet-4-20250514", "openai": "gpt-4o"}
    model = _get_config(request, "extractor-model", "EXTRACTOR_MODEL", model_defaults.get(provider, "gpt-4o"))
    return provider, model


@pytest.fixture
def judge_model(request):
    """Returns a DeepEvalBaseLLM instance for the judge."""
    provider = _get_config(request, "judge-provider", "JUDGE_PROVIDER", "openai")
    model_defaults = {"anthropic": "claude-sonnet-4-20250514", "openai": "gpt-4o"}
    model = _get_config(request, "judge-model", "JUDGE_MODEL", model_defaults.get(provider, "gpt-4o"))
    return _make_model(provider, model)


# ---------------------------------------------------------------------------
# Metric factories — create metrics with the configured judge
# ---------------------------------------------------------------------------


def make_completeness_metric(judge):
    return GEval(
        name="Extraction Completeness",
        evaluation_steps=[
            "Compare the 'actual output' JSON against the 'expected output' JSON.",
            "Check that every field present in the expected output is also present "
            "in the actual output with a non-null value.",
            "A field present in the expected output but missing or null in the actual output "
            "should be penalized, UNLESS the expected value is 0 and the field is absent "
            "(treating absence as zero is acceptable for fee fields).",
            "Extra fields in the actual output (not in expected) should NOT be penalized.",
            "Fields present in actual output with null that aren't in expected output are fine.",
            "Integer vs float type differences do NOT matter.",
        ],
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=0.8,
        model=judge,
    )


def make_accuracy_metric(judge):
    return GEval(
        name="Extraction Accuracy",
        evaluation_steps=[
            "Compare each numeric value in 'actual output' against 'expected output'.",
            "Values must match exactly or within 1% relative tolerance.",
            "Integer vs float differences do NOT matter — 50000 and 50000.0 are the same value.",
            "null vs 0 are acceptable equivalents for fee fields.",
            "String values (like payment_frequency) must match semantically.",
            "Boolean values (like has_confession_of_judgment) must match exactly.",
            "Each genuinely incorrect value should be heavily penalized.",
            "Extra fields in the actual output that are NOT in the expected output "
            "should NOT be penalized — extracting additional correct information is good.",
        ],
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=0.9,
        model=judge,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLiveExtraction:
    """Live tests — extractor and judge models are configurable."""

    def test_offer1_mca_with_coj(self, extractor_config, judge_model):
        """Standard MCA with confession of judgment clause."""
        provider, model = extractor_config
        actual = extract_terms(SAMPLE_OFFER_TEXT_1, provider, model)
        print(f"\n--- {provider}/{model} extracted (offer 1) ---\n{actual}\n")
        print(f"--- Judge: {judge_model.get_model_name()} ---\n")

        test_case = LLMTestCase(
            input=f"Extract terms from:\n{SAMPLE_OFFER_TEXT_1}",
            actual_output=actual,
            expected_output=json.dumps(SAMPLE_OFFER_TEXT_1_EXPECTED, indent=2),
        )
        metrics = [make_completeness_metric(judge_model), make_accuracy_metric(judge_model)]
        assert_test(test_case, metrics)

    def test_offer2_revenue_based(self, extractor_config, judge_model):
        """Revenue-based financing with processing fee."""
        provider, model = extractor_config
        actual = extract_terms(SAMPLE_OFFER_TEXT_2, provider, model)
        print(f"\n--- {provider}/{model} extracted (offer 2) ---\n{actual}\n")
        print(f"--- Judge: {judge_model.get_model_name()} ---\n")

        test_case = LLMTestCase(
            input=f"Extract terms from:\n{SAMPLE_OFFER_TEXT_2}",
            actual_output=actual,
            expected_output=json.dumps(SAMPLE_OFFER_TEXT_2_EXPECTED, indent=2),
        )
        metrics = [make_completeness_metric(judge_model), make_accuracy_metric(judge_model)]
        assert_test(test_case, metrics)

    def test_offer3_percentage_holdback(self, extractor_config, judge_model):
        """Percentage-based with holdback and monthly minimum."""
        provider, model = extractor_config
        actual = extract_terms(SAMPLE_OFFER_TEXT_3, provider, model)
        print(f"\n--- {provider}/{model} extracted (offer 3) ---\n{actual}\n")
        print(f"--- Judge: {judge_model.get_model_name()} ---\n")

        test_case = LLMTestCase(
            input=f"Extract terms from:\n{SAMPLE_OFFER_TEXT_3}",
            actual_output=actual,
            expected_output=json.dumps(SAMPLE_OFFER_TEXT_3_EXPECTED, indent=2),
        )
        metrics = [make_completeness_metric(judge_model), make_accuracy_metric(judge_model)]
        assert_test(test_case, metrics)
