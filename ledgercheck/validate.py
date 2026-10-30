"""Invariants the corpus has to satisfy.

These check the data, not a model. A fixture set that drifts out of agreement
with its own documents is worse than none at all, because it keeps producing
numbers that look like measurements.

Every check below either caught something while the corpus was being written
or guards a case that would go silently wrong the next time the catalog is
edited.
"""

from __future__ import annotations

import json
import statistics
from decimal import Decimal
from pathlib import Path

from .model import ANOMALIES, CATEGORIES


def _load(root: Path, name: str):
    return json.loads((root / name).read_text())


def validate(root: Path) -> list[str]:
    problems: list[str] = []

    extraction = _load(root, "extraction_truth.json")
    decisions = {d["doc_id"]: d for d in _load(root, "expected_decisions.json")}
    charges = _load(root, "card_statement.json")
    summary = _load(root, "corpus.json")

    def fail(msg: str) -> None:
        problems.append(msg)

    # --- structure -------------------------------------------------------
    ids = [row["doc_id"] for row in extraction]
    if len(set(ids)) != len(ids):
        fail("document ids are not unique")
    if sorted(ids) != ids:
        fail("documents are not in doc_id order")
    if set(ids) != set(decisions):
        fail("extraction truth and expected decisions cover different documents")

    for row in extraction:
        path = root / row["file"]
        if not path.exists():
            fail(f"{row['doc_id']}: file missing at {row['file']}")
        elif path.stat().st_size == 0:
            fail(f"{row['doc_id']}: file is empty")

    # --- arithmetic ------------------------------------------------------
    for row in extraction:
        subtotal = Decimal("0.00")
        for item in row["line_items"]:
            expected = (Decimal(item["quantity"]) * Decimal(item["unit_price"])).quantize(Decimal("0.01"))
            if expected != Decimal(item["amount"]):
                    fail(
                    f"{row['doc_id']}: line '{item['description'][:30]}' "
                    "amount does not equal quantity times unit price"
                )
            subtotal += Decimal(item["amount"])
        if subtotal.quantize(Decimal("0.01")) != Decimal(row["subtotal"]):
            fail(f"{row['doc_id']}: subtotal does not equal the sum of its lines")
        with_tax = (Decimal(row["subtotal"]) + Decimal(row["tax"])).quantize(Decimal("0.01"))
        if with_tax != Decimal(row["total"]):
            fail(f"{row['doc_id']}: total does not equal subtotal plus tax")

    # --- vocabulary ------------------------------------------------------
    for doc_id, row in decisions.items():
        if row["category"] not in CATEGORIES:
            fail(f"{doc_id}: unknown category {row['category']}")
        for anomaly in row["anomalies"]:
            if anomaly not in ANOMALIES:
                fail(f"{doc_id}: unknown anomaly {anomaly}")

    # --- every covered case is actually present --------------------------
    present = set()
    for row in decisions.values():
        present.update(row["anomalies"])
    if any(c["matching_doc_id"] is None for c in charges):
        present.add("missing_receipt")
    for anomaly in ANOMALIES:
        if anomaly not in present:
            fail(f"corpus claims to cover {anomaly} but no document carries it")
    if set(summary["cases"]) != set(ANOMALIES):
        fail("the case descriptions in the catalog and the anomaly list disagree")

    by_id = {row["doc_id"]: row for row in extraction}

    # --- duplicate -------------------------------------------------------
    dupes = [i for i, r in decisions.items() if "duplicate" in r["anomalies"]]
    for doc_id in dupes:
        this = by_id[doc_id]
        twins = [
            r for r in extraction
            if r["doc_id"] != doc_id
            and r["invoice_number"] == this["invoice_number"]
            and r["total"] == this["total"]
        ]
        if len(twins) != 1:
            fail(f"{doc_id}: marked duplicate but {len(twins)} matching originals found")
        elif abs(int(twins[0]["doc_id"][1:]) - int(doc_id[1:])) < 2:
            # A deduplicator that only compares a document with the one before
            # it would pass without doing anything. The case has to require a
            # lookup across the whole period.
            fail(
                f"{doc_id}: the duplicate is adjacent to its original, "
                "so the case does not exercise matching"
            )

    # --- price increase --------------------------------------------------
    for doc_id, row in decisions.items():
        if "price_increase" not in row["anomalies"]:
            continue
        supplier = row["supplier_canonical"]
        same = sorted(
            (by_id[i] for i, d in decisions.items() if d["supplier_canonical"] == supplier),
            key=lambda r: r["issue_date"],
        )
        idx = [r["doc_id"] for r in same].index(doc_id)
        if idx == 0:
            fail(f"{doc_id}: marked as a price increase but it is the first document for {supplier}")
        elif Decimal(same[idx]["total"]) <= Decimal(same[idx - 1]["total"]):
            fail(f"{doc_id}: marked as a price increase but it is not higher than the month before")

    # --- double billing --------------------------------------------------
    doubles = [i for i, r in decisions.items() if "double_billing" in r["anomalies"]]
    if len(doubles) != 2:
        fail(f"double billing needs exactly two sides, found {len(doubles)}")
    else:
        months = {by_id[i]["issue_date"][:7] for i in doubles}
        if len(months) != 1:
            fail("the two sides of the double billing are in different months")

    # --- netted statements -----------------------------------------------
    for doc_id, row in decisions.items():
        if "netted_statement" not in row["anomalies"]:
            continue
        figures = by_id[doc_id].get("statement_figures")
        if not figures:
            fail(f"{doc_id}: netted statement with no statement figures")
            continue
        gross, refunds, fees, net = (Decimal(figures[k]) for k in ("gross", "refunds", "fees", "net_payout"))
        if (gross - refunds - fees).quantize(Decimal("0.01")) != net:
            fail(f"{doc_id}: gross minus refunds minus fees does not equal the payout")
        if Decimal(row["bookable_amount"]) != fees:
            fail(f"{doc_id}: the bookable amount should be the fee, not the payout")
        if fees >= net:
            fail(f"{doc_id}: the fee is not smaller than the payout, so the case has no signal")

    # --- credit note, currency, amount anomaly ---------------------------
    for doc_id, row in decisions.items():
        if "credit_note" in row["anomalies"] and Decimal(row["bookable_amount"]) >= 0:
            fail(f"{doc_id}: credit note is not negative")
        if "foreign_currency" in row["anomalies"] and row["bookable_currency"] == summary["books_currency"]:
            fail(f"{doc_id}: marked foreign currency but it is in the books currency")
        if "amount_anomaly" in row["anomalies"]:
            supplier = row["supplier_canonical"]
            others = [
                Decimal(by_id[i]["total"])
                for i, d in decisions.items()
                if d["supplier_canonical"] == supplier and i != doc_id
            ]
            if not others or Decimal(row["bookable_amount"]) < statistics.median(others) * 2:
                fail(f"{doc_id}: marked an amount anomaly but it is not far from this supplier's normal")

    # --- card statement --------------------------------------------------
    unmatched = [c for c in charges if c["matching_doc_id"] is None]
    if len(unmatched) != 1:
        fail(f"expected exactly one card charge without a document, found {len(unmatched)}")
    for charge in charges:
        doc_id = charge["matching_doc_id"]
        if doc_id is None:
            amounts = {r["total"] for r in extraction}
            if charge["amount"] in amounts:
                fail("the unmatched charge shares an amount with a document, so the match is ambiguous")
            continue
        if doc_id not in by_id:
            fail(f"{charge['charge_id']}: points at unknown document {doc_id}")
        elif by_id[doc_id]["total"] != charge["amount"]:
            fail(f"{charge['charge_id']}: amount does not match document {doc_id}")
        elif "duplicate" in decisions[doc_id]["anomalies"]:
            fail(f"{charge['charge_id']}: a duplicate document should not also have a card charge")

    return problems
