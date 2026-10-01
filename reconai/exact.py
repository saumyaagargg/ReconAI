"""Pass 1: exact matches. Same reference, same amount, same date."""
from collections import defaultdict


def exact_pass(bank, ledger):
    """Return a list of match dicts. Each ledger row is used at most once."""
    ledger_by_ref = defaultdict(list)
    for l in ledger:
        ledger_by_ref[l["ref"]].append(l)

    used_ledger = set()
    results = []
    for b in bank:
        for l in ledger_by_ref.get(b["ref"], []):
            if l["id"] in used_ledger:
                continue
            if abs(b["amount"] - l["amount"]) < 0.01 and b["date"] == l["date"]:
                used_ledger.add(l["id"])
                results.append({
                    "bank_id": b["id"], "ledger_id": l["id"],
                    "method": "exact", "confidence": 1.0,
                    "note": "exact match on ref, amount, date",
                })
                break
    return results