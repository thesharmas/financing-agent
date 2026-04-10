"""Test fixtures: sample financing offers with ground truth values.

Each fixture represents a realistic offer with pre-calculated
correct values. These are the source of truth for all evals.

Ground truth math is documented inline so it can be verified by hand.
Covers three product types: MCA, Receivables Purchase, PO Financing.
"""

from mca_analyzer.calculations import BUSINESS_DAYS_PER_MONTH, CostEscalation, FinancingTerms

# ============================================================================
# MCA FIXTURES
# ============================================================================

# --- FIXTURE 1: Standard MCA — fixed daily, moderate terms, no fees ---
STANDARD_MCA = FinancingTerms(
    advance_amount=50_000,
    repayment_type="fixed",
    product_type="mca",
    factor_rate=1.35,
    term_months=6,
    payment_frequency="daily",
)
STANDARD_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "origination_fee": 0.0,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,  # 50000 × 1.35
    "total_cost": 17_500.0,  # 67500 - 50000
    "num_payments": 126,  # 6 × 21
    "payment_amount": 535.71,  # 67500 / 126
    "effective_apr": 70.0,  # (17500/50000) × (12/6) × 100
    "cents_on_dollar": 0.35,
}

# --- FIXTURE 2: Aggressive MCA — fixed daily, high factor, short term ---
AGGRESSIVE_MCA = FinancingTerms(
    advance_amount=30_000,
    repayment_type="fixed",
    product_type="mca",
    factor_rate=1.49,
    term_months=4,
    payment_frequency="daily",
)
AGGRESSIVE_MCA_EXPECTED = {
    "factor_rate": 1.49,
    "origination_fee": 0.0,
    "effective_advance": 30_000.0,
    "total_repayment": 44_700.0,
    "total_cost": 14_700.0,
    "num_payments": 84,
    "payment_amount": 532.14,
    "effective_apr": 147.0,
    "cents_on_dollar": 0.49,
}

# --- FIXTURE 3: Predatory MCA — 5% fee deducted, very high factor ---
PREDATORY_MCA = FinancingTerms(
    advance_amount=25_000,
    repayment_type="fixed",
    product_type="mca",
    factor_rate=1.55,
    term_months=3,
    payment_frequency="daily",
    origination_fee_pct=0.05,
    fee_deducted_from_advance=True,
)
PREDATORY_MCA_EXPECTED = {
    "factor_rate": 1.55,
    "origination_fee": 1_250.0,
    "effective_advance": 23_750.0,
    "total_repayment": 38_750.0,
    "total_cost": 15_000.0,  # 38750 - 23750
    "num_payments": 63,
    "payment_amount": 615.08,
    "effective_apr": 252.63,
    "cents_on_dollar": 0.6316,
}

# --- FIXTURE 4: Reasonable MCA — weekly, low factor, longer term ---
REASONABLE_MCA = FinancingTerms(
    advance_amount=100_000,
    repayment_type="fixed",
    product_type="mca",
    factor_rate=1.15,
    term_months=12,
    payment_frequency="weekly",
)
REASONABLE_MCA_EXPECTED = {
    "factor_rate": 1.15,
    "origination_fee": 0.0,
    "effective_advance": 100_000.0,
    "total_repayment": 115_000.0,
    "total_cost": 15_000.0,
    "num_payments": 52,
    "payment_amount": 2_211.54,
    "effective_apr": 15.0,
    "cents_on_dollar": 0.15,
}

# --- FIXTURE 5: MCA with flat fee paid separately ---
FEE_MCA = FinancingTerms(
    advance_amount=40_000,
    repayment_type="fixed",
    product_type="mca",
    factor_rate=1.30,
    term_months=6,
    payment_frequency="daily",
    origination_fee=1_200,
    fee_deducted_from_advance=False,
)
FEE_MCA_EXPECTED = {
    "factor_rate": 1.30,
    "origination_fee": 1_200.0,
    "effective_advance": 40_000.0,
    "total_repayment": 52_000.0,
    "total_cost": 13_200.0,
    "num_payments": 126,
    "payment_amount": 412.70,
    "effective_apr": 66.0,
    "cents_on_dollar": 0.33,
}

# --- FIXTURE 6: Percentage-based MCA (holdback) — no stated term ---
PERCENTAGE_MCA = FinancingTerms(
    advance_amount=50_000,
    repayment_type="percentage",
    product_type="mca",
    factor_rate=1.35,
    holdback_pct=0.15,
    estimated_monthly_revenue=80_000,
)
PERCENTAGE_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "origination_fee": 0.0,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "estimated_term_months": 5.625,
    "payment_amount": 571.43,
    "num_payments": 118,
    "effective_apr": 74.67,
    "cents_on_dollar": 0.35,
}

