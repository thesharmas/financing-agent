"""Background eval worker — double extraction comparison.

For every run, sends the same PDF to a second LLM (OpenAI by default)
with the same extraction prompt. Compares the two extractions field by
field. If they agree, high confidence the extraction is correct. If
they disagree, flags which fields differ.

This catches the main risk: garbage in from bad extraction → garbage
out from correct math. The MCP math will always be "right" for the
inputs it receives — the question is whether the inputs were right.

Run manually:
    python -m financing_proxy.eval_worker

Run on a schedule:
    python -m financing_proxy.eval_worker --once

Run continuously:
    python -m financing_proxy.eval_worker --poll --interval 60
"""

import argparse
import json
import time

import openai

from financing_proxy.firestore import get_pending_runs, save_eval_scores

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
- repayment_type: string, "fixed", "percentage", or "lump_sum"
- holdback_pct: numeric (0-1), percentage of sales taken as repayment (null if not applicable)
- origination_fee: numeric, any origination/processing fee (0 if explicitly no fees)
- fee_deducted_from_advance: boolean, whether fee was deducted from the advance
- has_confession_of_judgment: boolean, whether a COJ clause is present or absent
- product_type: string, "mca", "term_loan", "po_financing", or "receivables_purchase"

Return ONLY the JSON object, no markdown formatting, no other text.

