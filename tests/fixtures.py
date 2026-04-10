"""Test fixtures: sample MCA offers with ground truth values.

Each fixture represents a realistic MCA offer with pre-calculated
correct values. These are the source of truth for all evals.

Ground truth math is documented inline so it can be verified by hand.
"""

from mca_analyzer.calculations import MCATerms

# ============================================================================
# FIXTURE 1: Standard MCA — fixed daily, moderate terms, no fees
# ============================================================================
STANDARD_MCA = MCATerms(
    advance_amount=50_000,
    repayment_type="fixed",
    factor_rate=1.35,
    term_months=6,
    payment_frequency="daily",
)
STANDARD_MCA_EXPECTED = {
    # Step 0: No fees, effective_advance = advance
    "factor_rate": 1.35,
    "origination_fee": 0.0,
    "effective_advance": 50_000.0,
    # Step 1: 50000 × 1.35
    "total_repayment": 67_500.0,
    # Step 2: 67500 - 50000 + 0
    "total_cost": 17_500.0,
    # Step 3: 6 × 21 = 126 payments; 67500 / 126 = 535.71
    "num_payments": 126,
    "payment_amount": 535.71,
    # Step 4: (17500 / 50000) × (12/6) × 100 = 70.0
    "effective_apr": 70.0,
    # Step 5: 17500 / 50000 = 0.35
    "cents_on_dollar": 0.35,
}

# ============================================================================
# FIXTURE 2: Aggressive MCA — fixed daily, high factor, short term
# ============================================================================
AGGRESSIVE_MCA = MCATerms(
    advance_amount=30_000,
    repayment_type="fixed",
    factor_rate=1.49,
    term_months=4,
    payment_frequency="daily",
)
AGGRESSIVE_MCA_EXPECTED = {
    "factor_rate": 1.49,
    "origination_fee": 0.0,
    "effective_advance": 30_000.0,
    # 30000 × 1.49
    "total_repayment": 44_700.0,
    # 44700 - 30000
    "total_cost": 14_700.0,
    # 4 × 21 = 84; 44700 / 84 = 532.14
    "num_payments": 84,
    "payment_amount": 532.14,
    # (14700 / 30000) × (12/4) × 100 = 147.0
    "effective_apr": 147.0,
    # 14700 / 30000
    "cents_on_dollar": 0.49,
}

# ============================================================================
# FIXTURE 3: Predatory MCA — 5% fee deducted from advance, very high factor
# ============================================================================
PREDATORY_MCA = MCATerms(
    advance_amount=25_000,
    repayment_type="fixed",
    factor_rate=1.55,
    term_months=3,
    payment_frequency="daily",
    origination_fee_pct=0.05,  # 5% = $1,250
    fee_deducted_from_advance=True,
)
PREDATORY_MCA_EXPECTED = {
    "factor_rate": 1.55,
    # fee: 25000 × 0.05 = 1250
    "origination_fee": 1_250.0,
    # effective_advance: 25000 - 1250 = 23750
    "effective_advance": 23_750.0,
    # 25000 × 1.55
    "total_repayment": 38_750.0,
    # fee deducted: 38750 - 23750 = 15000
    "total_cost": 15_000.0,
    # 3 × 21 = 63; 38750 / 63 = 615.08
    "num_payments": 63,
    "payment_amount": 615.08,
    # (15000 / 23750) × (12/3) × 100 = 252.63
    "effective_apr": 252.63,
    # 15000 / 23750
    "cents_on_dollar": 0.6316,
}

# ============================================================================
# FIXTURE 4: Reasonable MCA — weekly, low factor, longer term
# ============================================================================
REASONABLE_MCA = MCATerms(
    advance_amount=100_000,
    repayment_type="fixed",
    factor_rate=1.15,
    term_months=12,
    payment_frequency="weekly",
)
REASONABLE_MCA_EXPECTED = {
    "factor_rate": 1.15,
    "origination_fee": 0.0,
    "effective_advance": 100_000.0,
    # 100000 × 1.15
    "total_repayment": 115_000.0,
    # 115000 - 100000
    "total_cost": 15_000.0,
    # round(12 × 4.33) = 52; 115000 / 52 = 2211.54
    "num_payments": 52,
    "payment_amount": 2_211.54,
    # (15000 / 100000) × (12/12) × 100 = 15.0
    "effective_apr": 15.0,
    # 15000 / 100000
    "cents_on_dollar": 0.15,
}

