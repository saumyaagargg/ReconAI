"""
ReconAI — AI Finance Controller
Streamlit dashboard for the multi-source reconciliation engine.

Reads ONLY existing output files (reconciliation_report.json, review_queue.json)
and the three source CSVs. Never modifies reconcile.py, generate_data.py, the
CSVs, or reconciliation_report.json. Human review decisions on AI-proposed
matches are written to a separate review_decisions.json — the original report
and review queue are never touched.
"""

import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="ReconAI — AI Finance Controller", layout="wide")

# --- Light blue / dark blue theme (styling only, no functional change) ---
st.markdown("""
<style>
    .stApp { background-color: #EAF4FC; }
    h1, h2, h3 { color: #0B3D66; }
    [data-testid="stMetricValue"] { color: #0B3D66; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #1E5F8C; }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #BFE0F5;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 1px 3px rgba(11,61,102,0.08);
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border: 1px solid #BFE0F5;
        border-radius: 10px;
    }
    .stButton > button {
        background-color: #1E5F8C;
        color: white;
        border-radius: 6px;
        border: none;
    }
    .stButton > button:hover {
        background-color: #0B3D66;
        color: white;
    }
    [data-testid="stDataFrame"] { border: 1px solid #BFE0F5; border-radius: 8px; }
    .stTabs [data-baseweb="tab"] { color: #1E5F8C; }
</style>
""", unsafe_allow_html=True)

BASE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE, "reconciliation_report.json")
QUEUE_PATH = os.path.join(BASE, "review_queue.json")
DECISIONS_PATH = os.path.join(BASE, "review_decisions.json")
BANK_CSV = os.path.join(BASE, "bank_statement.csv")
LEDGER_CSV = os.path.join(BASE, "internal_ledger.csv")
INVOICE_CSV = os.path.join(BASE, "invoice_records.csv")


# ---------------------------------------------------------------------------
# Loaders — all defensive, no crashes on missing/empty files
# ---------------------------------------------------------------------------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return default


def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


report = load_json(REPORT_PATH, {})
review_queue = load_json(QUEUE_PATH, [])
decisions = load_json(DECISIONS_PATH, {})

bank_df = load_csv(BANK_CSV)
ledger_df = load_csv(LEDGER_CSV)
invoice_df = load_csv(INVOICE_CSV)

# Rebuild the same positional IDs reconcile.py assigns (bank_0, bank_1, ... /
# ledger_0, ledger_1, ...) so we can join report entries back to real rows.
if not bank_df.empty:
    bank_df = bank_df.reset_index().rename(columns={"index": "row_idx"})
    bank_df["row_id"] = "bank_" + bank_df["row_idx"].astype(str)
if not ledger_df.empty:
    ledger_df = ledger_df.reset_index().rename(columns={"index": "row_idx"})
    ledger_df["row_id"] = "ledger_" + ledger_df["row_idx"].astype(str)

bank_lookup = bank_df.set_index("row_id").to_dict("index") if not bank_df.empty else {}
ledger_lookup = ledger_df.set_index("row_id").to_dict("index") if not ledger_df.empty else {}


def resolve_bank(bank_id):
    """bank_id can be a single id ('bank_3') or a split-payment pair
    ('bank_5+bank_9'). Returns a list of row dicts."""
    if not bank_id:
        return []
    ids = bank_id.split("+")
    return [bank_lookup[i] for i in ids if i in bank_lookup]


def resolve_ledger(ledger_id):
    if not ledger_id or ledger_id not in ledger_lookup:
        return []
    return [ledger_lookup[ledger_id]]


missing_files = [p for p in [REPORT_PATH, BANK_CSV, LEDGER_CSV, INVOICE_CSV] if not os.path.exists(p)]
if missing_files:
    st.error(
        "Missing required file(s): " + ", ".join(os.path.basename(p) for p in missing_files) +
        ". Run generate_data.py and reconcile.py first."
    )
    st.stop()

matches = report.get("matches", [])
exceptions = report.get("exceptions", [])
total_bank_rows = report.get("total_bank_rows", len(bank_df))
matched_bank_rows = report.get("matched_bank_rows", 0)
match_rate = report.get("match_rate_pct", 0)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("ReconAI — AI Finance Controller")
st.caption("Multi-source financial reconciliation with AI-assisted human review")
st.divider()

