"""
Multi-source reconciliation engine.

Pass 1: Exact match (deterministic - same amount + same date + same ref)
Pass 2: Fuzzy match (amount tolerance + date window + fuzzy ref string match)
Pass 3: LLM-assisted match for whatever's still ambiguous after rules
         (this is the "right tool, right place" layer - only invoked
          where deterministic rules genuinely can't decide)

Outputs a match report: match rate, categorized exceptions, and WHY
each exception failed - no cherry-picking, every unmatched row is
accounted for.
"""

import csv
import json
from datetime import datetime
from rapidfuzz import fuzz

AMOUNT_TOLERANCE = 3.0   # rupees
DATE_WINDOW_DAYS = 2
REF_FUZZY_THRESHOLD = 75  # rapidfuzz similarity score out of 100

def load_csv(path, date_col, party_col, amount_col, ref_col):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "date": datetime.strptime(r[date_col], "%Y-%m-%d").date(),
                "party": r[party_col],
                "amount": float(r[amount_col]),
                "ref": r[ref_col],
                "raw": r,
            })
    return rows

bank = load_csv("bank_statement.csv", "date", "description", "amount", "reference_no")
ledger = load_csv("internal_ledger.csv", "txn_date", "narration", "amount", "ref_id")

for i, r in enumerate(bank):
    r["id"] = f"bank_{i}"
for i, r in enumerate(ledger):
    r["id"] = f"ledger_{i}"

matched_bank_ids = set()
matched_ledger_ids = set()
results = []  # list of dicts: {bank_id, ledger_id(s), confidence, method, note}

# ---------- PASS 1: exact match ----------
for b in bank:
    if b["id"] in matched_bank_ids:
        continue
    for l in ledger:
        if l["id"] in matched_ledger_ids:
            continue
        if b["ref"] == l["ref"] and abs(b["amount"] - l["amount"]) < 0.01 and b["date"] == l["date"]:
            matched_bank_ids.add(b["id"])
            matched_ledger_ids.add(l["id"])
            results.append({"bank_id": b["id"], "ledger_id": l["id"], "method": "exact",
                             "confidence": 1.0, "note": "exact match on ref, amount, date"})
            break

# ---------- PASS 2: fuzzy match ----------
for b in bank:
    if b["id"] in matched_bank_ids:
        continue
    best, best_score = None, 0
    for l in ledger:
        if l["id"] in matched_ledger_ids:
            continue
        amt_ok = abs(b["amount"] - l["amount"]) <= AMOUNT_TOLERANCE
        date_ok = abs((b["date"] - l["date"]).days) <= DATE_WINDOW_DAYS
        ref_score = fuzz.ratio(b["ref"], l["ref"])
        if amt_ok and date_ok and ref_score >= REF_FUZZY_THRESHOLD:
            score = ref_score
            if score > best_score:
                best, best_score = l, score
    if best:
        matched_bank_ids.add(b["id"])
        matched_ledger_ids.add(best["id"])
        results.append({"bank_id": b["id"], "ledger_id": best["id"], "method": "fuzzy",
                         "confidence": round(best_score/100, 2),
                         "note": f"amount diff={round(abs(b['amount']-best['amount']),2)}, "
                                 f"date diff={abs((b['date']-best['date']).days)}d, ref_sim={best_score}"})

# ---------- PASS 2b: split-payment detection ----------
# Look for TWO unmatched bank rows whose combined amount matches ONE unmatched ledger row,
# with refs sharing a common prefix (our synthetic generator uses "REF-A"/"REF-B").
unmatched_bank = [b for b in bank if b["id"] not in matched_bank_ids]
for l in ledger:
    if l["id"] in matched_ledger_ids:
        continue
    for i in range(len(unmatched_bank)):
        for j in range(i+1, len(unmatched_bank)):
            b1, b2 = unmatched_bank[i], unmatched_bank[j]
            if b1["id"] in matched_bank_ids or b2["id"] in matched_bank_ids:
                continue
            combined = round(b1["amount"] + b2["amount"], 2)
            prefix_match = b1["ref"].split("-")[0] == b2["ref"].split("-")[0] == l["ref"]
            if abs(combined - l["amount"]) < 0.5 and prefix_match:
                matched_bank_ids.update([b1["id"], b2["id"]])
                matched_ledger_ids.add(l["id"])
                results.append({"bank_id": f"{b1['id']}+{b2['id']}", "ledger_id": l["id"],
                                 "method": "split_payment_rule",
                                 "confidence": 0.9,
                                 "note": f"two bank entries ({b1['amount']}+{b2['amount']}) sum to ledger amount {l['amount']}"})