# --- FIXTURE 7: Percentage-based with monthly minimum ---
PERCENTAGE_MIN_MCA = FinancingTerms(
    advance_amount=50_000,
    repayment_type="percentage",
    product_type="mca",
    factor_rate=1.35,
    holdback_pct=0.15,
    estimated_monthly_revenue=80_000,
    monthly_minimum=5_000,
)
PERCENTAGE_MIN_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "origination_fee": 0.0,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "estimated_term_months": 5.625,
    "payment_amount": 571.43,
    "num_payments": 118,
    "effective_apr": 74.67,
    "cents_on_dollar": 0.35,
    "worst_case_term_months": 13.5,
    "worst_case_apr": 31.11,
}

# --- FIXTURE 8: Contract gives total_repayment instead of factor_rate ---
NO_FACTOR_MCA = FinancingTerms(
    advance_amount=50_000,
    repayment_type="fixed",
    product_type="mca",
    total_repayment=67_500,
    term_months=6,
    payment_frequency="daily",
)
NO_FACTOR_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "effective_apr": 70.0,
    "cents_on_dollar": 0.35,
}

# --- FIXTURE 9: Contract gives stated_cost instead of factor_rate ---
STATED_COST_MCA = FinancingTerms(
    advance_amount=50_000,
    repayment_type="fixed",
    product_type="mca",
    stated_cost=17_500,
    term_months=6,
    payment_frequency="daily",
)
STATED_COST_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "effective_apr": 70.0,
    "cents_on_dollar": 0.35,
}

# --- FIXTURE 10: Incomplete MCA — no term, no way to calculate it ---
INCOMPLETE_MCA = FinancingTerms(
    advance_amount=50_000,
    repayment_type="fixed",
    product_type="mca",
    factor_rate=1.35,
)
INCOMPLETE_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "cents_on_dollar": 0.35,
    "effective_apr": None,
    "num_payments": None,
    "payment_amount": None,
    "is_complete": False,
}


# ============================================================================
# REAL CONTRACT FIXTURES
# ============================================================================

# --- FIXTURE 11: Be Amazing / SpringCash — PO Financing ---
# Source: Be_Amazing_Contract - SpringCash.pdf
# $1M PO advance, $80K flat fee, 240-day term, lump sum repayment from Target
BE_AMAZING_PO = FinancingTerms(
    advance_amount=1_000_000,
    repayment_type="lump_sum",
    product_type="po_financing",
    stated_cost=80_000,
    term_days=240,  # 240 calendar days = 8 months
    third_party_payer="Target",
    cost_escalation=CostEscalation(
        rate=0.0016,  # 0.16% per 5-day period
        period_days=5,
        grace_period_days=7,  # 7-day grace after Day 240
        description="0.16% per 5-day period (approx 12% annualized) on unpaid balance after 7-day grace period",
    ),
)
BE_AMAZING_PO_EXPECTED = {
    "product_type": "po_financing",
    # factor: (1000000 + 80000) / 1000000 = 1.08
    "factor_rate": 1.08,
    "origination_fee": 0.0,
    "effective_advance": 1_000_000.0,
    # 1000000 × 1.08
    "total_repayment": 1_080_000.0,
    # 1080000 - 1000000
    "total_cost": 80_000.0,
    # 240 days / 30 = 8 months
    "estimated_term_months": 8.0,
    # Lump sum = 1 payment of the full amount
    "num_payments": 1,
    "payment_amount": 1_080_000.0,
    # (80000 / 1000000) × (12 / 8) × 100 = 12.0
    "effective_apr": 12.0,
    # 80000 / 1000000
    "cents_on_dollar": 0.08,
    # Late fee projections:
    # 30 days late: billable = 30 - 7 = 23 days, periods = 23/5 = 4.6
    # extra cost = 1080000 × 0.0016 × 4.6 = $7,948.80
    "escalated_cost_30_days": 7_948.80,
    # 90 days late: billable = 90 - 7 = 83 days, periods = 83/5 = 16.6
    # extra cost = 1080000 × 0.0016 × 16.6 = $28,684.80
    "escalated_cost_90_days": 28_684.80,
}

