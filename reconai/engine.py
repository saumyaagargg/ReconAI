"""Runs the passes in order and writes the report and review queue.

Order: exact -> fuzzy -> split -> AI review. Each pass only sees rows that
the earlier passes did not match.
"""
import json
import os

from .ai_review import ask_gemini, find_candidates, to_review_entries
from .config import DEFAULT_GEMINI_MODEL
from .exact import exact_pass
from .fuzzy import fuzzy_pass
from .loader import load_bank, load_ledger
from .split import split_pass


def reconcile(bank, ledger, api_key=None, model=DEFAULT_GEMINI_MODEL, post=None):
    """Pure function: rows in, (report, review_queue) out. No file access."""
    matched_bank, matched_ledger = set(), set()
    results = []

    def remaining():
        return ([b for b in bank if b["id"] not in matched_bank],
                [l for l in ledger if l["id"] not in matched_ledger])

    for matcher in (exact_pass, fuzzy_pass, split_pass):
        rem_bank, rem_ledger = remaining()
        for r in matcher(rem_bank, rem_ledger):
            results.append(r)
            matched_bank.update(r["bank_id"].split("+"))
            matched_ledger.add(r["ledger_id"])

    # AI review for whatever is left
    rem_bank, rem_ledger = remaining()
    review_queue = []
    flagged_bank, flagged_ledger = set(), set()
    extra = {"post": post} if post else {}
    for group in find_candidates(rem_bank, rem_ledger).values():
        b, candidates = group["bank"], group["ledger_candidates"]
        verdict = ask_gemini(b, candidates, api_key, model, **extra)
        review_queue.extend(to_review_entries(b, candidates, verdict))
        flagged_bank.add(b["id"])
        flagged_ledger.update(l["id"] for l in candidates)

    exceptions = []
    for b in bank:
        if b["id"] in matched_bank:
            continue
        reason = ("needs_llm_review (amount within the review window of an unmatched ledger row)"
                  if b["id"] in flagged_bank
                  else "no plausible ledger counterpart found (possible unrecorded transaction)")
        exceptions.append({"side": "bank", "id": b["id"], "ref": b["ref"],
                           "amount": b["amount"], "date": str(b["date"]), "reason": reason})
    for l in ledger:
        if l["id"] in matched_ledger:
            continue
        reason = ("needs_llm_review (amount within the review window of an unmatched bank row)"
                  if l["id"] in flagged_ledger
                  else "no bank entry received yet (possible pending payment)")
        exceptions.append({"side": "ledger", "id": l["id"], "ref": l["ref"],
                           "amount": l["amount"], "date": str(l["date"]), "reason": reason})

    total = len(bank)
    report = {
        "total_bank_rows": total,
        "matched_bank_rows": len(matched_bank),
        "match_rate_pct": round(100 * len(matched_bank) / total, 1) if total else 0.0,
        "matches": results,
        "exceptions": exceptions,
    }
    return report, review_queue


def run(data_dir="data", out_dir="output", api_key=None, model=DEFAULT_GEMINI_MODEL):
    """Load CSVs, reconcile, and write the two JSON files the dashboard reads."""
    bank = load_bank(os.path.join(data_dir, "bank_statement.csv"))
    ledger = load_ledger(os.path.join(data_dir, "internal_ledger.csv"))
    report, review_queue = reconcile(bank, ledger, api_key=api_key, model=model)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "reconciliation_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)
    with open(os.path.join(out_dir, "review_queue.json"), "w") as f:
        json.dump(review_queue, f, indent=2, default=str)
    return report, review_queue