"""The scenario: six months of paper for one ecommerce store.

Everything the corpus contains is declared here. The renderer draws from these
objects and the truth files are written from the same objects, so a change in
one place moves both.

The store is Harbour & Pine, a US homeware brand on Shopify, books in USD,
January to June 2026. The suppliers are the ones a store that size actually
pays: two ad platforms, the Shopify bill with apps buried inside it, a handful
of SaaS subscriptions, a freight forwarder, a customs broker, an overseas
manufacturer, a 3PL and a payment processor.

The eight cases in CASES below are the ones that cost money in practice. They
are what the corpus is for. A system that reads every field correctly and
catches none of them is not useful to anyone.
"""

from __future__ import annotations

from decimal import Decimal as D

from .model import CardCharge, Document, LineItem

BOOKS_CURRENCY = "USD"
STORE = "Harbour & Pine"
STORE_ADDRESS = ["Harbour & Pine LLC", "1180 SE Grand Ave, Suite 210", "Portland, OR 97214", "United States"]

MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]


def _d(month: str, day: int) -> str:
    return f"{month}-{day:02d}"


# --------------------------------------------------------------------------
# Advertising
# --------------------------------------------------------------------------

# Meta prints its own name three different ways across six months, and the
# card statement prints a fourth. Resolving these to one supplier is a string
# problem with an alias table, not a semantic one, and the corpus exists partly
# to stop people reaching for embeddings here.
_META_NAMES = [
    "META PLATFORMS IRELAND LIMITED",
    "META PLATFORMS IRELAND LIMITED",
    "Meta Platforms Ireland Ltd.",
    "Meta Platforms Ireland Ltd.",
    "META PLATFORMS IRELAND LTD",
    "META PLATFORMS IRELAND LTD",
]
_META_SPEND = [D("4218.44"), D("5102.90"), D("6744.12"), D("3980.55"), D("7221.08"), D("6015.73")]


def _meta() -> list[Document]:
    docs: list[Document] = []
    for i, month in enumerate(MONTHS):
        docs.append(
            Document(
                doc_id=f"d{len(docs) + 1:03d}",
                doc_type="ads_invoice",
                supplier_raw=_META_NAMES[i],
                supplier_canonical="meta",
                invoice_number=f"FBADS-2026-{i + 1:02d}-88431",
                issue_date=_d(month, 1),
                currency="USD",
                lines=[LineItem(f"Advertising services, {month}", D("1"), _META_SPEND[i])],
                category="advertising",
            )
        )
    return docs


def _google() -> list[Document]:
    spend = [D("2104.10"), D("2390.77"), D("2855.40"), D("2011.09"), D("3302.66"), D("2944.18")]
    return [
        Document(
            doc_id="",
            doc_type="ads_invoice",
            supplier_raw="Google Ireland Limited",
            supplier_canonical="google_ads",
            invoice_number=f"GGL-5520{i + 10}",
            issue_date=_d(month, 2),
            currency="USD",
            lines=[LineItem(f"Google Ads, {month}", D("1"), spend[i])],
            category="advertising",
        )
        for i, month in enumerate(MONTHS)
    ]


def _tiktok() -> list[Document]:
    spend = [D("880.00"), D("412.35")]
    return [
        Document(
            doc_id="",
            doc_type="ads_invoice",
            supplier_raw="TikTok Information Technologies UK Limited",
            supplier_canonical="tiktok_ads",
            invoice_number=f"TT-2026-{i + 1:02d}-0071",
            issue_date=_d(MONTHS[i], 3),
            currency="USD",
            lines=[LineItem(f"TikTok Ads, {MONTHS[i]}", D("1"), spend[i])],
            category="advertising",
            notes="Spend stops after February. Nothing is wrong with this. It is a"
                  " control: a system that calls every disappearance an anomaly should"
                  " lose points here.",
        )
        for i in range(2)
    ]


# --------------------------------------------------------------------------
# Platform and software
# --------------------------------------------------------------------------

# The Shopify bill is the interesting one. App charges are line items inside
# it, which is how a store ends up paying for the same app twice without
# noticing: once through Shopify and once on a card.
_SHOPIFY_APPS = {
    "2026-01": [("Klaviyo", D("0.00")), ("Gorgias", D("0.00"))],
    "2026-02": [("Judge.me Reviews", D("15.00"))],
    "2026-03": [("Judge.me Reviews", D("15.00"))],
    "2026-04": [("Judge.me Reviews", D("15.00")), ("Recharge Subscriptions", D("99.00"))],
    "2026-05": [("Judge.me Reviews", D("15.00"))],
    "2026-06": [("Judge.me Reviews", D("15.00")), ("Shopify Flow", D("0.00"))],
}


