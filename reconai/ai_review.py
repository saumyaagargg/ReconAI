"""AI-assisted review for rows the rules could not decide.

The model only RECOMMENDS. Every recommendation goes to a human review queue.
If the call fails, times out, or returns something unusable, the case still
goes to the queue with zero confidence. Nothing is guessed.
"""
import json
import urllib.request

from rapidfuzz import fuzz

from .config import AI_AMOUNT_WINDOW, GEMINI_TIMEOUT_SECONDS

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def find_candidates(bank, ledger, amount_window=AI_AMOUNT_WINDOW):
    """Group plausible ledger rows by bank row, so the model sees all
    alternatives for one bank transaction together."""
    out = {}
    for b in bank:
        close = [l for l in ledger if abs(b["amount"] - l["amount"]) <= amount_window]
        if close:
            out[b["id"]] = {"bank": b, "ledger_candidates": close}
    return out


def build_prompt(bank_row, ledger_candidates):
    lines = []
    for l in ledger_candidates:
        lines.append(
            f"- ledger_ref={l['ref']}, party={l['party']}, amount={l['amount']}, date={l['date']} "
            f"| amount_diff={round(abs(bank_row['amount'] - l['amount']), 2)}, "
            f"date_diff_days={abs((bank_row['date'] - l['date']).days)}, "
            f"ref_similarity={fuzz.ratio(bank_row['ref'], l['ref'])}/100, "
            f"party_similarity={fuzz.ratio(bank_row['party'], l['party'])}/100"
        )
    return (
        f"Bank transaction: date={bank_row['date']}, party={bank_row['party']}, "
        f"amount={bank_row['amount']}, ref={bank_row['ref']}\n\n"
        "Candidate ledger entries for this bank transaction:\n" + "\n".join(lines) + "\n\n"
        "Considering amount difference, date difference, reference similarity, and "
        "party/name similarity, which ONE ledger candidate most plausibly represents "
        "the same underlying transaction? "
        'Respond ONLY with JSON: {"best_candidate_ref": "<ledger_ref of best match>", '
        '"confidence": 0-1, "reason": "short explanation", '
        '"ranked_alternatives": ["<ledger_ref>", ...] }'
    )


def fallback(reason):
    """The safe answer: no recommendation, zero confidence."""
    return {"best_candidate_ref": None, "confidence": 0,
            "reason": reason, "ranked_alternatives": []}


def _post_json(url, body, api_key, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def parse_response(data):
    """Pull the JSON verdict out of a Gemini response. Raises on bad shape."""
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict) or "best_candidate_ref" not in parsed:
        raise ValueError("response missing expected fields")
    try:
        conf = float(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0.0
    parsed["confidence"] = min(max(conf, 0.0), 1.0)
    parsed.setdefault("reason", "")
    parsed.setdefault("ranked_alternatives", [])
    return parsed


def ask_gemini(bank_row, ledger_candidates, api_key, model,
               timeout=GEMINI_TIMEOUT_SECONDS, post=_post_json):
    """One call per bank row. `post` can be swapped out in tests."""
    if not api_key:
        return fallback("no API key set - set GEMINI_API_KEY to enable AI-assisted suggestions")
    body = {"contents": [{"parts": [{"text": build_prompt(bank_row, ledger_candidates)}]}]}
    try:
        verdict = parse_response(post(API_URL.format(model=model), body, api_key, timeout))
        valid_refs = {l["ref"] for l in ledger_candidates}
        best = verdict["best_candidate_ref"]
        if best is not None and best not in valid_refs:
            return fallback(f"model recommended unknown ledger ref {best!r}")
        return verdict
    except Exception as e:
        return fallback(f"LLM call failed or returned invalid JSON: {e}")


def to_review_entries(bank_row, ledger_candidates, verdict):
    """One queue entry per candidate pair (the format the dashboard reads)."""
    best_ref = verdict.get("best_candidate_ref")
    entries = []
    for l in ledger_candidates:
        is_top = best_ref is not None and l["ref"] == best_ref
        if is_top:
            reason = verdict.get("reason")
        elif best_ref:
            reason = f"Not selected - AI recommended {best_ref} instead"
        else:
            reason = verdict.get("reason")
        entries.append({
            "bank_id": bank_row["id"], "ledger_id": l["id"],
            "llm_verdict": {
                "match": True if is_top else (False if best_ref else None),
                "confidence": verdict.get("confidence") if is_top else 0,
                "reason": reason,
                "best_candidate_ref": best_ref,
                "ranked_alternatives": verdict.get("ranked_alternatives", []),
                "is_top_recommendation": is_top,
            },
            "status": "PENDING_HUMAN_REVIEW",
        })
    return entries