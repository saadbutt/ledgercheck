"""Render each document as a PDF, and one of them as a phone photo.

The layouts differ on purpose. An ads invoice, a platform bill with app
charges buried in it, a manufacturer's proforma with carton quantities and a
payout statement where the headline figure is not an expense are four
different reading problems, and a corpus where every page looks the same
measures nothing.
"""

from __future__ import annotations

import io
import math
import random
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

from .catalog import STORE_ADDRESS
from .model import Document

W, H = A4
LEFT = 20 * mm
RIGHT = W - 20 * mm


def _money(amount: Decimal, currency: str) -> str:
    sign = "-" if amount < 0 else ""
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency + " ")
    return f"{sign}{symbol}{abs(amount):,.2f}"


def _header(c: pdfcanvas.Canvas, doc: Document, title: str) -> float:
    c.setFont("Helvetica-Bold", 15)
    c.drawString(LEFT, H - 28 * mm, doc.supplier_raw)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawRightString(RIGHT, H - 24 * mm, title)
    c.setFillColor(colors.black)

    y = H - 40 * mm
    c.setFont("Helvetica", 9)
    for i, line in enumerate(STORE_ADDRESS):
        c.drawString(LEFT, y - i * 4.6 * mm, line)

    c.setFont("Helvetica", 9)
    rows = [("Invoice number", doc.invoice_number), ("Date", doc.issue_date), ("Currency", doc.currency)]
    for i, (k, v) in enumerate(rows):
        c.drawRightString(RIGHT - 32 * mm, y - i * 4.6 * mm, k)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(RIGHT, y - i * 4.6 * mm, v)
        c.setFont("Helvetica", 9)

    c.setStrokeColor(colors.HexColor("#cccccc"))
    c.line(LEFT, y - 26 * mm, RIGHT, y - 26 * mm)
    return y - 34 * mm


def _line_table(c: pdfcanvas.Canvas, doc: Document, y: float, qty_header: str = "Qty") -> float:
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawString(LEFT, y, "Description")
    c.drawRightString(RIGHT - 60 * mm, y, qty_header)
    c.drawRightString(RIGHT - 30 * mm, y, "Unit")
    c.drawRightString(RIGHT, y, "Amount")
    c.setFillColor(colors.black)
    y -= 2 * mm
    c.setStrokeColor(colors.HexColor("#dddddd"))
    c.line(LEFT, y, RIGHT, y)
    y -= 6 * mm

    c.setFont("Helvetica", 9)
    for item in doc.lines:
        c.drawString(LEFT, y, item.description[:62])
        qty = f"{item.quantity:,.0f}" if item.quantity == item.quantity.to_integral() else f"{item.quantity}"
        c.drawRightString(RIGHT - 60 * mm, y, qty)
        c.drawRightString(RIGHT - 30 * mm, y, _money(item.unit_price, doc.currency))
        c.drawRightString(RIGHT, y, _money(item.amount, doc.currency))
        y -= 5.6 * mm
    return y - 4 * mm


def _totals(c: pdfcanvas.Canvas, doc: Document, y: float) -> float:
    c.setStrokeColor(colors.HexColor("#dddddd"))
    c.line(RIGHT - 70 * mm, y, RIGHT, y)
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawRightString(RIGHT - 30 * mm, y, "Subtotal")
    c.drawRightString(RIGHT, y, _money(doc.subtotal, doc.currency))
    if doc.tax:
        y -= 5 * mm
        c.drawRightString(RIGHT - 30 * mm, y, "Tax")
        c.drawRightString(RIGHT, y, _money(doc.tax, doc.currency))
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(RIGHT - 30 * mm, y, "Total due")
    c.drawRightString(RIGHT, y, _money(doc.total, doc.currency))
    c.setFont("Helvetica", 9)
    return y - 10 * mm


TITLES = {
    "ads_invoice": "Advertising invoice",
    "platform_bill": "Monthly platform bill",
    "saas_receipt": "Receipt",
    "supplier_invoice": "Proforma invoice",
    "freight_invoice": "Freight invoice",
    "credit_note": "Credit note",
    "duty_invoice": "Customs entry summary",
    "fulfilment_invoice": "Fulfilment invoice",
    "payout_statement": "Payout statement",
    "creator_invoice": "Invoice",
}