def _shopify() -> list[Document]:
    docs = []
    for _i, month in enumerate(MONTHS):
        lines = [LineItem("Shopify Advanced plan, monthly", D("1"), D("399.00"))]
        for name, price in _SHOPIFY_APPS[month]:
            if price > 0:
                lines.append(LineItem(f"App charge: {name}", D("1"), price))
        anomalies = ["double_billing"] if month == "2026-04" else []
        docs.append(
            Document(
                doc_id="",
                doc_type="platform_bill",
                supplier_raw="Shopify International Limited",
                supplier_canonical="shopify",
                invoice_number=f"SHOP-{month.replace('-', '')}-7741",
                issue_date=_d(month, 5),
                currency="USD",
                lines=lines,
                category="platform_fees",
                anomalies=anomalies,
                notes=(
                    "April bills Recharge inside the Shopify invoice while Recharge also"
                    " invoices the card directly the same month. Same service, same period,"
                    " two channels."
                    if month == "2026-04" else ""
                ),
            )
        )
    return docs


def _klaviyo() -> list[Document]:
    # The price rise is the headline case. It is invisible on any single
    # document and only exists in the comparison with the month before.
    prices = [D("45.00"), D("45.00"), D("45.00"), D("120.00"), D("120.00"), D("120.00")]
    docs = []
    for i, month in enumerate(MONTHS):
        docs.append(
            Document(
                doc_id="",
                doc_type="saas_receipt",
                supplier_raw="Klaviyo, Inc.",
                supplier_canonical="klaviyo",
                invoice_number=f"KLV-{month.replace('-', '')}-3312",
                issue_date=_d(month, 7),
                currency="USD",
                lines=[LineItem("Email marketing, monthly plan", D("1"), prices[i])],
                category="software",
                anomalies=["price_increase"] if month == "2026-04" else [],
                notes=(
                    "45.00 for three months, then 120.00. Nothing on the April receipt says"
                    " the price changed."
                    if month == "2026-04" else ""
                ),
            )
        )
    return docs


def _flat_saas() -> list[Document]:
    docs = []
    for month in MONTHS:
        docs.append(
            Document(
                doc_id="",
                doc_type="saas_receipt",
                supplier_raw="Gorgias Inc",
                supplier_canonical="gorgias",
                invoice_number=f"GRG-{month.replace('-', '')}",
                issue_date=_d(month, 8),
                currency="USD",
                lines=[LineItem("Helpdesk, Basic plan", D("1"), D("60.00"))],
                category="software",
            )
        )
    for month in MONTHS[1:]:
        docs.append(
            Document(
                doc_id="",
                doc_type="saas_receipt",
                supplier_raw="Loom, Inc.",
                supplier_canonical="loom",
                invoice_number=f"LOOM-{month.replace('-', '')}",
                issue_date=_d(month, 9),
                currency="USD",
                lines=[LineItem("Loom Business, 2 seats", D("2"), D("15.00"))],
                category="software",
            )
        )
    docs.append(
        Document(
            doc_id="",
            doc_type="saas_receipt",
            supplier_raw="Canva Pty Ltd",
            supplier_canonical="canva",
            invoice_number="CNV-2026-004412",
            issue_date="2026-01-14",
            currency="USD",
            lines=[LineItem("Canva Teams, annual, 3 seats", D("3"), D("100.00"))],
            category="software",
            notes="Annual, so it appears once. A system that expects monthly cadence"
                  " should not call the other five months missing.",
        )
    )
    docs.append(
        Document(
            doc_id="",
            doc_type="saas_receipt",
            supplier_raw="Figma, Inc.",
            supplier_canonical="figma",
            invoice_number="FIG-2026-0119",
            issue_date="2026-01-19",
            currency="USD",
            lines=[LineItem("Figma Professional, 1 seat", D("1"), D("16.00"))],
            category="software",
        )
    )
    docs.append(
        Document(
            doc_id="",
            doc_type="saas_receipt",
            supplier_raw="Recharge Payments, Inc.",
            supplier_canonical="recharge",
            invoice_number="RCH-20260411",
            issue_date="2026-04-11",
            currency="USD",
            lines=[LineItem("Recharge Subscriptions, Standard", D("1"), D("99.00"))],
            category="software",
            anomalies=["double_billing"],
            notes="The other half of the April double billing. Also charged on the"
                  " Shopify bill dated 2026-04-05.",
        )
    )
    return docs


# --------------------------------------------------------------------------
# Goods, freight, duty, fulfilment
# --------------------------------------------------------------------------

