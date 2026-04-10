"""Test fixtures: sample MCA offers with ground truth values.

Each fixture represents a realistic MCA offer with pre-calculated
correct values. These are the source of truth for all evals.
"""

from mca_analyzer.calculations import MCATerms

# --- FIXTURE 1: Standard MCA offer (moderate terms) ---
STANDARD_MCA = MCATerms(
    advance_amount=50_000,
    factor_rate=1.35,
    term_months=6,
    payment_frequency="daily",
)
STANDARD_MCA_EXPECTED = {
    "total_repayment": 67_500.0,  # 50000 * 1.35
    "total_cost": 17_500.0,  # 67500 - 50000
    "effective_apr": 70.0,  # (17500 / 50000) * (12 / 6) * 100
    "num_payments": 126,  # 6 months * 21 business days
    "payment_amount": 535.71,  # 67500 / 126 (rounded to 2 decimal)
    "cents_on_dollar": 0.35,  # 17500 / 50000
}

# --- FIXTURE 2: Aggressive MCA (high factor, short term) ---
AGGRESSIVE_MCA = MCATerms(
    advance_amount=30_000,
    factor_rate=1.49,
    term_months=4,
    payment_frequency="daily",
)
AGGRESSIVE_MCA_EXPECTED = {
    "total_repayment": 44_700.0,  # 30000 * 1.49
    "total_cost": 14_700.0,  # 44700 - 30000
    "effective_apr": 147.0,  # (14700 / 30000) * (12 / 4) * 100
    "num_payments": 84,  # 4 * 21
    "payment_amount": 532.14,  # 44700 / 84
    "cents_on_dollar": 0.49,
}

# --- FIXTURE 3: Predatory MCA (very high factor, fees, short term) ---
PREDATORY_MCA = MCATerms(
    advance_amount=25_000,
    factor_rate=1.55,
    term_months=3,
    payment_frequency="daily",
    origination_fee_pct=0.05,  # 5% origination fee
)
PREDATORY_MCA_EXPECTED = {
    "total_repayment": 38_750.0,  # 25000 * 1.55
    "total_cost": 15_000.0,  # (38750 - 25000) + (25000 * 0.05)
    "effective_apr": 240.0,  # (15000 / 25000) * (12 / 3) * 100
    "num_payments": 63,  # 3 * 21
    "payment_amount": 615.08,  # 38750 / 63
    "cents_on_dollar": 0.60,  # 15000 / 25000
}

# --- FIXTURE 4: Reasonable MCA (low factor, weekly, longer term) ---
REASONABLE_MCA = MCATerms(
    advance_amount=100_000,
    factor_rate=1.15,
    term_months=12,
    payment_frequency="weekly",
)
REASONABLE_MCA_EXPECTED = {
    "total_repayment": 115_000.0,  # 100000 * 1.15
    "total_cost": 15_000.0,  # 115000 - 100000
    "effective_apr": 15.0,  # (15000 / 100000) * (12 / 12) * 100
    "num_payments": 52,  # 12 * 4.33, rounded
    "payment_amount": 2_211.54,  # 115000 / 52
    "cents_on_dollar": 0.15,
}

# --- FIXTURE 5: MCA with flat origination fee ---
FEE_MCA = MCATerms(
    advance_amount=40_000,
    factor_rate=1.30,
    term_months=6,
    payment_frequency="daily",
    origination_fee=1_200,  # flat $1200 fee
)
FEE_MCA_EXPECTED = {
    "total_repayment": 52_000.0,  # 40000 * 1.30
    "total_cost": 13_200.0,  # (52000 - 40000) + 1200
    "effective_apr": 66.0,  # (13200 / 40000) * (12 / 6) * 100
    "num_payments": 126,  # 6 * 21
    "payment_amount": 412.70,  # 52000 / 126
    "cents_on_dollar": 0.33,  # 13200 / 40000
}


# --- Sample MCA offer text (for extraction evals) ---
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