# ---------------------------------------------------------------------------
# Section 1 — Executive Overview
# ---------------------------------------------------------------------------

st.subheader("Executive Overview")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Bank Transactions", total_bank_rows)
c2.metric("Matched Transactions", matched_bank_rows)
c3.metric("Match Rate", f"{match_rate}%")
c4.metric("Unmatched Exceptions", len(exceptions))
c5.metric("AI Review Queue", len(review_queue))

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Matching Breakdown
# ---------------------------------------------------------------------------

st.subheader("Matching Breakdown")

method_counts = {}
for m in matches:
    method_counts[m.get("method", "unknown")] = method_counts.get(m.get("method", "unknown"), 0) + 1

if method_counts:
    method_df = pd.DataFrame(
        {"Method": list(method_counts.keys()), "Count": list(method_counts.values())}
    ).set_index("Method")
    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.bar_chart(method_df)
    with col_table:
        st.dataframe(method_df, width="stretch")
else:
    st.info("No matches recorded yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Matched Transactions
# ---------------------------------------------------------------------------

st.subheader("Matched Transactions")

matched_rows = []
for m in matches:
    bank_rows = resolve_bank(m.get("bank_id"))
    ledger_rows = resolve_ledger(m.get("ledger_id"))
    bank_amt = sum(r.get("amount", 0) for r in bank_rows)
    bank_ref = " + ".join(str(r.get("reference_no", "")) for r in bank_rows)
    bank_date = ", ".join(str(r.get("date", "")) for r in bank_rows)
    ledger_amt = sum(r.get("amount", 0) for r in ledger_rows)
    ledger_ref = ", ".join(str(r.get("ref_id", "")) for r in ledger_rows)
    matched_rows.append({
        "Bank Ref": bank_ref,
        "Bank Amount": round(bank_amt, 2),
        "Bank Date": bank_date,
        "Ledger Ref": ledger_ref,
        "Ledger Amount": round(ledger_amt, 2),
        "Method": m.get("method", ""),
        "Confidence": m.get("confidence", ""),
        "Note": m.get("note", ""),
    })

matched_df = pd.DataFrame(matched_rows)

if not matched_df.empty:
    search = st.text_input("Search matched transactions (ref, method, note)", "")
    filtered = matched_df
    if search:
        mask = matched_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        filtered = matched_df[mask]
    method_filter = st.multiselect(
        "Filter by method", options=sorted(matched_df["Method"].unique()), default=[]
    )
    if method_filter:
        filtered = filtered[filtered["Method"].isin(method_filter)]
    st.dataframe(filtered, width="stretch", hide_index=True)
else:
    st.info("No matched transactions to display.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4 — Exceptions
# ---------------------------------------------------------------------------

st.subheader("Exceptions")

if exceptions:
    exc_df = pd.DataFrame(exceptions)
    reason_counts = exc_df["reason"].value_counts() if "reason" in exc_df.columns else pd.Series(dtype=int)

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.metric("Total Exceptions", len(exc_df))
        side_counts = exc_df["side"].value_counts() if "side" in exc_df.columns else pd.Series(dtype=int)
        for side, cnt in side_counts.items():
            st.write(f"**{side.capitalize()}-side:** {cnt}")
    with col_b:
        st.write("**Reasons:**")
        for reason, cnt in reason_counts.items():
            st.warning(f"{reason} — {cnt} row(s)")

    st.dataframe(exc_df, width="stretch", hide_index=True)
else:
    st.success("No unmatched exceptions.")

st.divider()

# ---------------------------------------------------------------------------
# Section 5 — AI Human Review Queue
# ---------------------------------------------------------------------------

st.subheader("AI Human Review Queue")
st.info("**AI recommendation — Human decision required.** AI does not auto-commit financial matches.")

if review_queue:
    for i, item in enumerate(review_queue):
        b_rows = resolve_bank(item.get("bank_id"))
        l_rows = resolve_ledger(item.get("ledger_id"))
        verdict = item.get("llm_verdict") or {}
        status = item.get("status", "PENDING_HUMAN_REVIEW")

        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write("**Bank entry**")
                for r in b_rows:
                    st.write(f"{r.get('date','')} · {r.get('description','')} · ₹{r.get('amount','')} · {r.get('reference_no','')}")
            with col2:
                st.write("**Proposed ledger match**")
                for r in l_rows:
                    st.write(f"{r.get('txn_date','')} · {r.get('narration','')} · ₹{r.get('amount','')} · {r.get('ref_id','')}")
            with col3:
                conf = verdict.get("confidence", "—") if verdict else "—"
                st.metric("AI Confidence", conf)

            reason = verdict.get("reason", "No AI reasoning available (no API key set at run time).") if verdict else "No AI reasoning available."
            st.caption(f"AI reasoning: {reason}")

            key_base = f"{item.get('bank_id')}_{item.get('ledger_id')}_{i}"
            existing_decision = decisions.get(key_base)

            if existing_decision:
                st.write(f"Decision recorded: **{existing_decision['decision']}** at {existing_decision['timestamp']}")
            else:
                dcol1, dcol2 = st.columns(2)
                if dcol1.button("Approve", key=f"approve_{key_base}"):
                    decisions[key_base] = {
                        "decision": "APPROVED",
                        "timestamp": datetime.now().isoformat(),
                        "bank_id": item.get("bank_id"),
                        "ledger_id": item.get("ledger_id"),
                    }
                    with open(DECISIONS_PATH, "w") as f:
                        json.dump(decisions, f, indent=2)
                    st.rerun()
                if dcol2.button("Reject", key=f"reject_{key_base}"):
                    decisions[key_base] = {
                        "decision": "REJECTED",
                        "timestamp": datetime.now().isoformat(),
                        "bank_id": item.get("bank_id"),
                        "ledger_id": item.get("ledger_id"),
                    }
                    with open(DECISIONS_PATH, "w") as f:
                        json.dump(decisions, f, indent=2)
                    st.rerun()
else:
    st.write("No items currently in the AI review queue. (Set `ANTHROPIC_API_KEY` before running `reconcile.py` to enable AI-assisted proposals for ambiguous cases.)")

st.divider()

# ---------------------------------------------------------------------------
# Section 6 — Transaction Explorer
# ---------------------------------------------------------------------------

st.subheader("Transaction Explorer")
st.caption("Search across all three sources to see how the same transaction appears differently in each.")

query = st.text_input("Search by reference, amount, or party/description", "", key="explorer_search")

if query:
    bank_matches = bank_df[bank_df.astype(str).apply(lambda row: row.str.contains(query, case=False).any(), axis=1)] if not bank_df.empty else pd.DataFrame()
    ledger_matches = ledger_df[ledger_df.astype(str).apply(lambda row: row.str.contains(query, case=False).any(), axis=1)] if not ledger_df.empty else pd.DataFrame()
    invoice_matches = invoice_df[invoice_df.astype(str).apply(lambda row: row.str.contains(query, case=False).any(), axis=1)] if not invoice_df.empty else pd.DataFrame()

    ecol1, ecol2, ecol3 = st.columns(3)
    with ecol1:
        st.write("**Bank**")
        st.dataframe(bank_matches.drop(columns=["row_idx", "row_id"], errors="ignore"), width="stretch", hide_index=True)
    with ecol2:
        st.write("**Ledger**")
        st.dataframe(ledger_matches.drop(columns=["row_idx", "row_id"], errors="ignore"), width="stretch", hide_index=True)
    with ecol3:
        st.write("**Invoice**")
        st.dataframe(invoice_matches, width="stretch", hide_index=True)
else:
    st.caption("Enter a search term above to compare records across sources.")

st.divider()

# ---------------------------------------------------------------------------
# Section 7 — Data Source Summary
# ---------------------------------------------------------------------------

st.subheader("Data Source Summary")

s1, s2, s3 = st.columns(3)
s1.metric("Bank Statement records", len(bank_df))
s2.metric("Internal Ledger records", len(ledger_df))
s3.metric("Invoice Records", len(invoice_df))