def _supply_chain() -> list[Document]:
    docs: list[Document] = []

    # Manufacturer proforma invoices. Carton quantities and unit prices, which
    # is a different extraction shape from a one-line SaaS receipt.
    docs.append(
        Document(
            doc_id="",
            doc_type="supplier_invoice",
            supplier_raw="Shenzhen Lianhe Trading Co., Ltd",
            supplier_canonical="shenzhen_lianhe",
            invoice_number="SZLH-PI-26014",
            issue_date="2026-01-22",
            currency="USD",
            lines=[
                LineItem("Ceramic vessel, 8oz, matte white (ctn of 48)", D("40"), D("182.40")),
                LineItem("Lid, bamboo, 8oz (ctn of 96)", D("20"), D("76.80")),
                LineItem("Printed carton, branded", D("60"), D("9.15")),
            ],
            category="cogs",
        )
    )
    docs.append(
        Document(
            doc_id="",
            doc_type="supplier_invoice",
            supplier_raw="Shenzhen Lianhe Trading Co., Ltd",
            supplier_canonical="shenzhen_lianhe",
            invoice_number="SZLH-PI-26037",
            issue_date="2026-04-09",
            currency="USD",
            lines=[
                LineItem("Ceramic vessel, 8oz, matte white (ctn of 48)", D("55"), D("182.40")),
                LineItem("Ceramic vessel, 12oz, sand (ctn of 36)", D("25"), D("214.20")),
                LineItem("Lid, bamboo, assorted (ctn of 96)", D("30"), D("76.80")),
            ],
            category="cogs",
        )
    )

    # A euro invoice in a USD book. The number on the page is not the number
    # that belongs in the ledger, and no conversion rate is printed anywhere.
    docs.append(
        Document(
            doc_id="",
            doc_type="supplier_invoice",
            supplier_raw="Cera Lusitana Unipessoal Lda",
            supplier_canonical="cera_lusitana",
            invoice_number="CL-2026-0188",
            issue_date="2026-03-17",
            currency="EUR",
            lines=[
                LineItem("Soy wax blend C-3, 25kg sack", D("48"), D("41.50")),
                LineItem("Cotton wick, CD-18, spool", D("12"), D("23.75")),
            ],
            category="cogs",
            anomalies=["foreign_currency"],
            notes="Priced in EUR. The books are USD and the document carries no rate.",
        )
    )

    # Freight, with tax, and a credit note against an earlier invoice.
    freight = [("2026-02-11", "DHL-EX-774120", D("1842.60")),
               ("2026-04-15", "DHL-EX-781004", D("2210.85")),
               ("2026-06-12", "DHL-EX-790331", D("1655.40"))]
    for date, num, amount in freight:
        docs.append(
            Document(
                doc_id="",
                doc_type="freight_invoice",
                supplier_raw="DHL Express (USA), Inc.",
                supplier_canonical="dhl",
                invoice_number=num,
                issue_date=date,
                currency="USD",
                lines=[
                    LineItem("Air freight, SZX to PDX, consolidated", D("1"), amount),
                    LineItem("Fuel surcharge", D("1"), (amount * D("0.185")).quantize(D("0.01"))),
                ],
                tax=D("0.00"),
                category="freight",
            )
        )
    docs.append(
        Document(
            doc_id="",
            doc_type="credit_note",
            supplier_raw="DHL Express (USA), Inc.",
            supplier_canonical="dhl",
            invoice_number="DHL-CN-781004-R",
            issue_date="2026-05-06",
            currency="USD",
            lines=[LineItem("Credit: re-weigh adjustment on DHL-EX-781004", D("1"), D("-318.40"))],
            category="freight",
            anomalies=["credit_note"],
            notes="Negative total. A system that takes absolute values will book this"
                  " as a cost and overstate freight by twice the credit.",
        )
    )

    for date, num, duty, mpf in [("2026-02-14", "USCB-44120", D("3104.22"), D("88.40")),
                                 ("2026-04-18", "USCB-45077", D("3870.15"), D("102.75"))]:
        docs.append(
            Document(
                doc_id="",
                doc_type="duty_invoice",
                supplier_raw="Mercer & Hale Customs Brokers LLC",
                supplier_canonical="mercer_hale",
                invoice_number=num,
                issue_date=date,
                currency="USD",
                lines=[
                    LineItem("Estimated duty, HTS 6912.00.4810", D("1"), duty),
                    LineItem("Merchandise processing fee", D("1"), mpf),
                    LineItem("Customs brokerage, entry preparation", D("1"), D("165.00")),
                ],
                category="duty",
                render="scan" if date == "2026-02-14" else "pdf",
                notes="Arrives as a phone photo of a printed entry summary."
                      if date == "2026-02-14" else "",
            )
        )

    # 3PL, monthly, with a storage spike in May.
    picks = [D("1840"), D("2110"), D("2605"), D("1990"), D("2402"), D("2755")]
    storage = [D("420.00"), D("455.00"), D("488.00"), D("502.00"), D("4100.00"), D("531.00")]
    for i, month in enumerate(MONTHS):
        sub_lines = [
            LineItem("Pick and pack, per order", picks[i], D("1.35")),
            LineItem("Storage, pallet months", D("1"), storage[i]),
            LineItem("Receiving, per carton", D("60"), D("1.10")),
        ]
        docs.append(
            Document(
                doc_id="",
                doc_type="fulfilment_invoice",
                supplier_raw="Pacific Fulfilment Partners, Inc.",
                supplier_canonical="pacific_fulfilment",
                invoice_number=f"PFP-{month.replace('-', '')}-118",
                issue_date=_d(month, 6),
                currency="USD",
                lines=sub_lines,
                tax=(sum((x.amount for x in sub_lines), D("0.00")) * D("0.0825")).quantize(D("0.01")),
                category="fulfilment",
                anomalies=["amount_anomaly"] if month == "2026-05" else [],
                notes="Storage jumps from about 500 to 4100 with no matching change in order volume."
                      if month == "2026-05" else "",
            )
        )
    return docs