# --- FIXTURE 12: Latin Goodness Foods / SpringCash — Receivables Purchase ---
# Source: Latin Goodness Foods - Receivables Agreement - SpringCash.pdf
# $150K advance, $1,849.32 discount (stated cost), ~30-day term
# 50% holdback, hybrid repayment (receivables then daily ACH fallback)
LATIN_GOODNESS_RECEIVABLES = FinancingTerms(
    advance_amount=150_000,
    repayment_type="percentage",
    product_type="receivables_purchase",
    stated_cost=1_849.32,
    term_days=30,  # Estimated 30 days based on Collection Date
    holdback_pct=0.50,  # 50% "Specified Percentage"
    estimated_monthly_revenue=10_123.29 * BUSINESS_DAYS_PER_MONTH,  # daily rev × 21
    fixed_payment=5_061.64,  # Fallback daily ACH if not paid by Collection Date
    third_party_payer="Retailer and Distributor",
    cost_escalation=CostEscalation(
        rate=0.0042,  # 0.42% additional receivables per 10-day period
        period_days=10,
        grace_period_days=0,  # Starts on Collection Date
        description="0.42% additional receivables per 10-day period after Collection Date",
    ),
)
LATIN_GOODNESS_RECEIVABLES_EXPECTED = {
    "product_type": "receivables_purchase",
    # factor: (150000 + 1849.32) / 150000 = 1.01233
    "factor_rate": 1.01233,
    "origination_fee": 0.0,
    "effective_advance": 150_000.0,
    # 150000 + 1849.32
    "total_repayment": 151_849.32,
    # stated cost
    "total_cost": 1_849.32,
    # 30 days / 30 = 1 month
    "estimated_term_months": 1.0,
    # Stated APR in contract is 15% — let's verify:
    # (1849.32 / 150000) × (12 / 1) × 100 = 14.79
    "effective_apr": 14.79,
    # 1849.32 / 150000
    "cents_on_dollar": 0.01233,
    # Late fee projections:
    # 30 days late: 30/10 = 3 periods, 151849.32 × 0.0042 × 3 = $1,913.30
    "escalated_cost_30_days": 1_913.30,
    # 90 days late: 90/10 = 9 periods, 151849.32 × 0.0042 × 9 = $5,739.90
    "escalated_cost_90_days": 5_739.90,
}


# ============================================================================
# Sample offer texts (for extraction evals)
# ============================================================================

SAMPLE_OFFER_TEXT_1 = """
MERCHANT CASH ADVANCE AGREEMENT

Funder: QuickCash Capital LLC
Merchant: ABC Plumbing Services Inc.

ADVANCE DETAILS:
Purchase Price (Advance Amount): $50,000.00
Factor Rate: 1.35
Total Repayment Amount: $67,500.00

REPAYMENT TERMS:
Estimated Term: 6 months
Payment Frequency: Daily ACH
Estimated Daily Payment: $535.71

FEES:
Origination Fee: $0.00

This agreement contains a Confession of Judgment clause. By signing,
the Merchant waives the right to contest collection in court.
"""

SAMPLE_OFFER_TEXT_1_EXPECTED = {
    "advance_amount": 50_000.0,
    "factor_rate": 1.35,
    "total_repayment": 67_500.0,
    "term_months": 6,
    "payment_frequency": "daily",
    "daily_payment": 535.71,
    "origination_fee": 0.0,
    "has_confession_of_judgment": True,
}

SAMPLE_OFFER_TEXT_2 = """
REVENUE-BASED FINANCING AGREEMENT

Provider: Velocity Funding Group
Business: Johnson's Auto Repair LLC

FUNDING DETAILS:
Funded Amount: $30,000.00
Purchase Price: $44,700.00 (Factor Rate: 1.49x)

COLLECTION TERMS:
Repayment Period: Approximately 4 months
Collection Method: ACH Debit - Daily
Expected Daily Remittance: $532.14

ADDITIONAL FEES:
Processing Fee: 3% of Funded Amount ($900.00)

Note: This agreement does NOT contain a Confession of Judgment.
"""

SAMPLE_OFFER_TEXT_2_EXPECTED = {
    "advance_amount": 30_000.0,
    "factor_rate": 1.49,
    "total_repayment": 44_700.0,
    "term_months": 4,
    "payment_frequency": "daily",
    "daily_payment": 532.14,
    "origination_fee": 900.0,
    "has_confession_of_judgment": False,
}

SAMPLE_OFFER_TEXT_3 = """
MERCHANT FINANCING AGREEMENT

Funder: BlueWave Capital Partners
Business: Maria's Catering LLC

ADVANCE DETAILS:
Advance Amount: $50,000.00
Total Cost of Capital: $17,500.00
Total Repayment: $67,500.00

REPAYMENT TERMS:
Holdback Percentage: 15% of daily credit card sales
Estimated Monthly Revenue: $80,000.00
Estimated Repayment Period: 5-6 months
Monthly Minimum Payment: $5,000.00

FEES:
None

This agreement does NOT contain a Confession of Judgment clause.
"""

SAMPLE_OFFER_TEXT_3_EXPECTED = {
    "advance_amount": 50_000.0,
    "stated_cost": 17_500.0,
    "total_repayment": 67_500.0,
    "repayment_type": "percentage",
    "holdback_pct": 0.15,
    "estimated_monthly_revenue": 80_000.0,
    "monthly_minimum": 5_000.0,
    "origination_fee": 0.0,
    "has_confession_of_judgment": False,
}
