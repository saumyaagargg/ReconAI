ReconAI

AI-powered financial reconciliation system that matches bank transactions with internal ledger records and invoices, while keeping uncertain cases under human review.

Live Demo

https://reconnai.streamlit.app/

Project Overview

ReconAI is a financial reconciliation system designed to reduce the manual effort involved in comparing transaction records from different sources.

In a typical financial workflow, the same transaction can appear differently in a bank statement, an internal ledger, and an invoice record. Differences in dates, amounts, references, descriptions, or missing records can make manual reconciliation time-consuming.

ReconAI brings these sources together and uses a layered matching process to identify transactions that can be confidently reconciled. Cases that cannot be resolved reliably are separated for further review instead of being forced into an incorrect match.

The system also includes an AI-assisted review layer for ambiguous cases, while keeping the final decision with a human reviewer.


How It Works

ReconAI follows a layered reconciliation workflow.

1. The system reads the bank statement, internal ledger, and invoice records.

2. Transactions are compared using available information such as reference, amount, date, and transaction details.

3. Exact matches are identified first.

4. When an exact match is not available, potential matches are evaluated using less strict matching criteria.

5. The system assigns confidence information to the resulting matches.

6. Transactions that remain uncertain are placed into a review queue.

7. The AI review layer can provide a recommendation and reasoning for selected ambiguous cases.

8. The final approval remains with the human reviewer.


Main Features

Multi-source reconciliation

ReconAI works with three financial sources:

- Bank statement records
- Internal ledger records
- Invoice records

Matching

The reconciliation process starts with reliable exact matches and then evaluates transactions that require more flexible matching.

Confidence scoring

Potential matches are accompanied by confidence information so that users can distinguish between straightforward matches and cases that require additional attention.

Exception handling

Transactions that cannot be reliably matched are not automatically forced into a result. They remain visible as exceptions for further investigation.

AI-assisted review

The AI layer is used for cases where deterministic reconciliation alone is not sufficient. It provides a recommendation and supporting reasoning rather than directly making the final financial decision.

Human-in-the-loop approval

A reviewer can inspect the recommendation and approve or reject the proposed match. This keeps the human responsible for the final decision.

Transaction Explorer

The dashboard provides a way to search and compare transaction information across the available sources.

Dashboard

The Streamlit dashboard provides an overview of reconciliation results, matched transactions, exceptions, and the AI review queue.


Dashboard Sections

Executive Overview

The dashboard provides a high-level view of the reconciliation process, including transaction counts, matched transactions, match rate, unresolved exceptions, and the AI review queue.

Matched Transactions

This section displays transactions that have been successfully matched, along with information such as bank reference, bank amount, bank date, ledger reference, ledger amount, matching method, confidence, and notes.

Transaction Explorer

The Transaction Explorer allows users to search for a transaction and compare how it appears across the different data sources.

Data Source Summary

This section shows the number of records available in the bank statement, internal ledger, and invoice data.

Exceptions

Transactions that could not be confidently reconciled are shown separately so they can be investigated instead of being silently ignored.

AI Human Review

Ambiguous cases can be sent to the AI review layer. The reviewer can see the proposed match, confidence, and reasoning before making the final decision.


Project Structure

ReconAI/
│
├── app.py
├── reconcile.py
├── generate_data.py
│
├── bank_statement.csv
├── internal_ledger.csv
├── invoice_records.csv
├── ground_truth.csv
│
├── reconciliation_report.json
├── review_queue.json
├── review_decisions.json
│
├── .gitignore
└── README.md


Files

app.py

Contains the Streamlit dashboard and user interface for exploring the reconciliation results and review workflow.

reconcile.py

Contains the core reconciliation logic used to compare and match transaction records.

generate_data.py

Used to generate the project data used for testing the reconciliation workflow.

bank_statement.csv

Contains bank transaction records used by the system.

internal_ledger.csv

Contains internal ledger records used for reconciliation.

invoice_records.csv

Contains invoice-related transaction records.

ground_truth.csv

Contains the reference data used for evaluating the reconciliation results.

reconciliation_report.json

Stores the generated reconciliation results.

review_queue.json

Contains cases that require additional review.

review_decisions.json

Stores decisions made during the human review process.


Technology

Python

Streamlit

Pandas

JSON

CSV-based financial transaction data

AI-assisted review


Running the Project Locally

Clone the repository:

git clone https://github.com/saumyaagargg/ReconAI.git

Move into the project directory:

cd ReconAI

Create and activate a virtual environment:

python -m venv .venv

On Windows:

.venv\Scripts\activate

Install the required dependencies:

pip install streamlit pandas

Run the application:

streamlit run app.py

The dashboard will then open in the browser.


Design Approach

ReconAI is intentionally designed as a combination of deterministic reconciliation and AI-assisted review.

Deterministic matching is used where the available transaction information is sufficient. This makes the straightforward cases predictable and easier to validate.

AI is introduced only for cases where additional reasoning is useful.

The system does not treat an AI response as an automatic financial approval. Instead, the recommendation is presented to a human reviewer who makes the final decision.

This approach is intended to reduce manual effort without removing human oversight from financial reconciliation.


Handling Uncertain Cases

A key part of ReconAI is that not every transaction is forced into a match.

When the available evidence is insufficient, the transaction remains unresolved or is sent for review.

This is important because a higher match percentage is not useful if it is achieved by creating unreliable matches.

The system therefore makes uncertainty visible through exceptions, confidence information, and the human review queue.


Failure Handling

The AI review process can also encounter failures such as unavailable services or request timeouts.

When an AI request cannot provide a valid result, the system does not create a fabricated recommendation. The case can instead remain in the human review workflow.

This allows the rest of the reconciliation dashboard to continue functioning even when the AI layer is unavailable.


Limitations

The current version uses structured transaction data and a controlled dataset for demonstrating the reconciliation workflow.

Real-world financial systems can contain significantly larger volumes of data, additional transaction formats, currency differences, complex accounting rules, and integrations with banking or enterprise systems.

The current project is therefore a working prototype demonstrating the reconciliation workflow and human-in-the-loop design rather than a production banking integration.


Future Improvements

Possible future improvements include:

- Integration with live banking and accounting systems
- Support for larger transaction volumes
- More advanced matching models
- Better duplicate and split-transaction detection
- Role-based access control
- Audit logging for reviewer actions
- More detailed reconciliation analytics
- Additional financial data formats
- Production-grade authentication and deployment


Why ReconAI

The goal of ReconAI is not simply to maximize the number of automatically matched transactions.

The goal is to make reconciliation faster while keeping the process understandable and reviewable.

Straightforward transactions should be handled automatically.

Uncertain transactions should be clearly identified.

AI should assist where it adds value.

And important financial decisions should remain under human control.


Repository

GitHub:
https://github.com/saumyaagargg/ReconAI

Live Application:
https://reconnai.streamlit.app/

Pitch Video:
https://youtu.be/nQOEdBSpi98
