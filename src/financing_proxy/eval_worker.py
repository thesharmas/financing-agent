"""Background eval worker for production runs.

Picks up logged runs from Firestore, evaluates them with cheap checks
(every run) and expensive LLM-judge checks (sampled), then writes
scores back.

Run manually:
    python -m financing_proxy.eval_worker

Run on a schedule (Cloud Scheduler → Cloud Run Job):
    python -m financing_proxy.eval_worker --once

Run continuously:
    python -m financing_proxy.eval_worker --poll --interval 60
"""

import argparse
import random
import re
import time

from financing_proxy.firestore import get_pending_runs, save_eval_scores

# What percentage of runs get expensive LLM evals (0.0 to 1.0)
EXPENSIVE_EVAL_SAMPLE_RATE = 0.1  # 10%

EXPECTED_TOOLS = {"analyze_offer", "detect_predatory_terms", "get_market_benchmarks"}


# ---------------------------------------------------------------------------
# Cheap checks — regex/string-based, run on every request
# ---------------------------------------------------------------------------


def check_apr_present(output: str) -> dict:
    """Check if the output contains a specific APR percentage number.

    Looks for patterns like "9.7% APR", "APR of 70%", "effective APR: 15%".
    """
    patterns = [
        r"\d+\.?\d*\s*%\s*APR",
        r"APR\s*(?:of|is|:)\s*(?:approximately\s*)?~?\s*\d+\.?\d*\s*%",
        r"effective\s+APR\s*(?:of|is|:)?\s*(?:approximately\s*)?~?\s*\*?\*?\d+\.?\d*\s*%",
    ]
    for pattern in patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return {"score": 1.0, "passed": True, "reason": "APR percentage found in output"}

    return {"score": 0.0, "passed": False, "reason": "No specific APR percentage found in output"}


def check_predatory_consistent(output: str, tool_calls: list[dict]) -> dict:
    """Check if predatory detection results are reflected in the output.

    If detect_predatory_terms was called, the output should mention
    red flags, warnings, or predatory terms.
    """
    called_predatory = any(t.get("name") == "detect_predatory_terms" for t in tool_calls)
    if not called_predatory:
        return {"score": 0.5, "passed": True, "reason": "Predatory check not called — skipped"}

    flag_words = ["red flag", "warning", "predatory", "danger", "concerning", "high risk", "caution"]
    found = [w for w in flag_words if w.lower() in output.lower()]

    if found:
        return {"score": 1.0, "passed": True, "reason": f"Predatory terms mentioned: {found}"}
    return {"score": 0.0, "passed": False, "reason": "Predatory check was called but no flags mentioned in output"}


def check_tool_calls_complete(tool_calls: list[dict]) -> dict:
    """Check if the agent called all expected MCP tools."""
    called = {t.get("name") for t in tool_calls}
    missing = EXPECTED_TOOLS - called

    if not missing:
        return {"score": 1.0, "passed": True, "reason": "All expected tools called"}

    return {
        "score": len(called & EXPECTED_TOOLS) / len(EXPECTED_TOOLS),
        "passed": False,
        "reason": f"Missing tool calls: {missing}",
    }


def run_cheap_checks(run: dict) -> dict:
    """Run all cheap checks on a run. Returns a dict of scores."""
    output = run.get("output", "")
    tool_calls = run.get("tool_calls", [])

    return {
        "apr_present": check_apr_present(output),
        "predatory_consistent": check_predatory_consistent(output, tool_calls),
        "tool_calls_complete": check_tool_calls_complete(tool_calls),
    }


# ---------------------------------------------------------------------------
# Expensive checks — LLM-as-judge, run on a sample
# ---------------------------------------------------------------------------


def run_expensive_checks(run: dict) -> dict:
    """Run DeepEval GEval checks on a run. Returns a dict of scores."""
    try:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError:
        return {"_skipped": "deepeval not installed"}

    output = run.get("output", "")

    scores = {}

    # Jargon-free check
    jargon_metric = GEval(
        name="Jargon-Free",
        evaluation_steps=[
            "Check if financial jargon (factor rate, APR, ACH, holdback, "
            "origination fee, confession of judgment) is explained in plain English.",
            "Every technical term must be accompanied by a clear explanation.",
            "Penalize unexplained jargon.",
        ],
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.8,
    )
    test_case = LLMTestCase(input="", actual_output=output)
    jargon_metric.measure(test_case)
    scores["jargon_free"] = {
        "score": jargon_metric.score,
        "passed": jargon_metric.score >= 0.8,
        "reason": jargon_metric.reason,
    }

    # Shows tradeoffs check
    tradeoffs_metric = GEval(
        name="Shows Tradeoffs",
        evaluation_steps=[
            "Check if the output presents tradeoffs — pros AND cons.",
            "A simple verdict without explaining what the borrower gains "
            "and gives up is a failure.",
        ],
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.7,
    )
    test_case = LLMTestCase(input="", actual_output=output)
    tradeoffs_metric.measure(test_case)
    scores["shows_tradeoffs"] = {
        "score": tradeoffs_metric.score,
        "passed": tradeoffs_metric.score >= 0.7,
        "reason": tradeoffs_metric.reason,
    }

    return scores


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------


def evaluate_run(run: dict) -> dict:
    """Evaluate a single run with cheap + optionally expensive checks."""
    scores = run_cheap_checks(run)

    # Sample expensive evals
    if random.random() < EXPENSIVE_EVAL_SAMPLE_RATE:
        expensive = run_expensive_checks(run)
        scores.update(expensive)
        scores["_expensive_eval"] = True
    else:
        scores["_expensive_eval"] = False

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

            passed = all(
                s.get("passed", True)
                for k, s in scores.items()
                if isinstance(s, dict) and "passed" in s
            )
            status = "PASS" if passed else "FAIL"
            print(f"  {run['doc_id'][:12]}... [{status}] {run.get('pdf_title', 'unknown')}")
        except Exception as e:
            print(f"  {run['doc_id'][:12]}... [ERROR] {e}")

    return len(runs)


def main():
    parser = argparse.ArgumentParser(description="Eval worker for production runs")
    parser.add_argument("--once", action="store_true", help="Process pending runs and exit")
    parser.add_argument("--poll", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--sample-rate", type=float, default=0.1,
                        help="Fraction of runs to get expensive LLM evals (0-1)")
    args = parser.parse_args()

    global EXPENSIVE_EVAL_SAMPLE_RATE
    EXPENSIVE_EVAL_SAMPLE_RATE = args.sample_rate

    if args.once or not args.poll:
        process_pending_runs()
    else:
        print(f"Polling every {args.interval}s (expensive eval sample rate: {args.sample_rate})")
        while True:
            process_pending_runs()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
