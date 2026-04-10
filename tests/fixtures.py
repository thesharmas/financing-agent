"""Test fixtures: sample financing offers with ground truth values.

Each fixture represents a realistic offer with pre-calculated
correct values. These are the source of truth for all evals.

Ground truth math is documented inline so it can be verified by hand.
Covers four product types: MCA, Receivables Purchase, PO Financing, Term Loan.
"""

from financing_mcp.calculations import BUSINESS_DAYS_PER_MONTH, CostEscalation, FinancingTerms

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
    minimum_payment=5_000,
    minimum_payment_period_days=30,
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
    # worst case: monthly_min = 5000, worst_term = 67500 / 5000 = 13.5
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
# MULTI-PRODUCT FIXTURES
# ============================================================================

# --- FIXTURE 11: PO financing — lump sum repayment, late fee escalation ---
LUMP_SUM_PO_FINANCING = FinancingTerms(
    advance_amount=1_000_000,
    repayment_type="lump_sum",
    product_type="po_financing",
    stated_cost=80_000,
    term_days=240,
    third_party_payer="Target",
    cost_escalation=CostEscalation(
        rate=0.0016,
        period_days=5,
        grace_period_days=7,
        description="0.16% per 5-day period (approx 12% annualized) on unpaid balance after 7-day grace period",
    ),
)
LUMP_SUM_PO_FINANCING_EXPECTED = {
    "product_type": "po_financing",
    "factor_rate": 1.08,
    "origination_fee": 0.0,
    "effective_advance": 1_000_000.0,
    "total_repayment": 1_080_000.0,
    "total_cost": 80_000.0,
    "estimated_term_months": 8.0,
    "num_payments": 1,
    "payment_amount": 1_080_000.0,
    "effective_apr": 12.0,
    "cents_on_dollar": 0.08,
    # 30 days late: billable = 23, periods = 4.6, 1080000 × 0.0016 × 4.6
    "escalated_cost_30_days": 7_948.80,
    # 90 days late: billable = 83, periods = 16.6, 1080000 × 0.0016 × 16.6
    "escalated_cost_90_days": 28_684.80,
}

# --- FIXTURE 12: Receivables purchase — percentage holdback, short term ---
PERCENTAGE_RECEIVABLES = FinancingTerms(
    advance_amount=150_000,
    repayment_type="percentage",
    product_type="receivables_purchase",
    stated_cost=1_849.32,
    term_days=30,
    holdback_pct=0.50,
    estimated_monthly_revenue=10_123.29 * BUSINESS_DAYS_PER_MONTH,
    fixed_payment=5_061.64,
    third_party_payer="Retailer and Distributor",
    cost_escalation=CostEscalation(
        rate=0.0042,
        period_days=10,
        grace_period_days=0,
        description="0.42% additional receivables per 10-day period after Collection Date",
    ),
)
PERCENTAGE_RECEIVABLES_EXPECTED = {
    "product_type": "receivables_purchase",
    "factor_rate": 1.01233,
    "origination_fee": 0.0,
    "effective_advance": 150_000.0,
    "total_repayment": 151_849.32,
    "total_cost": 1_849.32,
    "estimated_term_months": 1.0,
    "effective_apr": 14.79,
    "cents_on_dollar": 0.01233,
    "escalated_cost_30_days": 1_913.30,
    "escalated_cost_90_days": 5_739.90,
}

# --- FIXTURE 13: Term loan — fixed weekly, fee deducted from advance ---
FIXED_WEEKLY_TERM_LOAN = FinancingTerms(
    advance_amount=200_000,
    repayment_type="fixed",
    product_type="term_loan",
    stated_cost=42_200.14,
    payment_frequency="weekly",
    fixed_payment=6_210.26,
    origination_fee=5_000,
    fee_deducted_from_advance=True,
    cost_escalation=CostEscalation(
        rate=0.0,
        period_days=1,
        description="$10 late fee (max $50 per 20-day period)",
    ),
)
FIXED_WEEKLY_TERM_LOAN_EXPECTED = {
    "product_type": "term_loan",
    "factor_rate": 1.21100,
    "origination_fee": 5_000.0,
    "effective_advance": 195_000.0,
    "total_repayment": 242_200.14,
    "total_cost": 47_200.14,
    # term from fixed payment: 242200.14 / (6210.26 × 4.33) = 9.006
    "estimated_term_months": 9.006,
    "num_payments": 39,
    "payment_amount": 6_210.26,
    "effective_apr": 32.27,
    "cents_on_dollar": 0.2421,
}

# --- FIXTURE 14: Percentage loan with 60-day minimum, term from milestones ---
PERCENTAGE_60DAY_MINIMUM = FinancingTerms(
    advance_amount=500_000,
    repayment_type="percentage",
    product_type="term_loan",
    stated_cost=65_000,
    holdback_pct=0.14,
    term_days=360,
    minimum_payment=94_167,
    minimum_payment_period_days=60,
)
PERCENTAGE_60DAY_MINIMUM_EXPECTED = {
    "product_type": "term_loan",
    "factor_rate": 1.13,
    "origination_fee": 0.0,
    "effective_advance": 500_000.0,
    "total_repayment": 565_000.0,
    "total_cost": 65_000.0,
    "estimated_term_months": 12.0,
    "effective_apr": 13.0,
    "cents_on_dollar": 0.13,
    # monthly_equiv = 94167 × (30/60) = 47083.50, worst_term = 565000 / 47083.50
    "worst_case_term_months": 12.0,
    "worst_case_apr": 13.0,
}

# --- FIXTURE 15: Percentage loan with stated term and 60-day minimum ---
PERCENTAGE_WITH_STATED_TERM = FinancingTerms(
    advance_amount=249_300,
    repayment_type="percentage",
    product_type="term_loan",
    stated_cost=36_273,
    holdback_pct=0.1925,
    term_months=18,
    minimum_payment=15_865.16,
    minimum_payment_period_days=60,
)
PERCENTAGE_WITH_STATED_TERM_EXPECTED = {
    "product_type": "term_loan",
    "factor_rate": 1.14552,
    "origination_fee": 0.0,
    "effective_advance": 249_300.0,
    "total_repayment": 285_573.0,
    "total_cost": 36_273.0,
    "estimated_term_months": 18.0,
    "effective_apr": 9.70,
    "cents_on_dollar": 0.14552,
    # monthly_equiv = 15865.16 × (30/60) = 7932.58, worst_term = 285573 / 7932.58
    "worst_case_term_months": 36.0,
    "worst_case_apr": 4.85,
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
    # stated_cost not explicitly in contract — Claude may infer it, but not required
    "term_months": 6,
    "payment_frequency": "daily",
    "repayment_type": "fixed",
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
    # stated_cost not explicitly in contract — derivable but not required
    "term_months": 4,
    "payment_frequency": "daily",
    "repayment_type": "fixed",
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
    "minimum_payment": 5_000.0,
    "origination_fee": 0.0,
    "has_confession_of_judgment": False,
}
