"""
Generates 3 synthetic datasets simulating the same ~70 underlying transactions
viewed from 3 different sources (bank, internal ledger, invoices), with
deliberately injected mismatches so the reconciliation engine has real work
to do, and a ground-truth file so we can report HONEST accuracy numbers.

Run: python3 generate_data.py
Outputs: bank_statement.csv, internal_ledger.csv, invoice_records.csv, ground_truth.csv
"""

import random
import csv
from datetime import date, timedelta
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

N = 70  # base number of underlying transactions
START_DATE = date(2026, 7, 1)

def rand_date(base, max_offset_days=0):
    if max_offset_days == 0:
        return base
    offset = random.randint(-max_offset_days, max_offset_days)
    return base + timedelta(days=offset)

# ---- Step 1: generate ground-truth transactions ----
transactions = []
for i in range(N):
    txn_id = f"TXN{1000+i}"
    party = fake.company()
    amount = round(random.uniform(500, 85000), 2)
    txn_date = START_DATE + timedelta(days=random.randint(0, 45))
    transactions.append({
        "txn_id": txn_id,
        "party": party,
        "amount": amount,
        "date": txn_date,
    })

# ---- Step 2: assign each transaction a scenario type ----
# exact        -> appears identically in all 3 sources
# fuzzy_date    -> date off by 1-2 days in bank vs ledger
# fuzzy_amount  -> rounding difference (bank fee / paise rounding)
# fuzzy_ref     -> reference number typo'd or reformatted
# duplicate     -> bank shows the txn TWICE (should NOT double count)
# split_payment -> one invoice = two separate bank entries
# missing_bank  -> exists in ledger/invoice but bank entry missing (e.g. pending)
# missing_ledger-> exists in bank but never recorded in ledger (unrecorded txn)

scenario_pool = (
    ["exact"] * 11 +
    ["fuzzy_date"] * 12 +
    ["fuzzy_amount"] * 10 +
    ["fuzzy_ref"] * 10 +
    ["duplicate"] * 7 +
    ["split_payment"] * 7 +
    ["missing_bank"] * 5 +
    ["missing_ledger"] * 5 +
    ["close_amount_ambiguous"] * 1 +
    ["date_lag_ambiguous"] * 1 +
    ["multi_candidate_ambiguous"] * 1
)
random.shuffle(scenario_pool)
while len(scenario_pool) < N:
    scenario_pool.append("exact")
scenario_pool = scenario_pool[:N]

bank_rows, ledger_rows, invoice_rows, ground_truth = [], [], [], []

def ref_from_txn(txn_id):
    return txn_id

def typo_ref(ref):
    # swap two adjacent chars or drop a char, simple typo simulation
    ref = list(ref)
    if len(ref) > 4:
        i = random.randint(1, len(ref) - 2)
        ref[i], ref[i+1] = ref[i+1], ref[i]
    return "".join(ref)

