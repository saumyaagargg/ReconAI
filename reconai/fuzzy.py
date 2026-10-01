"""Pass 2: fuzzy matches. Close amount, close date, similar reference.

Greedy: bank rows are handled in file order, and each one takes the
best-scoring ledger row still free. This is simple and predictable, but it is
not a globally optimal assignment (see README limitations).
"""
from rapidfuzz import fuzz

from .config import AMOUNT_TOLERANCE, DATE_WINDOW_DAYS, REF_FUZZY_THRESHOLD


def fuzzy_pass(bank, ledger,
               amount_tol=AMOUNT_TOLERANCE,
               date_window=DATE_WINDOW_DAYS,
               ref_threshold=REF_FUZZY_THRESHOLD):
    used_ledger = set()
    results = []
    for b in bank:
        best, best_score = None, 0
        for l in ledger:
            if l["id"] in used_ledger:
                continue
            if abs(b["amount"] - l["amount"]) > amount_tol:
                continue
            if abs((b["date"] - l["date"]).days) > date_window:
                continue
            score = fuzz.ratio(b["ref"], l["ref"])
            if score >= ref_threshold and score > best_score:
                best, best_score = l, score
        if best:
            used_ledger.add(best["id"])
            results.append({
                "bank_id": b["id"], "ledger_id": best["id"],
                "method": "fuzzy",
                # confidence here is just the reference similarity
                "confidence": round(best_score / 100, 2),
                "note": (f"amount diff={round(abs(b['amount'] - best['amount']), 2)}, "
                         f"date diff={abs((b['date'] - best['date']).days)}d, "
                         f"ref_sim={best_score}"),
            })
    return results