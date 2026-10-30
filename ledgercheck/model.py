"""Data model for the corpus.

One rule holds this project together: the documents and the ground truth are
generated from the same objects. Nothing is transcribed by hand, so the truth
cannot drift away from the paper. If you change a line item, the PDF and the
expected answer change together or not at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# Categories a small ecommerce store actually books against. Deliberately not
# a generic chart of accounts: the point of the corpus is that the categories
# are the ones a Shopify operator argues about.
CATEGORIES: tuple[str, ...] = (
    "advertising",
    "platform_fees",
    "software",
    "cogs",
    "freight",
    "duty",
    "fulfilment",
    "processor_fees",
    "creator_marketing",
    "other",
)

# Every anomaly the corpus deliberately contains. The agent is scored on
# finding these and on not inventing extras.
ANOMALIES: tuple[str, ...] = (
    "duplicate",            # same invoice delivered twice
    "price_increase",       # a recurring charge went up
    "double_billing",       # billed through two channels in one period
    "missing_receipt",      # card charge with no document
    "credit_note",          # negative document against an earlier charge
    "netted_statement",     # gross minus fees minus refunds equals payout
    "amount_anomaly",       # far outside this supplier's normal range
    "foreign_currency",     # not in the books' currency
)


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


@dataclass
class Document:
    """One piece of paper, and everything true about it.

    `category` and `anomalies` are decision truth, not extraction truth. They
    are split apart when the corpus is written, because a system can read every
    field perfectly and still file the invoice under the wrong heading, and the
    two failures need separate numbers.
    """

    doc_id: str
    doc_type: str
    supplier_raw: str          # exactly as printed on the document
    supplier_canonical: str    # the identity the agent should resolve it to
    invoice_number: str
    issue_date: str            # ISO, the date printed on the page
    currency: str
    lines: list[LineItem]
    tax: Decimal = Decimal("0.00")
    category: str = "other"
    anomalies: list[str] = field(default_factory=list)
    notes: str = ""
    # When it landed in the inbox. Defaults to the issue date; a re-sent copy
    # carries the original date on the page but arrives much later.
    received_date: str = ""
    render: str = "pdf"        # pdf | scan
    # Statements report a payout rather than a charge, so the number a naive
    # reader picks up is not the number that belongs in the books.
    netted: dict[str, Decimal] | None = None

    def __post_init__(self) -> None:
        # A re-sent invoice carries its original date but arrives weeks later.
        # Keeping the two apart is what makes a duplicate findable without
        # comparing a document to the one immediately before it.
        if not self.received_date:
            self.received_date = self.issue_date

    @property
    def subtotal(self) -> Decimal:
        return sum((item.amount for item in self.lines), Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def total(self) -> Decimal:
        return (self.subtotal + self.tax).quantize(Decimal("0.01"))

    @property
    def filename(self) -> str:
        ext = "jpg" if self.render == "scan" else "pdf"
        return f"{self.doc_id}-{self.supplier_canonical}-{self.issue_date}.{ext}"


@dataclass(frozen=True)
class CardCharge:
    """A line on the card statement.

    `doc_id` is None where no document exists. That is the missing-receipt
    case, and it is the only way to test it: the absence has to be represented
    somewhere or there is nothing to find.
    """

    charge_id: str
    posted_date: str
    descriptor: str            # the mangled string a card statement prints
    amount: Decimal
    currency: str
    doc_id: str | None