def _render_pdf_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4, invariant=1)
    y = _header(c, doc, TITLES.get(doc.doc_type, "Invoice"))

    if doc.doc_type == "payout_statement":
        # The payout is printed biggest, the fee is a line in the middle, and
        # only the fee is an expense.
        n = doc.netted or {}
        c.setFont("Helvetica-Bold", 10)
        c.drawString(LEFT, y, "Summary for the period")
        y -= 8 * mm
        c.setFont("Helvetica", 9.5)
        for label, key in [("Gross sales", "gross"), ("Refunds", "refunds"), ("Processing fees", "fees")]:
            c.drawString(LEFT, y, label)
            val = n.get(key, Decimal("0"))
            shown = -val if key in ("refunds", "fees") else val
            c.drawRightString(RIGHT, y, _money(shown, doc.currency))
            y -= 5.6 * mm
        y -= 3 * mm
        c.setStrokeColor(colors.HexColor("#dddddd"))
        c.line(LEFT, y, RIGHT, y)
        y -= 9 * mm
        c.setFont("Helvetica-Bold", 16)
        c.drawString(LEFT, y, "Net payout")
        c.drawRightString(RIGHT, y, _money(n.get("net_payout", Decimal("0")), doc.currency))
        y -= 14 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.HexColor("#777777"))
        c.drawString(LEFT, y, "Payout transferred to account ending 4471.")
        c.setFillColor(colors.black)
    else:
        qty_header = "Cartons" if doc.doc_type == "supplier_invoice" else "Qty"
        y = _line_table(c, doc, y, qty_header)
        y = _totals(c, doc, y)

    if doc.doc_type == "credit_note":
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.HexColor("#b03030"))
        c.drawString(LEFT, y, "This is a credit. The amount shown is owed to the customer.")
        c.setFillColor(colors.black)

    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#999999"))
    footer = "Generated for the ledgercheck corpus. Not a real invoice."
    c.drawString(LEFT, 16 * mm, footer)
    c.setFillColor(colors.black)
    c.showPage()
    c.save()
    return buf.getvalue()


def _degrade_to_photo(pdf_bytes: bytes, seed: int) -> bytes:
    """Turn a clean PDF into something that looks like it was photographed.

    Customs paperwork arrives as a phone picture of a printed page more often
    than it arrives as a PDF, and a corpus of nothing but clean renders lets a
    pipeline look better than it is. Slight rotation, uneven lighting, sensor
    noise and JPEG artefacts, all deterministic from the seed.
    """
    from pdf2image import convert_from_bytes
    from PIL import Image, ImageEnhance, ImageFilter

    rng = random.Random(seed)
    page = convert_from_bytes(pdf_bytes, dpi=150)[0].convert("RGB")

    page = page.rotate(
        rng.uniform(-1.6, 1.6), resample=Image.BICUBIC, expand=True, fillcolor=(246, 244, 240)
    )
    page = page.filter(ImageFilter.GaussianBlur(radius=0.6))

    # Uneven lighting: a soft diagonal gradient, brighter at one corner.
    w, h = page.size
    grad = Image.new("L", (w, h))
    px = grad.load()
    step = 4
    for yy in range(0, h, step):
        for xx in range(0, w, step):
            t = (xx / w) * 0.6 + (1 - yy / h) * 0.4
            v = int(200 + 55 * math.sin(t * math.pi))
            for dy in range(step):
                for dx in range(step):
                    if xx + dx < w and yy + dy < h:
                        px[xx + dx, yy + dy] = v
    page = Image.composite(page, Image.new("RGB", (w, h), (255, 255, 255)), grad)

    page = ImageEnhance.Contrast(page).enhance(0.92)
    page = ImageEnhance.Brightness(page).enhance(1.03)

    noise = Image.new("RGB", (w, h))
    npx = noise.load()
    for yy in range(0, h, 2):
        for xx in range(0, w, 2):
            n = rng.randint(118, 138)
            for dy in range(2):
                for dx in range(2):
                    if xx + dx < w and yy + dy < h:
                        npx[xx + dx, yy + dy] = (n, n, n)
    page = Image.blend(page, noise, 0.06)

    page.thumbnail((1400, 1980))
    out = io.BytesIO()
    page.save(out, "JPEG", quality=58)
    return out.getvalue()


def write_document(doc: Document, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = _render_pdf_bytes(doc)
    path = out_dir / doc.filename
    if doc.render == "scan":
        path.write_bytes(_degrade_to_photo(pdf, seed=int(doc.doc_id[1:])))
    else:
        path.write_bytes(pdf)
    return path


def write_all(docs: list[Document], out_dir: Path) -> list[Path]:
    """Render every document, and remove anything stale.

    Document ids move when the catalog changes, so without the sweep an old
    build leaves orphaned files behind and the folder stops matching the
    truth files. That is the same drift the whole project exists to avoid.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = [write_document(d, out_dir) for d in docs]
    keep = {p.name for p in written}
    for existing in out_dir.iterdir():
        if existing.is_file() and existing.name not in keep:
            existing.unlink()
    return written
