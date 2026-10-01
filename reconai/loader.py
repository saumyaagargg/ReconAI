"""Read the bank and ledger CSVs into a common row format.

Every row gets a positional id (bank_0, bank_1, ... / ledger_0, ...).
The dashboard uses the same ids to find the original CSV rows.
"""
import csv
from datetime import datetime


def load_csv(path, date_col, party_col, amount_col, ref_col, id_prefix):
    rows = []
    with open(path, newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            rows.append({
                "id": f"{id_prefix}_{i}",
                "date": datetime.strptime(r[date_col], "%Y-%m-%d").date(),
                "party": r[party_col],
                "amount": float(r[amount_col]),
                "ref": r[ref_col],
                "raw": r,
            })
    return rows


def load_bank(path):
    return load_csv(path, "date", "description", "amount", "reference_no", "bank")


def load_ledger(path):
    return load_csv(path, "txn_date", "narration", "amount", "ref_id", "ledger")