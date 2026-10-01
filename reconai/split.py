"""Pass 3: split payments. Two bank rows that add up to one ledger row.

Uses amount and date only, so it does not depend on how references are named.
If more than one pair could explain a ledger row, nothing is matched: an
ambiguous case should go to a human, not be guessed.
"""
from itertools import combinations

from .config import SPLIT_AMOUNT_TOLERANCE, SPLIT_CONFIDENCE, SPLIT_DATE_WINDOW_DAYS


def split_pass(bank, ledger,
               amount_tol=SPLIT_AMOUNT_TOLERANCE,
               date_window=SPLIT_DATE_WINDOW_DAYS,
               confidence=SPLIT_CONFIDENCE):
    used_bank = set()
    results = []
    for l in ledger:
        nearby = [b for b in bank
                  if b["id"] not in used_bank
                  and abs((b["date"] - l["date"]).days) <= date_window]
        pairs = [(b1, b2) for b1, b2 in combinations(nearby, 2)
                 if abs(b1["amount"] + b2["amount"] - l["amount"]) < amount_tol]
        if len(pairs) != 1:
            continue  # no candidate, or ambiguous
        b1, b2 = pairs[0]
        used_bank.update([b1["id"], b2["id"]])
        results.append({
            "bank_id": f"{b1['id']}+{b2['id']}", "ledger_id": l["id"],
            "method": "split_payment_rule", "confidence": confidence,
            "note": (f"two bank entries ({b1['amount']}+{b2['amount']}) "
                     f"sum to ledger amount {l['amount']}"),
        })
    return results