# ---------- PASS 3: LLM-assisted for remaining ambiguous rows ----------
# (Stubbed here with a clear TODO - wire in your Gemini API key.
#  Only the genuinely leftover, rule-can't-decide rows get sent here -
#  that's the "right tool in the right place" judgment call.)
remaining_bank = [b for b in bank if b["id"] not in matched_bank_ids]
remaining_ledger = [l for l in ledger if l["id"] not in matched_ledger_ids]

llm_candidates = []
for b in remaining_bank:
    for l in remaining_ledger:
        # only send genuinely close-but-not-rule-confident pairs to the LLM,
        # not every possible pair (that would be wasteful and unprincipled)
        amt_close = abs(b["amount"] - l["amount"]) <= 500
        if amt_close:
            llm_candidates.append((b, l))

# Group by bank_id so Gemini sees ALL plausible ledger candidates for a
# given bank transaction together, not one isolated pair at a time. This
# only reorganizes the SAME (bank, ledger) pairs already selected above -
# it doesn't change which pairs qualify as candidates.
candidates_by_bank = {}
for b, l in llm_candidates:
    candidates_by_bank.setdefault(b["id"], {"bank": b, "ledger_candidates": []})
    candidates_by_bank[b["id"]]["ledger_candidates"].append(l)

# Real LLM call: the model PROPOSES a match with confidence + reasoning,
# but we deliberately do NOT auto-commit it. It goes into a human review
# queue instead. This is a conscious boundary, not a missing feature:
# financial reconciliation shouldn't auto-execute on an LLM's say-so.
#
# Sees ALL plausible ledger candidates for a given bank transaction in ONE
# request (grouped by bank_id above), instead of judging isolated pairs with
# no awareness of alternatives. The per-candidate review_queue.json entries
# are still emitted individually afterward, so the existing app.py (bank_id,
# ledger_id, llm_verdict, status fields; Approve/Reject per candidate) keeps
# working unchanged.
#
# PROVIDER: Gemini API (free tier), via raw HTTP - no SDK dependency.
import os
review_queue = []
llm_flagged_bank, llm_flagged_ledger = set(), set()

api_key = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.5-flash"  # verify current free-tier model name at aistudio.google.com before running

def ask_gemini_grouped(bank_row, ledger_candidates):
    """One call per bank row. Sends every plausible ledger candidate together
    so Gemini can compare them, plus precomputed amount/date/ref/party
    similarity signals to ground its reasoning. Returns a dict with
    best_candidate_ref, confidence, reason, ranked_alternatives - or a safe
    fallback dict on any failure."""
    cand_lines = []
    for l in ledger_candidates:
        amt_diff = round(abs(bank_row["amount"] - l["amount"]), 2)
        date_diff = abs((bank_row["date"] - l["date"]).days)
        ref_sim = fuzz.ratio(bank_row["ref"], l["ref"])
        party_sim = fuzz.ratio(bank_row["party"], l["party"])
        cand_lines.append(
            f"- ledger_ref={l['ref']}, party={l['party']}, amount={l['amount']}, date={l['date']} "
            f"| amount_diff={amt_diff}, date_diff_days={date_diff}, ref_similarity={ref_sim}/100, party_similarity={party_sim}/100"
        )
    prompt = (
        f"Bank transaction: date={bank_row['date']}, party={bank_row['party']}, "
        f"amount={bank_row['amount']}, ref={bank_row['ref']}\n\n"
        f"Candidate ledger entries for this bank transaction:\n" + "\n".join(cand_lines) + "\n\n"
        "Considering amount difference, date difference, reference similarity, and "
        "party/name similarity, which ONE ledger candidate most plausibly represents "
        "the same underlying transaction? "
        'Respond ONLY with JSON: {"best_candidate_ref": "<ledger_ref of best match>", '
        '"confidence": 0-1, "reason": "short explanation", '
        '"ranked_alternatives": ["<ledger_ref>", ...] }'
    )
    if not api_key:
        return {"best_candidate_ref": None, "confidence": 0,
                "reason": "no API key set - set GEMINI_API_KEY to enable AI-assisted suggestions",
                "ranked_alternatives": []}
    import urllib.request
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)
        # basic shape validation - fall back safely if the model didn't comply
        if not isinstance(parsed, dict) or "best_candidate_ref" not in parsed:
            raise ValueError("response missing expected fields")
        parsed.setdefault("confidence", 0)
        parsed.setdefault("reason", "")
        parsed.setdefault("ranked_alternatives", [])
        return parsed
    except Exception as e:
        return {"best_candidate_ref": None, "confidence": 0,
                "reason": f"LLM call failed or returned invalid JSON: {e}",
                "ranked_alternatives": []}

