from datetime import date


def row(id, ref, amount, day=10, party="ACME LTD"):
    """Build a transaction row like the loader produces."""
    return {"id": id, "ref": ref, "amount": float(amount),
            "date": date(2026, 8, day), "party": party, "raw": {}}