# --------------------------------------------------------------------------
# Processor statements and one-offs
# --------------------------------------------------------------------------

def _processor() -> list[Document]:
    """Payout statements.

    The biggest number on the page is the payout, and the payout is not an
    expense. The only bookable figure here is the processing fee. A reader that
    grabs the largest currency amount, or the one next to the word total, gets
    this wrong every single month, and gets it wrong by a factor of thirty.
    """
    rows = [
        (D("48210.33"), D("1204.00"), D("1486.52")),
        (D("52998.71"), D("1890.45"), D("1632.09")),
        (D("61440.18"), D("2201.80"), D("1884.77")),
        (D("47115.62"), D("1455.20"), D("1451.06")),
        (D("69302.55"), D("3010.65"), D("2127.44")),
        (D("64877.90"), D("2244.10"), D("1992.18")),
    ]
    docs = []
    for i, month in enumerate(MONTHS):
        gross, refunds, fees = rows[i]
        net = (gross - refunds - fees).quantize(D("0.01"))
        docs.append(
            Document(
                doc_id="",
                doc_type="payout_statement",
                supplier_raw="Stripe Payments Company",
                supplier_canonical="stripe",
                invoice_number=f"PO-2026{i + 1:02d}-HP",
                issue_date=_d(month, 28),
                currency="USD",
                lines=[LineItem(f"Processing fees, {month}", D("1"), fees)],
                category="processor_fees",
                anomalies=["netted_statement"],
                netted={"gross": gross, "refunds": refunds, "fees": fees, "net_payout": net},
                notes="Only the fee belongs in the books. Gross and payout are on the page"
                      " and are both larger.",
            )
        )
    return docs


def _creators() -> list[Document]:
    return [
        Document(
            doc_id="",
            doc_type="creator_invoice",
            supplier_raw="Nadia Okonkwo",
            supplier_canonical="creator_nadia_okonkwo",
            invoice_number="INV-004",
            issue_date="2026-03-24",
            currency="USD",
            lines=[
                LineItem("UGC package, 3 videos, 1 round of edits", D("1"), D("900.00")),
                LineItem("Usage rights, paid social, 90 days", D("1"), D("300.00")),
            ],
            category="creator_marketing",
            notes="An individual's hand-made invoice. No VAT line, no company number,"
                  " a four-digit invoice number that restarts every client.",
        ),
        Document(
            doc_id="",
            doc_type="creator_invoice",
            supplier_raw="BRIGHTSIDE STUDIO (sole trader: T. Vasquez)",
            supplier_canonical="creator_brightside",
            invoice_number="2026-11",
            issue_date="2026-05-19",
            currency="USD",
            lines=[LineItem("Photography, product refresh, 24 assets", D("1"), D("1450.00"))],
            category="creator_marketing",
        ),
    ]


DUPLICATE_RECEIVED = "2026-05-02"