for txn, scenario in zip(transactions, scenario_pool):
    tid, party, amt, dt = txn["txn_id"], txn["party"], txn["amount"], txn["date"]
    ref = ref_from_txn(tid)

    if scenario == "exact":
        bank_rows.append([dt, party, amt, ref])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, ref, ref, "exact", "clean match, all fields identical"])

    elif scenario == "fuzzy_date":
        bank_dt = rand_date(dt, 2)
        bank_rows.append([bank_dt, party, amt, ref])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, ref, ref, "fuzzy_date", f"bank date offset by {(bank_dt-dt).days} days (settlement lag)"])

    elif scenario == "fuzzy_amount":
        bank_amt = round(amt - random.choice([0.5, 1.0, 1.5, 2.0]), 2)
        bank_rows.append([dt, party, bank_amt, ref])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, ref, ref, "fuzzy_amount", f"bank amount off by {round(amt-bank_amt,2)} (rounding/fee)"])

    elif scenario == "fuzzy_ref":
        bad_ref = typo_ref(ref)
        bank_rows.append([dt, party, amt, bad_ref])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, bad_ref, ref, ref, "fuzzy_ref", f"bank ref '{bad_ref}' vs ledger ref '{ref}' (data entry typo)"])

    elif scenario == "duplicate":
        bank_rows.append([dt, party, amt, ref])
        bank_rows.append([dt, party, amt, ref])  # duplicate entry
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, ref, ref, "duplicate", "bank shows this txn twice - must not double-count"])

    elif scenario == "split_payment":
        amt1 = round(amt * 0.6, 2)
        amt2 = round(amt - amt1, 2)
        bank_rows.append([dt, party, amt1, ref + "-A"])
        bank_rows.append([rand_date(dt, 1), party, amt2, ref + "-B"])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, f"{ref}-A + {ref}-B", ref, ref, "split_payment", "invoice paid via two separate bank txns"])

    elif scenario == "missing_bank":
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, "MISSING", ref, ref, "missing_bank", "invoiced and recorded, payment not yet received"])

    elif scenario == "missing_ledger":
        bank_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, "MISSING", "MISSING", "missing_ledger", "bank credit never recorded internally (needs investigation)"])

    elif scenario == "close_amount_ambiguous":
        # Amount diff exceeds the fuzzy tolerance (>Rs.3) but stays well under
        # the Rs.500 LLM-candidate ceiling. Ref and date are identical, so a
        # human (or the AI reviewer) can plausibly judge it - the rules
        # genuinely can't, since fuzzy match requires amt_ok too.
        delta = random.choice([15, 18, 22, 27, -16, -19, -24])
        bank_amt = round(amt + delta, 2)
        bank_rows.append([dt, party, bank_amt, ref])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, ref, ref, "close_amount_ambiguous",
                              f"bank amount off by Rs.{abs(delta)} (beyond auto-tolerance) - likely a bank fee or manual adjustment, needs human judgment"])

    elif scenario == "date_lag_ambiguous":
        # Date diff exceeds the fuzzy window (>2 days) but amount and ref are
        # exact. A real settlement delay, but the rule engine can't
        # distinguish "delayed but legitimate" from "unrelated txn".
        lag = random.choice([4, 5, 6])
        bank_dt = dt + timedelta(days=lag)
        bank_rows.append([bank_dt, party, amt, ref])
        ledger_rows.append([dt, party, amt, ref])
        invoice_rows.append([dt, party, amt, ref])
        ground_truth.append([tid, ref, ref, ref, "date_lag_ambiguous",
                              f"bank entry lags ledger by {lag} days (beyond the 2-day auto window) - plausible settlement delay, not auto-confirmable"])

    elif scenario == "multi_candidate_ambiguous":
        # ONE bank entry sits within Rs.500 of TWO different ledger entries
        # (a genuine payer and a decoy with a similar amount). Neither
        # candidate clears fuzzy match's amount tolerance, so both land in
        # the LLM-candidate pool against the same bank row - the "one bank
        # transaction, two plausible ledger candidates" case.
        bank_rows.append([dt, party, amt, ref])
        decoy_party = fake.company()
        cand_a_amt = round(amt + random.choice([20, 30, 40]), 2)
        cand_b_amt = round(amt - random.choice([25, 35, 45]), 2)
        ledger_rows.append([dt, party, cand_a_amt, ref + "-CAND1"])
        ledger_rows.append([rand_date(dt, 1), decoy_party, cand_b_amt, ref + "-CAND2"])
        ground_truth.append([tid, ref, f"{ref}-CAND1 (correct) vs {ref}-CAND2 (decoy)", "MISSING",
                              "multi_candidate_ambiguous",
                              f"true match is {ref}-CAND1 (same party '{party}'); {ref}-CAND2 is a same-amount-range decoy from a different party '{decoy_party}' - tests whether party context, not just amount, drives the resolution"])

# ---- Write CSVs ----
def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

write_csv("bank_statement.csv", ["date", "description", "amount", "reference_no"], bank_rows)
write_csv("internal_ledger.csv", ["txn_date", "narration", "amount", "ref_id"], ledger_rows)
write_csv("invoice_records.csv", ["invoice_date", "party_name", "amount", "invoice_no"], invoice_rows)
write_csv("ground_truth.csv", ["txn_id", "bank_ref", "ledger_ref", "invoice_ref", "scenario", "explanation"], ground_truth)

print(f"Generated {len(bank_rows)} bank rows, {len(ledger_rows)} ledger rows, {len(invoice_rows)} invoice rows")
print(f"Ground truth: {len(ground_truth)} underlying transactions across {len(set(scenario_pool))} scenario types")
print("Scenario breakdown:", {s: scenario_pool.count(s) for s in set(scenario_pool)})