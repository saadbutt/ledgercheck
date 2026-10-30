"""Write the corpus: the documents, and the two truth files.

The truth is split in two on purpose.

extraction_truth.json is what is literally printed on each page. Supplier
string, invoice number, date, currency, line items, totals.

expected_decisions.json is what a system should conclude. Which supplier
identity the string resolves to, which category the cost belongs in, and which
of the covered failure modes it should raise.

They are different problems and they fail differently. A pipeline can read
every field on a Stripe payout perfectly and still book the payout as an
expense, which is wrong by a factor of thirty. Scoring them together hides
that, so they get separate files and separate numbers.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import catalog, render
from .model import CardCharge, Document


def _dec(value: Decimal) -> str:
    """Money is written as a string, never a float.

    A JSON float cannot hold 1486.52 exactly, and a corpus whose own ground
    truth is approximate has no business scoring anyone else's accuracy.
    """
    return f"{value:.2f}"


def extraction_truth(doc: Document) -> dict[str, Any]:
    row: dict[str, Any] = {
        "doc_id": doc.doc_id,
        "file": f"documents/{doc.filename}",
        "doc_type": doc.doc_type,
        "render": doc.render,
        "supplier_raw": doc.supplier_raw,
        "invoice_number": doc.invoice_number,
        "issue_date": doc.issue_date,
        "received_date": doc.received_date,
        "currency": doc.currency,
        "line_items": [
            {
                "description": item.description,
                "quantity": f"{item.quantity}",
                "unit_price": _dec(item.unit_price),
                "amount": _dec(item.amount),
            }
            for item in doc.lines
        ],
        "subtotal": _dec(doc.subtotal),
        "tax": _dec(doc.tax),
        "total": _dec(doc.total),
    }
    if doc.netted:
        row["statement_figures"] = {k: _dec(v) for k, v in doc.netted.items()}
    return row


def expected_decision(doc: Document) -> dict[str, Any]:
    row: dict[str, Any] = {
        "doc_id": doc.doc_id,
        "supplier_canonical": doc.supplier_canonical,
        "category": doc.category,
        "bookable_amount": _dec(doc.total),
        "bookable_currency": doc.currency,
        "anomalies": sorted(doc.anomalies),
    }
    if doc.notes:
        row["why"] = doc.notes
    return row


def card_row(charge: CardCharge) -> dict[str, Any]:
    return {
        "charge_id": charge.charge_id,
        "posted_date": charge.posted_date,
        "descriptor": charge.descriptor,
        "amount": _dec(charge.amount),
        "currency": charge.currency,
        "matching_doc_id": charge.doc_id,
    }


def corpus_summary(docs: list[Document], charges: list[CardCharge]) -> dict[str, Any]:
    by_anomaly: dict[str, list[str]] = {}
    for doc in docs:
        for anomaly in doc.anomalies:
            by_anomaly.setdefault(anomaly, []).append(doc.doc_id)
    unmatched = [c.charge_id for c in charges if c.doc_id is None]
    if unmatched:
        by_anomaly["missing_receipt"] = unmatched
    return {
        "store": catalog.STORE,
        "books_currency": catalog.BOOKS_CURRENCY,
        "period": [catalog.MONTHS[0], catalog.MONTHS[-1]],
        "document_count": len(docs),
        "card_charge_count": len(charges),
        "cases": catalog.CASES,
        "case_doc_ids": {k: sorted(v) for k, v in sorted(by_anomaly.items())},
    }


def write_corpus(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    docs = catalog.build_documents()
    charges = catalog.build_card_statement(docs)

    render.write_all(docs, root / "documents")

    (root / "extraction_truth.json").write_text(
        json.dumps([extraction_truth(d) for d in docs], indent=2) + "\n"
    )
    (root / "expected_decisions.json").write_text(
        json.dumps([expected_decision(d) for d in docs], indent=2) + "\n"
    )
    (root / "card_statement.json").write_text(
        json.dumps([card_row(c) for c in charges], indent=2) + "\n"
    )
    summary = corpus_summary(docs, charges)
    (root / "corpus.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
