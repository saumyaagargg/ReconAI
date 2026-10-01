"""Tunable settings in one place. Change a number here, not in the matching code."""

# Fuzzy pass: how far apart can two records be and still be the same transaction?
AMOUNT_TOLERANCE = 3.0       # rupees
DATE_WINDOW_DAYS = 2
REF_FUZZY_THRESHOLD = 75     # rapidfuzz similarity, 0-100

# Split-payment pass: two bank rows that add up to one ledger row
SPLIT_AMOUNT_TOLERANCE = 0.5
SPLIT_DATE_WINDOW_DAYS = 5
SPLIT_CONFIDENCE = 0.9       # a fixed heuristic value, not a calibrated probability

# AI review: only bank/ledger pairs this close in amount are sent to the model
AI_AMOUNT_WINDOW = 500.0     # rupees
GEMINI_TIMEOUT_SECONDS = 60
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"  # override with the GEMINI_MODEL env var