DOCUMENT:
{document}
"""

# Fields to compare between the two extractions
COMPARE_FIELDS = [
    "advance_amount",
    "factor_rate",
    "total_repayment",
    "stated_cost",
    "term_months",
    "repayment_type",
    "holdback_pct",
    "origination_fee",
    "fee_deducted_from_advance",
    "has_confession_of_judgment",
    "product_type",
]

# Numeric tolerance for comparison (1%)
NUMERIC_TOLERANCE = 0.01


def extract_with_openai(pdf_base64: str) -> dict | None:
    """Send the PDF to OpenAI for independent extraction.

    OpenAI doesn't support inline PDF documents like Anthropic.
    Upload the file first, then reference it in the message.
    """
    import base64
    import tempfile
    import os

    try:
        client = openai.OpenAI()

        # Write base64 PDF to a temp file for upload
        pdf_bytes = base64.b64decode(pdf_base64)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name

        try:
            # Upload to OpenAI Files API
            with open(tmp_path, "rb") as f:
                file_obj = client.files.create(file=f, purpose="assistants")

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "file": {"file_id": file_obj.id},
                        },
                        {
                            "type": "text",
                            "text": EXTRACTION_PROMPT.format(document="[see attached PDF]"),
                        },
                    ],
                }],
            )
        finally:
            os.unlink(tmp_path)
            # Clean up uploaded file
            try:
                client.files.delete(file_obj.id)
            except Exception:
                pass

        text = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        return {"_error": str(e)}


def get_primary_extraction(mcp_tool_inputs: list[dict]) -> dict | None:
    """Extract the primary (Claude) extraction from MCP tool inputs.

    The agent sends extracted terms to analyze_offer — those inputs
    are what Claude extracted from the PDF.
    """
    for entry in mcp_tool_inputs:
        if entry.get("tool") == "analyze_offer":
            return entry.get("input", {})
    return None


def compare_values(val_a, val_b, field_name: str) -> dict:
    """Compare two extracted values for a single field."""
    # Both null/None
    if val_a is None and val_b is None:
        return {"match": True, "a": val_a, "b": val_b}

    # One null, other not
    if val_a is None or val_b is None:
        return {"match": False, "a": val_a, "b": val_b, "reason": "one is null"}

    # Booleans
    if isinstance(val_a, bool) or isinstance(val_b, bool):
        return {"match": val_a == val_b, "a": val_a, "b": val_b}

    # Numeric comparison with tolerance
    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        if val_a == 0 and val_b == 0:
            return {"match": True, "a": val_a, "b": val_b}
        if val_a == 0 or val_b == 0:
            return {"match": False, "a": val_a, "b": val_b, "reason": "one is zero"}
        ratio = abs(val_a - val_b) / max(abs(val_a), abs(val_b))
        return {
            "match": ratio <= NUMERIC_TOLERANCE,
            "a": val_a,
            "b": val_b,
            "difference_pct": round(ratio * 100, 2),
        }

    # String comparison (case-insensitive)
    if isinstance(val_a, str) and isinstance(val_b, str):
        return {"match": val_a.lower() == val_b.lower(), "a": val_a, "b": val_b}

    # Fallback
    return {"match": str(val_a) == str(val_b), "a": val_a, "b": val_b}


def compare_extractions(primary: dict, secondary: dict) -> dict:
    """Compare two extractions field by field. Returns eval result."""
    field_results = {}
    matches = 0
    total = 0

    for field in COMPARE_FIELDS:
        val_a = primary.get(field)
        val_b = secondary.get(field)
        result = compare_values(val_a, val_b, field)
        field_results[field] = result
        if result["match"]:
            matches += 1
        total += 1

    agreement_rate = matches / total if total > 0 else 0
    disagreements = [f for f, r in field_results.items() if not r["match"]]

    return {
        "agreement_rate": round(agreement_rate, 3),
        "passed": agreement_rate >= 0.9,
        "total_fields": total,
        "matching_fields": matches,
        "disagreements": disagreements,
        "field_details": field_results,
    }


def evaluate_run(run: dict) -> dict:
    """Evaluate a single run via double extraction."""
    pdf_base64 = run.get("pdf_base64")
    if not pdf_base64:
        return {
            "passed": False,
            "error": "No PDF data in run log — cannot evaluate",
        }

    mcp_tool_inputs = run.get("mcp_tool_inputs", [])
    primary = get_primary_extraction(mcp_tool_inputs)
    if not primary:
        return {
            "passed": False,
            "error": "No analyze_offer tool input found — cannot get primary extraction",
        }

    # Get secondary extraction from OpenAI
    secondary = extract_with_openai(pdf_base64)
    if secondary is None or "_error" in secondary:
        error = secondary.get("_error", "unknown") if secondary else "null response"
        return {
            "passed": False,
            "error": f"Secondary extraction failed: {error}",
        }

    # Compare
    comparison = compare_extractions(primary, secondary)
    comparison["primary_model"] = "claude (managed agent)"
    comparison["secondary_model"] = "gpt-4o"

    return comparison


def evaluate_run_by_id(run_id: str) -> dict:
    """Evaluate a specific run by ID. Called from the proxy after each request."""
    from financing_proxy.firestore import save_eval_scores

    from google.cloud import firestore as fs
    from financing_proxy.config import GCP_PROJECT

    db = fs.Client(project=GCP_PROJECT)
    doc = db.collection("financing_runs").document(run_id).get()
    if not doc.exists:
        scores = {"passed": False, "error": f"Run {run_id} not found"}
        save_eval_scores(run_id, scores)
        return scores

    run = {"doc_id": doc.id, **doc.to_dict()}
    scores = evaluate_run(run)
    save_eval_scores(run_id, scores)

    status = "PASS" if scores.get("passed") else "FAIL"
    print(f"Eval [{status}] {run_id[:12]}... {run.get('pdf_title', 'unknown')}")
    if scores.get("disagreements"):
        print(f"  Disagreements: {scores['disagreements']}")

    return scores


def process_pending_runs():
    """Fetch and evaluate all pending runs."""
    runs = get_pending_runs(limit=50)
    if not runs:
        print("No pending runs")
        return 0

    print(f"Evaluating {len(runs)} runs...")
    for run in runs:
        try:
            scores = evaluate_run(run)
            save_eval_scores(run["doc_id"], scores)

            if "error" in scores:
                print(f"  {run['doc_id'][:12]}... [ERROR] {scores['error']}")
            else:
                status = "PASS" if scores["passed"] else "FAIL"
                rate = scores["agreement_rate"]
                disagreements = scores.get("disagreements", [])
                print(f"  {run['doc_id'][:12]}... [{status}] {rate:.0%} agreement — {run.get('pdf_title', 'unknown')}")
                if disagreements:
                    print(f"    Disagreements: {disagreements}")
        except Exception as e:
            print(f"  {run['doc_id'][:12]}... [ERROR] {e}")

    return len(runs)


def main():
    parser = argparse.ArgumentParser(description="Eval worker — double extraction comparison")
    parser.add_argument("--once", action="store_true", help="Process pending runs and exit")
    parser.add_argument("--poll", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    args = parser.parse_args()

    if args.once or not args.poll:
        process_pending_runs()
    else:
        print(f"Polling every {args.interval}s")
        while True:
            process_pending_runs()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