# ============================================================================
# FIXTURE 5: MCA with flat fee paid separately
# ============================================================================
FEE_MCA = MCATerms(
    advance_amount=40_000,
    repayment_type="fixed",
    factor_rate=1.30,
    term_months=6,
    payment_frequency="daily",
    origination_fee=1_200,  # flat $1200 fee, paid separately
    fee_deducted_from_advance=False,
)
FEE_MCA_EXPECTED = {
    "factor_rate": 1.30,
    "origination_fee": 1_200.0,
    # fee paid separately, effective_advance = advance
    "effective_advance": 40_000.0,
    # 40000 × 1.30
    "total_repayment": 52_000.0,
    # (52000 - 40000) + 1200 = 13200
    "total_cost": 13_200.0,
    # 6 × 21 = 126; 52000 / 126 = 412.70
    "num_payments": 126,
    "payment_amount": 412.70,
    # (13200 / 40000) × (12/6) × 100 = 66.0
    "effective_apr": 66.0,
    # 13200 / 40000
    "cents_on_dollar": 0.33,
}

# ============================================================================
# FIXTURE 6: Percentage-based MCA (holdback) — no stated term
# ============================================================================
PERCENTAGE_MCA = MCATerms(
    advance_amount=50_000,
    repayment_type="percentage",
    factor_rate=1.35,
    holdback_pct=0.15,  # 15% of daily sales
    estimated_monthly_revenue=80_000,
)
PERCENTAGE_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "origination_fee": 0.0,
    "effective_advance": 50_000.0,
    # 50000 × 1.35
    "total_repayment": 67_500.0,
    # 67500 - 50000
    "total_cost": 17_500.0,
    # estimated_term: 67500 / (80000 × 0.15) = 67500 / 12000 = 5.625 months
    "estimated_term_months": 5.625,
    # estimated daily payment: 80000 × 0.15 / 21 = 571.43
    "payment_amount": 571.43,
    # round(5.625 × 21) = 118
    "num_payments": 118,
    # (17500 / 50000) × (12 / 5.625) × 100 = 74.67
    "effective_apr": 74.67,
    # 17500 / 50000
    "cents_on_dollar": 0.35,
}

# ============================================================================
# FIXTURE 7: Percentage-based with monthly minimum
# ============================================================================
PERCENTAGE_MIN_MCA = MCATerms(
    advance_amount=50_000,
    repayment_type="percentage",
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
    # Same estimated term as fixture 6
    "estimated_term_months": 5.625,
    "payment_amount": 571.43,
    "num_payments": 118,
    "effective_apr": 74.67,
    "cents_on_dollar": 0.35,
    # Worst case: 67500 / 5000 = 13.5 months
    "worst_case_term_months": 13.5,
    # Worst case APR: (17500 / 50000) × (12 / 13.5) × 100 = 31.11
    "worst_case_apr": 31.11,
}

# ============================================================================
# FIXTURE 8: Contract gives total_repayment instead of factor_rate
# ============================================================================
NO_FACTOR_MCA = MCATerms(
    advance_amount=50_000,
    repayment_type="fixed",
    total_repayment=67_500,  # No factor_rate stated
    term_months=6,
    payment_frequency="daily",
)
NO_FACTOR_MCA_EXPECTED = {
    # Back-calculated: 67500 / 50000 = 1.35
    "factor_rate": 1.35,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "effective_apr": 70.0,
    "cents_on_dollar": 0.35,
}

# ============================================================================
# FIXTURE 9: Contract gives stated_cost instead of factor_rate
# ============================================================================
STATED_COST_MCA = MCATerms(
    advance_amount=50_000,
    repayment_type="fixed",
    stated_cost=17_500,  # No factor_rate or total_repayment
    term_months=6,
    payment_frequency="daily",
)
STATED_COST_MCA_EXPECTED = {
    # Back-calculated: (50000 + 17500) / 50000 = 1.35
    "factor_rate": 1.35,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    "effective_apr": 70.0,
    "cents_on_dollar": 0.35,
}

# ============================================================================
# FIXTURE 10: Incomplete MCA — no term, no way to calculate it
# ============================================================================
INCOMPLETE_MCA = MCATerms(
    advance_amount=50_000,
    repayment_type="fixed",
    factor_rate=1.35,
    # No term_months, no fixed_payment, no holdback — can't determine term
)
INCOMPLETE_MCA_EXPECTED = {
    "factor_rate": 1.35,
    "effective_advance": 50_000.0,
    "total_repayment": 67_500.0,
    "total_cost": 17_500.0,
    # Can still compute cents on dollar (no term needed)
    "cents_on_dollar": 0.35,
    # Cannot compute these
    "effective_apr": None,
    "num_payments": None,
    "payment_amount": None,
    "is_complete": False,
}


# ============================================================================
# Sample MCA offer texts (for extraction evals)
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
