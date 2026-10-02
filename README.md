# ReconAI

Matches bank statement rows against an internal ledger, and sends the cases
it cannot settle to a human instead of guessing.

**Live demo:** https://reconnai.streamlit.app/

## The problem

The same payment often looks different in the bank statement and the ledger:
a mistyped reference, a date a day off, an amount off by a few rupees, or one
ledger entry paid as two bank transfers. Checking this by hand is slow.

## How it works

Rules run first, then AI for what is left. Each step only sees rows the
earlier steps did not match.

1. **Exact:** same reference, amount and date.
2. **Fuzzy:** amount within Rs 3, date within 2 days, similar reference
   (rapidfuzz score of 75 or more). Each bank row takes the best free ledger row.
3. **Split payment:** two bank rows within 5 days of a ledger row whose
   amounts add up to it. If more than one pair fits, it is skipped.
4. **AI review:** for the rest, Gemini sees all plausible ledger rows for a
   bank row (amount within Rs 500) and recommends one, with a reason.

The AI never approves anything. Its recommendation goes to a review queue and
a person clicks Approve or Reject in the dashboard. If the Gemini call fails,
times out, or names a ledger row that was not offered, the case goes to the
queue with confidence 0 and no recommendation.

All thresholds are in `reconai/config.py`.

## Run it

```
pip install -r requirements.txt
python -m reconai            # reads data/, writes output/
streamlit run app.py         # dashboard
```

To enable AI suggestions, set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`)
before running `python -m reconai`. Without a key the rules still run and the
ambiguous cases go to review with no suggestion.

Sample data: `python generate_data.py` creates fake bank, ledger and invoice
files.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

Tests cover each matching pass, the ambiguous-split case, AI failure
fallbacks (no key, timeout, bad JSON, unknown reference), and a full run on
small CSV files.

## Project layout

```
reconai/
  loader.py     read the CSVs
  exact.py      pass 1
  fuzzy.py      pass 2
  split.py      pass 3
  ai_review.py  Gemini call, validation, review queue entries
  engine.py     runs the passes, builds the report
  config.py     thresholds
app.py          Streamlit dashboard
tests/
data/           sample CSVs
```

## Limitations

- Data is synthetic. It has not been tried on real bank exports.
- Invoices are only shown in the dashboard's Transaction Explorer. They are
  not part of the matching.
- Fuzzy matching is greedy, so it is not a globally optimal assignment.
- Confidence for fuzzy matches is just reference similarity, and split
  matches use a fixed 0.9. They are rough signals, not probabilities.
- Approve and Reject decisions are saved to `review_decisions.json` but do
  not change the reconciliation report.
- Splits are only detected for exactly two bank rows.