def _duplicate_of(original: Document, doc_id_hint: str) -> Document:
    """The same invoice arriving twice.

    Re-sent by the supplier with a different filename, which is how it happens
    in life. Same invoice number, same amount, same date. Nothing on either
    copy says it is a duplicate.
    """
    return Document(
        doc_id="",
        doc_type=original.doc_type,
        supplier_raw=original.supplier_raw,
        supplier_canonical=original.supplier_canonical,
        invoice_number=original.invoice_number,
        issue_date=original.issue_date,
        received_date=DUPLICATE_RECEIVED,
        currency=original.currency,
        lines=list(original.lines),
        tax=original.tax,
        category=original.category,
        anomalies=["duplicate"],
        notes=f"Second copy of the same invoice, re-sent by the supplier. Original is {doc_id_hint}.",
    )


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def build_documents() -> list[Document]:
    docs: list[Document] = []
    docs += _meta()
    docs += _google()
    docs += _tiktok()
    docs += _shopify()
    docs += _klaviyo()
    docs += _flat_saas()
    docs += _supply_chain()
    docs += _processor()
    docs += _creators()

    # The March Meta invoice arrives twice. Inserted after everything else so
    # the two copies are not adjacent, because a deduplicator that only checks
    # its immediate neighbour should not pass.
    march_meta = next(
        d for d in docs
        if d.supplier_canonical == "meta" and d.issue_date.startswith("2026-03")
    )
    docs.append(_duplicate_of(march_meta, "the March Meta invoice"))

    # Ordered by the day each document arrived, not the day it was issued.
    docs.sort(key=lambda d: (d.received_date, d.supplier_canonical, d.invoice_number))
    for i, doc in enumerate(docs, start=1):
        doc.doc_id = f"d{i:03d}"
    return docs


def build_card_statement(docs: list[Document]) -> list[CardCharge]:
    """The card statement.

    Most charges tie back to a document. One does not, and that absence is the
    missing-receipt case. It cannot be tested without being represented, so the
    statement is part of the corpus rather than an afterthought.

    Descriptors are mangled the way card statements mangle them, which is the
    other half of the supplier resolution problem.
    """
    descriptors = {
        "meta": "FACEBK *ADS 4QX9",
        "google_ads": "GOOGLE *ADS 8821",
        "tiktok_ads": "TIKTOK ADS LON",
        "shopify": "SHOPIFY* 7741",
        "klaviyo": "KLAVIYO INC BOSTON MA",
        "gorgias": "GORGIAS SAN FRANCISCO",
        "loom": "LOOM.COM",
        "canva": "CANVA* I-004412",
        "figma": "FIGMA MONTHLY",
        "recharge": "RECHARGE PAYMENTS",
        "dhl": "DHL EXPRESS USA",
        "mercer_hale": "MERCER HALE CUSTOMS",
        "pacific_fulfilment": "PACIFIC FULFILMENT PTN",
    }
    charges: list[CardCharge] = []
    n = 0
    for doc in docs:
        if doc.supplier_canonical not in descriptors:
            continue
        if doc.total <= 0:
            continue  # credit notes do not appear as card charges
        if "duplicate" in doc.anomalies:
            # The money left the account once. Two documents, one charge, which
            # is exactly what makes the duplicate findable rather than guessable.
            continue
        n += 1
        charges.append(
            CardCharge(
                charge_id=f"c{n:03d}",
                posted_date=doc.issue_date,
                descriptor=descriptors[doc.supplier_canonical],
                amount=doc.total,
                currency=doc.currency,
                doc_id=doc.doc_id,
            )
        )

    # No document for this one anywhere in the corpus.
    n += 1
    charges.append(
        CardCharge(
            charge_id=f"c{n:03d}",
            posted_date="2026-03-11",
            descriptor="ZAPIER.COM/CHARGE",
            amount=D("49.00"),
            currency="USD",
            doc_id=None,
        )
    )
    charges.sort(key=lambda c: (c.posted_date, c.descriptor))
    return charges


# The failure modes this corpus covers, and where each one occurs. The summary
# and the validator both read this, so the claims in the README cannot drift
# away from the data.
CASES = {
    "duplicate": "The March Meta invoice is re-sent in May. Same number, only one charge.",
    "price_increase": "Klaviyo goes from 45.00 to 120.00 in April with no notice on the receipt.",
    "double_billing": "Recharge is billed inside the April Shopify invoice and direct to the card.",
    "missing_receipt": "A 49.00 Zapier charge on the card statement has no document.",
    "credit_note": "DHL issues a negative credit note against an earlier freight invoice.",
    "netted_statement": "Six Stripe payouts where only the fee is bookable.",
    "amount_anomaly": "May storage at the 3PL is about eight times every other month.",
    "foreign_currency": "One supplier invoice is in EUR against USD books, with no rate printed.",
}
