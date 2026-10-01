import json

from reconai.ai_review import (ask_gemini, find_candidates, parse_response,
                               to_review_entries)
from tests.helpers import row

BANK = row("bank_0", "INV-1", 1000)
CANDS = [row("ledger_0", "INV-A", 1000), row("ledger_1", "INV-B", 1100)]


def gemini_reply(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_only_candidates_within_amount_window_are_sent():
    out = find_candidates([BANK], [row("ledger_0", "A", 1200), row("ledger_1", "B", 5000)], 500)
    assert [l["id"] for l in out["bank_0"]["ledger_candidates"]] == ["ledger_0"]


def test_no_api_key_gives_zero_confidence_fallback():
    v = ask_gemini(BANK, CANDS, api_key=None, model="m")
    assert v["best_candidate_ref"] is None and v["confidence"] == 0


def test_failed_call_falls_back_instead_of_guessing():
    def boom(*a, **k):
        raise TimeoutError("timed out")
    v = ask_gemini(BANK, CANDS, "key", "m", post=boom)
    assert v["best_candidate_ref"] is None and v["confidence"] == 0
    assert "timed out" in v["reason"]


def test_valid_reply_is_used():
    ok = gemini_reply({"best_candidate_ref": "INV-A", "confidence": 0.8, "reason": "same amount"})
    v = ask_gemini(BANK, CANDS, "key", "m", post=lambda *a, **k: ok)
    assert v["best_candidate_ref"] == "INV-A" and v["confidence"] == 0.8


def test_markdown_fenced_json_is_parsed():
    fenced = gemini_reply('```json\n{"best_candidate_ref": "INV-A", "confidence": 0.5}\n```')
    assert parse_response(fenced)["best_candidate_ref"] == "INV-A"


def test_unknown_ref_from_model_is_rejected():
    bad = gemini_reply({"best_candidate_ref": "MADE-UP", "confidence": 0.99})
    v = ask_gemini(BANK, CANDS, "key", "m", post=lambda *a, **k: bad)
    assert v["best_candidate_ref"] is None and v["confidence"] == 0


def test_garbage_reply_falls_back():
    v = ask_gemini(BANK, CANDS, "key", "m", post=lambda *a, **k: gemini_reply("not json"))
    assert v["best_candidate_ref"] is None


def test_confidence_is_clamped_to_0_1():
    assert parse_response(gemini_reply({"best_candidate_ref": "INV-A", "confidence": 7}))["confidence"] == 1.0


def test_review_entries_mark_top_pick_and_stay_pending():
    verdict = {"best_candidate_ref": "INV-A", "confidence": 0.8, "reason": "r", "ranked_alternatives": []}
    entries = to_review_entries(BANK, CANDS, verdict)
    assert [e["llm_verdict"]["is_top_recommendation"] for e in entries] == [True, False]
    assert all(e["status"] == "PENDING_HUMAN_REVIEW" for e in entries)