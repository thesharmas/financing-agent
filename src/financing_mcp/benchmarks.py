"""Market benchmark data for SMB financing products.

Provides typical ranges for each product type so the agent can tell
users where their offer falls relative to the market.

These are curated ranges based on industry data. In production,
you'd update these periodically from a data source.
"""

from dataclasses import dataclass


@dataclass
class BenchmarkRange:
    """A typical range for a metric, with labels for where values fall."""

    low: float
    typical_low: float
    typical_high: float
    high: float
    unit: str  # "percent", "factor", "cents"

    def classify(self, value: float) -> str:
        """Classify a value as below_market, competitive, typical, above_market, or high."""
        if value <= self.low:
            return "below_market"
        if value <= self.typical_low:
            return "competitive"
        if value <= self.typical_high:
            return "typical"
        if value <= self.high:
            return "above_market"
        return "high"


@dataclass
class ProductBenchmarks:
    """Benchmark ranges for a specific product type."""

    product_type: str
    description: str
    factor_rate: BenchmarkRange | None
    effective_apr: BenchmarkRange
    cents_on_dollar: BenchmarkRange


# ---------------------------------------------------------------------------
# Benchmark data by product type
# ---------------------------------------------------------------------------

BENCHMARKS = {
    "mca": ProductBenchmarks(
        product_type="mca",
        description="Merchant Cash Advance — factor rate applied to advance, repaid via daily/weekly ACH or percentage of sales",
        factor_rate=BenchmarkRange(
            low=1.10, typical_low=1.20, typical_high=1.40, high=1.50, unit="factor"
        ),
        effective_apr=BenchmarkRange(
            low=15.0, typical_low=40.0, typical_high=100.0, high=150.0, unit="percent"
        ),
        cents_on_dollar=BenchmarkRange(
            low=0.10, typical_low=0.20, typical_high=0.40, high=0.50, unit="cents"
        ),
    ),
    "receivables_purchase": ProductBenchmarks(
        product_type="receivables_purchase",
        description="Receivables Purchase — sale of future receivables at a discount, repaid via percentage of sales or invoice collection",
        factor_rate=BenchmarkRange(
            low=1.01, typical_low=1.02, typical_high=1.10, high=1.20, unit="factor"
        ),
        effective_apr=BenchmarkRange(
            low=5.0, typical_low=10.0, typical_high=30.0, high=50.0, unit="percent"
        ),
        cents_on_dollar=BenchmarkRange(
            low=0.01, typical_low=0.02, typical_high=0.10, high=0.20, unit="cents"
        ),
    ),
    "po_financing": ProductBenchmarks(
        product_type="po_financing",
        description="Purchase Order Financing — advance against a confirmed purchase order, repaid when the buyer pays",
        factor_rate=BenchmarkRange(
            low=1.02, typical_low=1.05, typical_high=1.10, high=1.15, unit="factor"
        ),
        effective_apr=BenchmarkRange(
            low=5.0, typical_low=8.0, typical_high=15.0, high=25.0, unit="percent"
        ),
        cents_on_dollar=BenchmarkRange(
            low=0.02, typical_low=0.05, typical_high=0.10, high=0.15, unit="cents"
        ),
    ),
    "term_loan": ProductBenchmarks(
        product_type="term_loan",
        description="Term Loan — fixed interest, scheduled payments over a defined term",
        factor_rate=None,  # Term loans use interest rates, not factor rates
        effective_apr=BenchmarkRange(
            low=5.0, typical_low=10.0, typical_high=30.0, high=50.0, unit="percent"
        ),
        cents_on_dollar=BenchmarkRange(
            low=0.05, typical_low=0.10, typical_high=0.25, high=0.40, unit="cents"
        ),
    ),
}


def get_benchmarks(product_type: str) -> dict:
    """Get benchmark data for a product type, with classification helpers.

    Returns a dict suitable for JSON serialization and agent consumption.
    """
    benchmarks = BENCHMARKS.get(product_type)
    if benchmarks is None:
        return {
            "error": f"Unknown product type: {product_type}",
            "known_types": list(BENCHMARKS.keys()),
        }

    result = {
        "product_type": benchmarks.product_type,
        "description": benchmarks.description,
        "effective_apr": {
            "below_market": f"< {benchmarks.effective_apr.low}%",
            "competitive": f"{benchmarks.effective_apr.low}% - {benchmarks.effective_apr.typical_low}%",
            "typical": f"{benchmarks.effective_apr.typical_low}% - {benchmarks.effective_apr.typical_high}%",
            "above_market": f"{benchmarks.effective_apr.typical_high}% - {benchmarks.effective_apr.high}%",
            "high": f"> {benchmarks.effective_apr.high}%",
        },
        "cents_on_dollar": {
            "below_market": f"< {benchmarks.cents_on_dollar.low}",
            "competitive": f"{benchmarks.cents_on_dollar.low} - {benchmarks.cents_on_dollar.typical_low}",
            "typical": f"{benchmarks.cents_on_dollar.typical_low} - {benchmarks.cents_on_dollar.typical_high}",
            "above_market": f"{benchmarks.cents_on_dollar.typical_high} - {benchmarks.cents_on_dollar.high}",
            "high": f"> {benchmarks.cents_on_dollar.high}",
        },
    }

    if benchmarks.factor_rate is not None:
        result["factor_rate"] = {
            "below_market": f"< {benchmarks.factor_rate.low}",
            "competitive": f"{benchmarks.factor_rate.low} - {benchmarks.factor_rate.typical_low}",
            "typical": f"{benchmarks.factor_rate.typical_low} - {benchmarks.factor_rate.typical_high}",
            "above_market": f"{benchmarks.factor_rate.typical_high} - {benchmarks.factor_rate.high}",
            "high": f"> {benchmarks.factor_rate.high}",
        }

    return result


def classify_offer(product_type: str, effective_apr: float | None = None,
                   factor_rate: float | None = None,
                   cents_on_dollar: float | None = None) -> dict:
    """Classify where an offer falls relative to market benchmarks.

    Returns a dict with classification for each provided metric.
    """
    benchmarks = BENCHMARKS.get(product_type)
    if benchmarks is None:
        return {"error": f"Unknown product type: {product_type}"}

    result = {"product_type": product_type}

    if effective_apr is not None:
        result["apr_classification"] = benchmarks.effective_apr.classify(effective_apr)
        result["apr_value"] = effective_apr

    if factor_rate is not None and benchmarks.factor_rate is not None:
        result["factor_rate_classification"] = benchmarks.factor_rate.classify(factor_rate)
        result["factor_rate_value"] = factor_rate

    if cents_on_dollar is not None:
        result["cost_classification"] = benchmarks.cents_on_dollar.classify(cents_on_dollar)
        result["cents_on_dollar_value"] = cents_on_dollar

    return result
