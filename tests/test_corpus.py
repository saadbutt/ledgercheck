"""Tests for the corpus and for the thing that checks the corpus.

The last test is the important one. A validator that cannot fail is not
evidence of anything, so it gets handed a deliberately broken corpus and has
to notice.
"""

from __future__ import annotations

import json
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from ledgercheck import catalog
from ledgercheck.generate import write_corpus
from ledgercheck.model import ANOMALIES
from ledgercheck.validate import validate

ROOT = Path(__file__).resolve().parent.parent / "corpus"


class TestCommittedCorpus(unittest.TestCase):
    def test_committed_corpus_is_consistent(self):
        self.assertEqual([], validate(ROOT))

    def test_every_anomaly_type_is_present(self):
        summary = json.loads((ROOT / "corpus.json").read_text())
        for anomaly in ANOMALIES:
            self.assertIn(anomaly, summary["case_doc_ids"], f"{anomaly} is not in the corpus")

    def test_money_is_never_a_float(self):
        # JSON floats cannot hold 1486.52 exactly. Ground truth that is already
        # approximate cannot be used to score anyone else's accuracy.
        def reject(found: str) -> None:
            raise AssertionError(f"ground truth contains a JSON float: {found}")

        for name in ("extraction_truth.json", "expected_decisions.json", "card_statement.json"):
            raw = json.loads((ROOT / name).read_text(), parse_float=reject)
            self.assertTrue(raw, name)

    def test_totals_round_trip_as_decimals(self):
        rows = json.loads((ROOT / "extraction_truth.json").read_text())
        for row in rows:
            self.assertEqual(Decimal(row["total"]), Decimal(row["subtotal"]) + Decimal(row["tax"]))


class TestGenerator(unittest.TestCase):
    def test_build_is_deterministic(self):
        with TemporaryDirectory() as a, TemporaryDirectory() as b:
            write_corpus(Path(a))
            write_corpus(Path(b))
            names = ("extraction_truth.json", "expected_decisions.json",
                     "card_statement.json", "corpus.json")
            for name in names:
                self.assertEqual(
                    (Path(a) / name).read_text(),
                    (Path(b) / name).read_text(),
                    f"{name} differs between two builds",
                )

    def test_documents_and_truth_cover_each_other(self):
        docs = catalog.build_documents()
        rows = json.loads((ROOT / "extraction_truth.json").read_text())
        self.assertEqual(len(docs), len(rows))
        self.assertEqual([d.doc_id for d in docs], [r["doc_id"] for r in rows])

    def test_duplicate_has_a_later_arrival_than_its_original(self):
        docs = {d.doc_id: d for d in catalog.build_documents()}
        dupes = [d for d in docs.values() if "duplicate" in d.anomalies]
        self.assertTrue(dupes)
        for dupe in dupes:
            original = next(
                d for d in docs.values()
                if d.doc_id != dupe.doc_id and d.invoice_number == dupe.invoice_number
            )
            self.assertEqual(dupe.issue_date, original.issue_date)
            self.assertGreater(dupe.received_date, original.received_date)


class TestRenderSweep(unittest.TestCase):
    def test_rebuild_removes_orphaned_documents(self):
        # Document ids move whenever the catalog changes. Without the sweep an
        # old build leaves files behind and the folder stops agreeing with the
        # truth files, which is the exact drift this project is about.
        with TemporaryDirectory() as d:
            tmp = Path(d)
            write_corpus(tmp)
            orphan = tmp / "documents" / "d999-ghost-2026-01-01.pdf"
            orphan.write_bytes(b"%PDF-1.4 stale\n")
            write_corpus(tmp)
            self.assertFalse(orphan.exists(), "a stale document survived a rebuild")
            self.assertEqual([], validate(tmp))


class TestValidatorCanFail(unittest.TestCase):
    """Break the corpus in one specific way each time and require a complaint."""

    def _broken(self, tmp: Path, mutate) -> list:
        write_corpus(tmp)
        path = tmp / "extraction_truth.json"
        rows = json.loads(path.read_text())
        mutate(tmp, rows)
        path.write_text(json.dumps(rows, indent=2))
        return validate(tmp)

    def test_catches_a_broken_total(self):
        with TemporaryDirectory() as d:
            def mutate(_tmp, rows):
                rows[0]["total"] = "1.00"
            problems = self._broken(Path(d), mutate)
            self.assertTrue(any("total does not equal" in p for p in problems), problems)

    def test_catches_a_missing_file(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            write_corpus(tmp)
            rows = json.loads((tmp / "extraction_truth.json").read_text())
            (tmp / rows[0]["file"]).unlink()
            problems = validate(tmp)
            self.assertTrue(any("file missing" in p for p in problems), problems)

    def test_catches_a_payout_booked_instead_of_a_fee(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            write_corpus(tmp)
            path = tmp / "expected_decisions.json"
            rows = json.loads(path.read_text())
            target = next(r for r in rows if "netted_statement" in r["anomalies"])
            truth = next(
                r for r in json.loads((tmp / "extraction_truth.json").read_text())
                if r["doc_id"] == target["doc_id"]
            )
            target["bookable_amount"] = truth["statement_figures"]["net_payout"]
            path.write_text(json.dumps(rows, indent=2))
            problems = validate(tmp)
            self.assertTrue(any("should be the fee" in p for p in problems), problems)

    def test_catches_a_duplicate_that_also_has_a_card_charge(self):
        with TemporaryDirectory() as d:
            tmp = Path(d)
            write_corpus(tmp)
            decisions = json.loads((tmp / "expected_decisions.json").read_text())
            dupe = next(r for r in decisions if "duplicate" in r["anomalies"])
            path = tmp / "card_statement.json"
            charges = json.loads(path.read_text())
            charges.append({
                "charge_id": "c999", "posted_date": "2026-03-01",
                "descriptor": "FACEBK *ADS 4QX9", "amount": "6744.12",
                "currency": "USD", "matching_doc_id": dupe["doc_id"],
            })
            path.write_text(json.dumps(charges, indent=2))
            problems = validate(tmp)
            self.assertTrue(any("should not also have a card charge" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
