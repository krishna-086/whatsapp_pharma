"""
Invoice Service - Orchestrates the invoice processing pipeline.

Extracted from legacy_reference/function_app.py.
This module does NOT call any SDK or DB directly; it delegates to:
  - storage.blob_storage.BlobStorage    (image upload)
  - ai.document_ai.DocumentAI           (OCR extraction)
  - database.cosmos_client.CosmosDBClient (session & invoice persistence)

Pipeline flow:
  1. Upload image  → BlobStorage.upload_invoice_image()
  2. Analyse image → DocumentAI.analyze_invoice_from_url()
  3. Recalculate totals & compute flags
  4. Save session  → Cosmos sessions container (temporary, editable)
  5. Handle edits  → EDIT / SHOW / OK / CONFIRM commands
  6. Finalize      → Move to invoices container, delete session
"""
import re
import logging
import os
from datetime import datetime

from azure.cosmos import CosmosClient

from ai.document_ai import DocumentAI
from storage.blob_storage import BlobStorage

logger = logging.getLogger(__name__)


class InvoiceService:
    """Service that orchestrates the full invoice pipeline."""

    def __init__(self):
        # AI + Storage delegates
        self.document_ai = DocumentAI()
        self.blob_storage = BlobStorage()

        # Cosmos DB (sessions + invoices)
        cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT", "")
        cosmos_key = os.environ.get("COSMOS_KEY", "")
        cosmos_db_name = os.environ.get("COSMOS_DB", "pharmagent")
        sessions_name = os.environ.get("COSMOS_CONTAINER_SESSIONS", "sessions")
        invoices_name = os.environ.get("COSMOS_CONTAINER_INVOICES", "invoices")

        self._cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        db = self._cosmos_client.get_database_client(cosmos_db_name)
        self._sessions = db.get_container_client(sessions_name)
        self._invoices = db.get_container_client(invoices_name)

        self.conf_threshold = float(os.environ.get("CONF_THRESHOLD", "0.85"))

    # ------------------------------------------------------------------
    #  Main pipeline entry: image bytes → structured invoice + flags
    # ------------------------------------------------------------------

    def process_invoice_image(self, image_bytes: bytes, sender: str) -> tuple:
        """
        Full pipeline: upload → analyse → recalc → flag → save session.

        Returns (invoice_dict, flags_list).
        """
        # 1. Upload to blob storage
        blob_url = self.blob_storage.upload_invoice_image(image_bytes, sender)
        logger.info("Invoice image uploaded: %s", blob_url)

        # 2. Analyse with Document Intelligence
        invoice = self.document_ai.analyze_invoice_from_url(blob_url)
        logger.info("Invoice extracted: %d items", len(invoice.get("items", [])))

        # 3. Recalculate totals
        self.recalc_total(invoice)

        # 4. Compute flags (missing expiry, etc.)
        flags = self.compute_flags(invoice)

        # 5. Save temporary session
        self.save_session(sender, blob_url, invoice, flags)

        return invoice, flags

    # ------------------------------------------------------------------
    #  Totals recalculation
    # ------------------------------------------------------------------

    @staticmethod
    def recalc_total(invoice: dict):
        """Recalculate item amounts and invoice net_amount from qty * unit_price."""
        total = 0.0
        for item in invoice.get("items", []):
            qty = float(item.get("quantity", {}).get("value") or 0)
            price = float(item.get("unit_price", {}).get("value") or 0)
            amount = qty * price
            item["amount"] = {
                "value": amount,
                "confidence": item.get("amount", {}).get("confidence"),
                "source": "computed",
            }
            total += amount
        invoice["net_amount"] = {
            "value": round(total, 2),
            "confidence": 1.0,
            "source": "computed",
        }

    # ------------------------------------------------------------------
    #  Flags (fields that need user confirmation)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_flags(invoice: dict) -> list:
        """Return a list of human-readable warnings for missing/low-confidence data."""
        flags = []
        for idx, item in enumerate(invoice.get("items", []), start=1):
            if not item.get("expiry_date", {}).get("value"):
                flags.append(f"Item {idx} expiry missing")
            if not item.get("batch_no", {}).get("value"):
                flags.append(f"Item {idx} batch missing")
        return flags

    # ------------------------------------------------------------------
    #  WhatsApp-friendly rendering
    # ------------------------------------------------------------------

    @staticmethod
    def render(invoice: dict, flags: list) -> str:
        """Render the invoice as a WhatsApp-friendly text message."""
        msg = []
        msg.append("Invoice received ✅")
        msg.append(f"Vendor: {invoice.get('vendor', {}).get('name', {}).get('value', 'N/A')}")
        msg.append(f"Invoice No: {invoice.get('invoice_number', {}).get('value', 'N/A')}")
        msg.append(f"Total: {invoice.get('net_amount', {}).get('value', 0.0)}")
        msg.append("")
        msg.append("Items:")

        for i, item in enumerate(invoice.get("items", []), 1):
            desc  = item.get("description", {}).get("value", "")
            qty   = item.get("quantity", {}).get("value", "")
            exp   = item.get("expiry_date", {}).get("value", "")
            batch = item.get("batch_no", {}).get("value", "")
            msg.append(
                f"{i}) {desc} | Qty: {qty} | "
                f"Batch: {batch or '(missing) ⚠'} | "
                f"Exp: {exp or '(missing) ⚠'}"
            )

        if flags:
            msg.append("\nNeeds confirmation ⚠")
            for f in flags:
                msg.append("- " + f)
            msg.append("\nReply: OK | EDIT 2 qty=10 | SHOW | CONFIRM")
        else:
            msg.append("\nReply CONFIRM to save ✅")

        return "\n".join(msg)

    # ------------------------------------------------------------------
    #  Session management (Cosmos DB)
    # ------------------------------------------------------------------

    def save_session(self, sender: str, blob_url: str, invoice: dict, flags: list):
        """Upsert the current invoice editing session."""
        self._sessions.upsert_item({
            "id": sender,
            "blob_url": blob_url,
            "invoice": invoice,
            "flags": flags,
        })

    def load_session(self, sender: str) -> dict | None:
        """Load an existing session for a sender, or None."""
        try:
            return self._sessions.read_item(sender, partition_key=sender)
        except Exception:
            return None

    def finalize(self, sender: str, session: dict):
        """Move the invoice to the invoices container and delete the session."""
        self._invoices.upsert_item({
            "id": sender,
            "invoice": session["invoice"],
            "confirmed_at": datetime.utcnow().isoformat(),
        })
        self._sessions.delete_item(sender, partition_key=sender)
        logger.info("Invoice finalized for sender: %s", sender)

    # ------------------------------------------------------------------
    #  Edit commands (EDIT 2 qty=10, EDIT 1 expiry=03-2026, etc.)
    # ------------------------------------------------------------------

    def apply_edit(self, session: dict, cmd: str) -> str:
        """
        Parse and apply an EDIT command to the session's invoice.
        Format: EDIT <item_number> <field>=<value>
        Returns a status message.
        """
        invoice = session["invoice"]
        raw = cmd.strip()[4:].strip()  # strip "EDIT"

        m = re.match(r"^(\d+)\s+([a-zA-Z_]+)\s*=\s*(.+)$", raw)
        if not m:
            return "Invalid EDIT format. Use: EDIT 2 qty=10"

        idx = int(m.group(1)) - 1
        field = m.group(2).lower()
        value = m.group(3).strip()

        if idx < 0 or idx >= len(invoice.get("items", [])):
            return "Invalid item number."

        item = invoice["items"][idx]

        if field in ("qty", "quantity"):
            item["quantity"] = {"value": float(value), "confidence": 1.0, "source": "manual"}
        elif field == "expiry":
            item["expiry_date"] = {"value": self._normalize_expiry(value) or value, "confidence": 1.0, "source": "manual"}
        elif field == "batch":
            item["batch_no"] = {"value": value, "confidence": 1.0, "source": "manual"}
        elif field in ("price", "unit_price"):
            item["unit_price"] = {"value": float(value), "confidence": 1.0, "source": "manual"}
        elif field == "mrp":
            item["mrp"] = {"value": float(value), "confidence": 1.0, "source": "manual"}
        else:
            return f"Unknown field '{field}'. Use: qty, expiry, batch, price, mrp."

        self.recalc_total(invoice)
        return "Item updated ✅"

    # ------------------------------------------------------------------
    #  Handle text commands on an active session
    # ------------------------------------------------------------------

    def handle_command(self, sender: str, text: str) -> str | None:
        """
        Handle SHOW / OK / CONFIRM / EDIT commands for an active session.

        Returns the response text to send back, or None if no session exists.
        """
        session = self.load_session(sender)
        if not session:
            return None

        upper = text.strip().upper()

        if upper == "SHOW":
            flags = self.compute_flags(session["invoice"])
            return self.render(session["invoice"], flags)

        if upper == "OK":
            self.save_session(sender, session["blob_url"], session["invoice"], [])
            return "Okay ✅ Saved as accepted. Reply CONFIRM to finalize."

        if upper == "CONFIRM":
            self.finalize(sender, session)
            return "Invoice confirmed ✅ Saved successfully."

        if upper.startswith("EDIT"):
            msg = self.apply_edit(session, text)
            flags = self.compute_flags(session["invoice"])
            self.save_session(sender, session["blob_url"], session["invoice"], flags)
            return msg + "\n\n" + self.render(session["invoice"], flags)

        return "Reply: SHOW | OK | EDIT ... | CONFIRM"

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_expiry(text: str) -> str:
        """Normalise user-typed expiry to MM-YYYY."""
        if not text:
            return ""
        text = text.replace("/", "-").replace(".", "-")
        m = re.search(r"\b(0[1-9]|1[0-2])-(\d{4})\b", text)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        m = re.search(r"\b(0[1-9]|1[0-2])-(\d{2})\b", text)
        if m:
            return f"{m.group(1)}-20{m.group(2)}"
        return ""
