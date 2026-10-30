# ledgercheck

[![CI](https://github.com/saadbutt/ledgercheck/actions/workflows/ci.yml/badge.svg)](https://github.com/saadbutt/ledgercheck/actions/workflows/ci.yml)

**A scored corpus of ecommerce bookkeeping documents: 64 invoices, receipts and
statements with a known correct answer for every field and every decision.**

Six months of paper for one Shopify store. Ad invoices, the platform bill with
app charges inside it, SaaS receipts, a manufacturer's proforma in cartons,
freight and customs, a 3PL, payout statements, creator invoices, and the card
statement that is supposed to reconcile against all of it.

It covers the eight failure modes that actually cost a store money:

```
duplicate         An invoice re-sent weeks later. Same number, one charge.
price_increase    A subscription goes from 45.00 to 120.00. No receipt says so.
double_billing    One app billed through the platform and direct in the same month.
missing_receipt   A card charge with no document anywhere in the corpus.
credit_note       A negative document issued against an earlier invoice.
netted_statement  A payout statement where only the fee is bookable. The payout is 30x.
amount_anomaly    Warehouse storage at eight times its normal month.
foreign_currency  A EUR invoice against USD books with no rate printed.
```

Python 3.10 or newer. Building the photographed document also needs poppler
(`brew install poppler` on macOS, `apt-get install poppler-utils` on Debian or
Ubuntu).

```
pip install -r requirements.txt
python -m ledgercheck.cli build     --root corpus
python -m ledgercheck.cli validate  --root corpus
python -m ledgercheck.cli summary   --root corpus
python -m unittest discover -s tests -t .
```

## Extraction truth and decision truth are separate

`extraction_truth.json` is what is printed on the page. Supplier string, invoice
number, date, currency, line items, totals.

`expected_decisions.json` is what a system should conclude. Which supplier the
printed string resolves to, which category the cost belongs in, which failure
modes apply.

They fail differently, so they are scored differently. A reader can get every
field on a payout statement exactly right and still book the payout as an
expense. The payout is thirty times the fee, so that single confusion costs more
than every other error in the file combined, and a combined accuracy number
hides it completely.

The card statement is part of the corpus for the same reason. A missing receipt
is an absence, and an absence cannot be measured unless it is represented.

## The documents and the truth come from one description

Everything is declared in `catalog.py` as data. The renderer draws the documents
from those objects and the truth files are written from the same objects. Change
a line item and both move, or neither does. There is no transcription step for
the two to disagree across.

One document is a photograph rather than a PDF, because customs paperwork
usually is.

## The validator, and the two things it caught

`validate.py` holds the invariants: every line amount equals quantity times unit
price, subtotals and totals agree, every covered case is present, the netted
statements actually net, the credit note is actually negative, a duplicate
document does not also carry a card charge.

It failed twice on the first run, and both times the data was wrong rather than
the check.

The duplicate invoice sorted directly beside its original, because they share an
issue date. A deduplicator comparing each document only against the one before
it would have scored full marks on a case that required nothing. Documents now
carry a received date as well as an issue date, and the re-sent copy arrives
seven weeks later still showing the original date, which is how it arrives in
practice.

The storage spike was 1.8 times the median month, which is worth a look but is
not an anomaly. It is eight times now.

There is also a test that hands the validator a deliberately corrupted corpus
and requires it to complain. A check that cannot fail is not evidence.

## What it is for

This is the measurement layer for an expense agent: a system that reads these
documents, resolves the supplier, assigns the category the way the store owner
assigns it, catches the eight cases above, and proposes ledger entries that a
person approves before anything is written.

The corpus was built first on purpose. Every number the agent reports later is
worth exactly what the fixtures behind it are worth.

## Scope and limitations

The documents are generated, not collected. They follow the real shape of a
Shopify store's paperwork, but no real invoice, supplier or amount appears
anywhere, and the generator is in the repo so the data can be audited rather
than trusted. That is deliberate: a fixture set you can regenerate and inspect
is more useful than a pile of redacted real invoices you cannot publish.

The photographed document is rotated, unevenly lit, noisy and JPEG compressed.
It is a phone photo, not a crumpled fax, and it is not a hard OCR case.

Eight failure modes across 64 documents is denser than a real inbox. That is
correct for scoring and it means a hit rate here does not transfer directly to
production volumes.