for bank_id, group in candidates_by_bank.items():
    b = group["bank"]
    ledger_candidates = group["ledger_candidates"]
    group_verdict = ask_gemini_grouped(b, ledger_candidates)
    best_ref = group_verdict.get("best_candidate_ref")

    for l in ledger_candidates:
        is_top = (best_ref is not None) and (l["ref"] == best_ref)
        # Keep the original single-pair fields (match, confidence, reason) for
        # backward compatibility with app.py, populated from the grouped
        # verdict rather than an isolated per-pair call.
        per_candidate_verdict = {
            "match": True if is_top else (False if best_ref is not None else None),
            "confidence": group_verdict.get("confidence") if is_top else 0,
            "reason": group_verdict.get("reason") if is_top else
                      (f"Not selected - AI recommended {best_ref} instead" if best_ref else group_verdict.get("reason")),
            "best_candidate_ref": best_ref,
            "ranked_alternatives": group_verdict.get("ranked_alternatives", []),
            "is_top_recommendation": is_top,
        }
        status = "PENDING_HUMAN_REVIEW" if api_key else \
            "PENDING_HUMAN_REVIEW (no API key set - set GEMINI_API_KEY to enable AI-assisted suggestions)"
        review_queue.append({
            "bank_id": b["id"], "ledger_id": l["id"],
            "llm_verdict": per_candidate_verdict,
            "status": status,
        })
        llm_flagged_bank.add(b["id"])
        llm_flagged_ledger.add(l["id"])

with open("review_queue.json", "w") as f:
    json.dump(review_queue, f, indent=2, default=str)

# ---------- Build final report ----------
total_bank = len(bank)
matched_count = len(matched_bank_ids)
report = {
    "total_bank_rows": total_bank,
    "matched_bank_rows": matched_count,
    "match_rate_pct": round(100 * matched_count / total_bank, 1),
    "matches": results,
    "exceptions": [],
}

for b in bank:
    if b["id"] in matched_bank_ids:
        continue
    reason = "needs_llm_review (amount within ₹500 of an unmatched ledger row)" if b["id"] in llm_flagged_bank else "no plausible ledger counterpart found (possible unrecorded transaction)"
    report["exceptions"].append({"side": "bank", "id": b["id"], "ref": b["ref"],
                                  "amount": b["amount"], "date": str(b["date"]), "reason": reason})

for l in ledger:
    if l["id"] in matched_ledger_ids:
        continue
    reason = "needs_llm_review (amount within ₹500 of an unmatched bank row)" if l["id"] in llm_flagged_ledger else "no bank entry received yet (possible pending payment)"
    report["exceptions"].append({"side": "ledger", "id": l["id"], "ref": l["ref"],
                                  "amount": l["amount"], "date": str(l["date"]), "reason": reason})

with open("reconciliation_report.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print(f"Match rate: {report['match_rate_pct']}% ({matched_count}/{total_bank} bank rows matched)")
print(f"Matched via: exact={sum(1 for r in results if r['method']=='exact')}, "
      f"fuzzy={sum(1 for r in results if r['method']=='fuzzy')}, "
      f"split_payment={sum(1 for r in results if r['method']=='split_payment_rule')}")
print(f"Unmatched exceptions: {len(report['exceptions'])} "
      f"({len(llm_flagged_bank)+len(llm_flagged_ledger)} flagged for LLM review)")
print(f"Review queue: {len(review_queue)} candidate pairs awaiting human confirmation "
      f"(written to review_queue.json)")
print("Full report written to reconciliation_report.json")