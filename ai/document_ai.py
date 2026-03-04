"""
Document AI - Azure Document Intelligence integration for invoice/document extraction.

Extracted from legacy_reference/invoice_ocr_2.py and legacy_reference/function_app.py.
Combines the prebuilt-invoice model with robust table extraction for pharma-specific
fields (batch, expiry, manufacturer, MRP, free quantity).
"""
import re
import logging
import os
from datetime import date, datetime

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Pure helper functions (no state, easily testable)
# ---------------------------------------------------------------------------

def _to_iso(v):
    """Convert date/datetime to ISO string."""
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def _safe_float(x, default=0.0):
    """Safely parse a numeric value, stripping non-numeric chars."""
    try:
        if x is None:
            return default
        s = str(x).strip()
        if not s:
            return default
        s = re.sub(r"[^\d\.\-]", "", s)
        if s in ("", "-", ".", "-."):
            return default
        return float(s)
    except Exception:
        return default


def _normalize_header(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = (s or "").lower().strip()
    s = re.sub(r"[\W_]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _clean_cell(s: str) -> str:
    """Clean an OCR table cell: collapse lines, remove common bleed junk."""
    s = (s or "").strip()
    s = s.replace("\r", "\n")
    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    s = " ".join(lines).strip()
    junk = {"invoice", "inv", "bill", "taxinvoice", "voice"}
    parts = [p for p in re.split(r"\s+", s) if p.lower() not in junk]
    return " ".join(parts).strip()


# Expiry date regex patterns (common pharma formats)
_EXP_PATTERNS = [
    re.compile(r"\b(0[1-9]|1[0-2])[-/\.](\d{4})\b"),                              # MM-YYYY
    re.compile(r"\b(0[1-9]|1[0-2])[-/\.](\d{2})\b"),                              # MM-YY
    re.compile(r"\b(\d{4})[-/\.](0[1-9]|1[0-2])\b"),                              # YYYY-MM
    re.compile(r"\b(0[1-9]|[12]\d|3[01])[-/\.](0[1-9]|1[0-2])[-/\.](\d{2,4})\b"),  # DD-MM-YYYY
]


def _parse_expiry(s: str) -> str:
    """Extract and normalise an expiry date to MM-YYYY."""
    s = _clean_cell(s)
    if not s:
        return ""
    for pat in _EXP_PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        if pat.pattern.startswith(r"\b(0[1-9]|1[0-2])"):
            mm, yy = m.group(1), m.group(2)
            if len(yy) == 2:
                yy = "20" + yy
            return f"{mm}-{yy}"
        if pat.pattern.startswith(r"\b(\d{4})"):
            yy, mm = m.group(1), m.group(2)
            return f"{mm}-{yy}"
        mm, yy = m.group(2), m.group(3)
        if len(yy) == 2:
            yy = "20" + yy
        return f"{mm}-{yy}"
    return ""


def _parse_batch(s: str) -> str:
    """Extract a batch/lot number from a cell value."""
    s = _clean_cell(s)
    if not s:
        return ""
    first = s.split()[0]
    first = re.sub(r"[^A-Za-z0-9\-]", "", first)
    if _parse_expiry(first):
        return ""
    return first.strip()


# ---------------------------------------------------------------------------
#  Field extraction helpers
# ---------------------------------------------------------------------------

def _field_value_conf(fields: dict, name: str, default_value):
    """Extract value + confidence from a prebuilt Document Intelligence field."""
    f = fields.get(name) if fields else None
    if not f:
        return {"value": default_value, "confidence": 0.0, "source": "prebuilt"}

    if getattr(f, "value_string", None) is not None:
        val = f.value_string or default_value
    elif getattr(f, "value_date", None) is not None:
        val = _to_iso(f.value_date)
    elif getattr(f, "value_currency", None) is not None and f.value_currency:
        val = float(f.value_currency.amount or default_value)
    elif getattr(f, "value_number", None) is not None:
        val = float(f.value_number or default_value)
    elif getattr(f, "value_address", None) is not None:
        val = str(f.value_address) if f.value_address else default_value
    else:
        val = default_value

    conf = float(getattr(f, "confidence", 0.0) or 0.0)
    return {"value": val, "confidence": conf, "source": "prebuilt"}


def _obj_value_conf(obj: dict, name: str, default_value):
    """Extract value + confidence from a prebuilt line-item sub-field."""
    f = obj.get(name) if obj else None
    if not f:
        return {"value": default_value, "confidence": 0.0, "source": "prebuilt"}

    if getattr(f, "value_string", None) is not None:
        val = f.value_string or default_value
    elif getattr(f, "value_date", None) is not None:
        val = _to_iso(f.value_date)
    elif getattr(f, "value_currency", None) is not None and f.value_currency:
        val = float(f.value_currency.amount or default_value)
    elif getattr(f, "value_number", None) is not None:
        val = float(f.value_number or default_value)
    else:
        val = default_value

    conf = float(getattr(f, "confidence", 0.0) or 0.0)
    return {"value": val, "confidence": conf, "source": "prebuilt"}


def _table_field(val, cast=None):
    """Wrap a table-extracted value with source='table' (no DI confidence)."""
    if val is None:
        val = ""
    val = _clean_cell(str(val))
    if cast == "float":
        return {"value": _safe_float(val, 0.0), "confidence": None, "source": "table"}
    return {"value": val, "confidence": None, "source": "table"}


# ---------------------------------------------------------------------------
#  Robust table extraction (from invoice_ocr_2.py)
# ---------------------------------------------------------------------------

def _best_col_index(headers, keyword_groups):
    """Score header columns against keyword groups and return the best match index."""
    best_i, best_score = None, 0
    for i, h in enumerate(headers):
        score = 0
        for group in keyword_groups:
            for kw in group:
                if kw in h:
                    score += 3
            if h in group:
                score += 5
        if score > best_score:
            best_score, best_i = score, i
    return best_i if best_score >= 3 else None


def _choose_header_row(grid):
    """Heuristically pick the header row from the first few rows of a table grid."""
    candidate_rows = list(range(min(3, len(grid))))
    best_r, best = 0, -1
    header_hint = [
        "hsn", "desc", "qty", "batch", "exp", "rate",
        "mrp", "amount", "tax", "gst", "pack", "mfr",
    ]
    for r in candidate_rows:
        row_text = " ".join(_normalize_header(c) for c in grid[r])
        hits = sum(1 for w in header_hint if w in row_text)
        nonempty = sum(1 for c in grid[r] if _clean_cell(c))
        score = hits * 10 + nonempty
        if score > best:
            best = score
            best_r = r
    return best_r


def _row_fallback_expiry(row_cells):
    """Scan all cells in a row for an expiry date as a last resort."""
    for cell in row_cells:
        exp = _parse_expiry(cell)
        if exp:
            return exp
    return ""


def _row_fallback_batch(row_cells):
    """Scan all cells in a row for a batch number as a last resort."""
    for cell in row_cells:
        c = _clean_cell(cell)
        if not c:
            continue
        token = c.split()[0]
        token = re.sub(r"[^A-Za-z0-9\-]", "", token)
        if 3 <= len(token) <= 20 and any(ch.isdigit() for ch in token):
            if _parse_expiry(token):
                continue
            return token
    return ""


def _extract_best_item_table(tables):
    """Find the best medicine-item table from all tables in the DI result."""
    if not tables:
        return []

    best_rows = []
    best_score = -1

    for t in tables:
        grid = [["" for _ in range(t.column_count)] for _ in range(t.row_count)]
        for c in t.cells:
            grid[c.row_index][c.column_index] = (c.content or "").strip()

        header_row = _choose_header_row(grid)
        headers = [_normalize_header(grid[header_row][c]) for c in range(t.column_count)]

        col_desc  = _best_col_index(headers, [["description", "item", "product", "particular", "name", "medicine", "drug"]])
        col_hsn   = _best_col_index(headers, [["hsn", "hsncode", "hsn/sac", "sac"]])
        col_mfr   = _best_col_index(headers, [["mfr", "manuf", "manufacturer", "mfg", "company"]])
        col_pack  = _best_col_index(headers, [["pack", "packing", "pkg", "strip", "unit pack"]])
        col_mrp   = _best_col_index(headers, [["mrp", "m.r.p", "retail", "max retail"]])
        col_batch = _best_col_index(headers, [["batch", "batchno", "b no", "b.no", "bn", "lot", "lotno"]])
        col_exp   = _best_col_index(headers, [["exp", "expiry", "expdt", "exp date", "valid upto", "use before", "best before", "validity"]])
        col_qty   = _best_col_index(headers, [["qty", "quantity", "qnty", "qnt", "nos", "units"]])
        col_free  = _best_col_index(headers, [["free", "bonus", "sch", "scheme"]])
        col_rate  = _best_col_index(headers, [["rate", "unit price", "price", "uprice", "ptr"]])
        col_gst   = _best_col_index(headers, [["gst", "tax", "vat", "cgst", "sgst", "igst"]])
        col_amt   = _best_col_index(headers, [["amount", "net", "value", "total", "line total"]])

        important = [col_desc, col_qty, col_amt]
        score = sum(1 for c in important if c is not None) * 1000

        rows = []
        for r in range(header_row + 1, t.row_count):
            row_cells = [_clean_cell(grid[r][c]) for c in range(t.column_count)]
            if not any(row_cells):
                continue

            desc = row_cells[col_desc] if col_desc is not None else ""
            footer = (desc or "").lower()
            if footer in ("total", "subtotal", "grand total", "net total"):
                continue

            row = {
                "hsn_code":      row_cells[col_hsn]   if col_hsn   is not None else "",
                "manufacturer":  row_cells[col_mfr]   if col_mfr   is not None else "",
                "description":   desc,
                "pack":          row_cells[col_pack]  if col_pack  is not None else "",
                "mrp_raw":       row_cells[col_mrp]   if col_mrp   is not None else "",
                "batch_no_raw":  row_cells[col_batch] if col_batch is not None else "",
                "expiry_raw":    row_cells[col_exp]   if col_exp   is not None else "",
                "quantity_raw":  row_cells[col_qty]   if col_qty   is not None else "",
                "free_raw":      row_cells[col_free]  if col_free  is not None else "",
                "rate_raw":      row_cells[col_rate]  if col_rate  is not None else "",
                "gst_raw":       row_cells[col_gst]   if col_gst   is not None else "",
                "amount_raw":    row_cells[col_amt]   if col_amt   is not None else "",
                "_row_cells":    row_cells,
            }

            if row["description"] or row["hsn_code"] or row["batch_no_raw"] or row["expiry_raw"]:
                rows.append(row)

        score += len(rows)
        if score > best_score and rows:
            best_score = score
            best_rows = rows

    return best_rows


# ---------------------------------------------------------------------------
#  Fallback: extract batch/expiry from raw page text
# ---------------------------------------------------------------------------

def _extract_batch_expiry_from_raw(result, invoice):
    """Regex-scan raw page text for batch/expiry and fill gaps in items."""
    full_text = ""
    for page in result.pages:
        for line in page.lines:
            full_text += line.content + "\n"

    expiry_matches = re.findall(r"(0[1-9]|1[0-2])[-/\.](\d{2,4})", full_text)
    batch_matches = re.findall(r"\b[Bb]atch\s*[:\-]?\s*([A-Za-z0-9]+)", full_text)

    expiry_list = []
    for m in expiry_matches:
        mm = m[0]
        yy = m[1]
        if len(yy) == 2:
            yy = "20" + yy
        expiry_list.append(f"{mm}-{yy}")

    for i, item in enumerate(invoice["items"]):
        if not item.get("expiry_date", {}).get("value") and i < len(expiry_list):
            item["expiry_date"] = {"value": expiry_list[i], "confidence": 0.6, "source": "raw_fallback"}
        if not item.get("batch_no", {}).get("value") and i < len(batch_matches):
            item["batch_no"] = {"value": batch_matches[i], "confidence": 0.6, "source": "raw_fallback"}


# ---------------------------------------------------------------------------
#  DocumentAI class — public interface
# ---------------------------------------------------------------------------

class DocumentAI:
    """
    Wrapper for Azure Document Intelligence (Form Recognizer).

    Combines the prebuilt-invoice model with robust table extraction
    for pharmacy-specific columns (batch, expiry, manufacturer, MRP, free qty).
    """

    def __init__(self):
        self.endpoint = os.environ.get("AZURE_FORM_RECOGNIZER_ENDPOINT", "")
        self.key = os.environ.get("AZURE_FORM_RECOGNIZER_KEY", "")
        self._client = None

    def _get_client(self) -> DocumentIntelligenceClient:
        if self._client is None:
            logger.info("Initializing Document Intelligence client.")
            self._client = DocumentIntelligenceClient(
                self.endpoint, AzureKeyCredential(self.key)
            )
        return self._client

    # ------------------------------------------------------------------
    #  Main entry point: analyse a blob URL and return structured invoice
    # ------------------------------------------------------------------

    def analyze_invoice_from_url(self, blob_url: str) -> dict:
        """
        Analyse an invoice image/PDF via its blob URL.

        Returns a structured dict with vendor info, line items (including
        pharma fields), and computed totals.
        """
        logger.info("Analyzing invoice from URL: %s", blob_url)
        client = self._get_client()

        poller = client.begin_analyze_document(
            "prebuilt-invoice",
            AnalyzeDocumentRequest(url_source=blob_url),
        )
        result = poller.result()
        return self._build_invoice_dict(result)

    def analyze_invoice_from_bytes(self, file_bytes: bytes) -> dict:
        """
        Analyse an invoice from raw file bytes (useful for local testing).
        """
        logger.info("Analyzing invoice from bytes (%d bytes).", len(file_bytes))
        client = self._get_client()

        poller = client.begin_analyze_document(
            "prebuilt-invoice",
            AnalyzeDocumentRequest(bytes_source=file_bytes),
        )
        result = poller.result()
        return self._build_invoice_dict(result)

    # ------------------------------------------------------------------
    #  Internal: build the rich invoice dict from DI result
    # ------------------------------------------------------------------

    def _build_invoice_dict(self, result) -> dict:
        """Merge prebuilt fields + table extraction into a single invoice dict."""
        if not result.documents:
            raise ValueError("No invoice detected in the document.")

        doc = result.documents[0]
        fields = doc.fields or {}

        # Table rows from the best item table
        table_rows = _extract_best_item_table(getattr(result, "tables", None))

        invoice = {
            "invoice_number": _field_value_conf(fields, "InvoiceId", ""),
            "invoice_date":   _field_value_conf(fields, "InvoiceDate", ""),
            "due_date":       _field_value_conf(fields, "DueDate", ""),
            "vendor": {
                "name":   _field_value_conf(fields, "VendorName", ""),
                "gstin":  _field_value_conf(fields, "VendorTaxId", ""),
                "address": _field_value_conf(fields, "VendorAddress", ""),
                "phone":  _field_value_conf(fields, "VendorPhoneNumber", ""),
            },
            "buyer": {
                "name":   _field_value_conf(fields, "CustomerName", ""),
                "gstin":  _field_value_conf(fields, "CustomerTaxId", ""),
                "address": _field_value_conf(fields, "CustomerAddress", ""),
            },
            "items": [],
            "subtotal":   _field_value_conf(fields, "SubTotal", 0.0),
            "total_tax":  _field_value_conf(fields, "TotalTax", 0.0),
            "discount":   {"value": 0.0, "confidence": 0.0, "source": "computed"},
            "net_amount": _field_value_conf(fields, "InvoiceTotal", 0.0),
            "total_paid_quantity": {"value": 0.0, "confidence": 1.0, "source": "computed"},
            "total_free_quantity": {"value": 0.0, "confidence": 1.0, "source": "computed"},
            "total_quantity":      {"value": 0.0, "confidence": 1.0, "source": "computed"},
        }

        items_field = fields.get("Items")
        total_paid_qty = 0.0
        total_free_qty = 0.0

        # Strategy A: DI Items present → enrich with table data
        if items_field and getattr(items_field, "value_array", None):
            for idx, it in enumerate(items_field.value_array):
                obj = it.value_object or {}

                desc              = _obj_value_conf(obj, "Description", "")
                qty_prebuilt      = _obj_value_conf(obj, "Quantity", 0.0)
                unit_price_prebuilt = _obj_value_conf(obj, "UnitPrice", 0.0)
                amount_prebuilt   = _obj_value_conf(obj, "Amount", 0.0)
                product_code      = _obj_value_conf(obj, "ProductCode", "")

                paid_qty = float(qty_prebuilt["value"] or 0.0)
                total_paid_qty += paid_qty

                trow = table_rows[idx] if idx < len(table_rows) else None
                row_cells = (trow or {}).get("_row_cells", [])

                batch_raw = (trow or {}).get("batch_no_raw", "")
                exp_raw   = (trow or {}).get("expiry_raw", "")
                batch = _parse_batch(batch_raw) or _row_fallback_batch(row_cells)
                exp   = _parse_expiry(exp_raw) or _row_fallback_expiry(row_cells)

                free_raw = (trow or {}).get("free_raw", "")
                free_qty = _safe_float(free_raw, 0.0)
                total_free_qty += free_qty

                pack_val = (trow or {}).get("pack", "")
                mfr_val  = (trow or {}).get("manufacturer", "")
                mrp_val  = (trow or {}).get("mrp_raw", "")
                gst_val  = (trow or {}).get("gst_raw", "")
                rate_val = (trow or {}).get("rate_raw", "")
                amt_val  = (trow or {}).get("amount_raw", "")

                invoice["items"].append({
                    "hsn_code":      product_code if product_code["confidence"] > 0 else _table_field((trow or {}).get("hsn_code", "")),
                    "description":   desc,
                    "batch_no":      {"value": batch, "confidence": None, "source": "table"},
                    "expiry_date":   {"value": exp, "confidence": None, "source": "table"},
                    "pack":          _table_field(pack_val),
                    "manufacturer":  _table_field(mfr_val),
                    "mrp":           _table_field(mrp_val, cast="float"),
                    "free_quantity": {"value": free_qty, "confidence": None, "source": "table"},
                    "quantity":      qty_prebuilt,
                    "unit_price":    unit_price_prebuilt if unit_price_prebuilt["confidence"] > 0 else _table_field(rate_val, cast="float"),
                    "amount":        amount_prebuilt if amount_prebuilt["confidence"] > 0 else _table_field(amt_val, cast="float"),
                    "tax":           _obj_value_conf(obj, "Tax", "") if obj.get("Tax") else _table_field(gst_val),
                })

        # Strategy B: no DI Items → build purely from table
        else:
            for trow in table_rows:
                row_cells = trow.get("_row_cells", [])
                desc_val = _clean_cell(trow.get("description", ""))
                batch = _parse_batch(trow.get("batch_no_raw", "")) or _row_fallback_batch(row_cells)
                exp   = _parse_expiry(trow.get("expiry_raw", "")) or _row_fallback_expiry(row_cells)
                paid_qty = _safe_float(trow.get("quantity_raw", ""), 0.0)
                free_qty = _safe_float(trow.get("free_raw", ""), 0.0)
                total_paid_qty += paid_qty
                total_free_qty += free_qty

                invoice["items"].append({
                    "hsn_code":      _table_field(trow.get("hsn_code", "")),
                    "description":   {"value": desc_val, "confidence": None, "source": "table"},
                    "batch_no":      {"value": batch, "confidence": None, "source": "table"},
                    "expiry_date":   {"value": exp, "confidence": None, "source": "table"},
                    "pack":          _table_field(trow.get("pack", "")),
                    "manufacturer":  _table_field(trow.get("manufacturer", "")),
                    "mrp":           _table_field(trow.get("mrp_raw", ""), cast="float"),
                    "free_quantity": {"value": free_qty, "confidence": None, "source": "table"},
                    "quantity":      {"value": paid_qty, "confidence": None, "source": "table"},
                    "unit_price":    _table_field(trow.get("rate_raw", ""), cast="float"),
                    "amount":        _table_field(trow.get("amount_raw", ""), cast="float"),
                    "tax":           _table_field(trow.get("gst_raw", "")),
                })

        # Fallback: fill remaining gaps from raw page text
        _extract_batch_expiry_from_raw(result, invoice)

        # Totals
        invoice["total_paid_quantity"]["value"] = total_paid_qty
        invoice["total_free_quantity"]["value"] = total_free_qty
        invoice["total_quantity"]["value"] = total_paid_qty + total_free_qty

        return invoice
