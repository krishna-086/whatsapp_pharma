"""
Inventory Service – Business logic for stock management via WhatsApp.

Flows supported:
  1. **Sell** – "sold 2 of belladonna"
       → look up item → confirmation prompt → YES → deduct stock → receipt
  2. **Add stock** – "add 50 belladonna at ₹120"
       → confirmation → YES → upsert stock
  3. **Query stock** – "how much belladonna do we have?"
       → instant reply with qty / price
  4. **Delete item** – "delete belladonna from inventory"
       → confirmation → YES → remove doc

Pending-action state is persisted in the Cosmos *sessions* container
under id = ``pending:<sender>`` so it survives Function restarts.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from database import inventory_repo, transactions_repo
from database.cosmos_client import get_container
from services.receipt_generator import generate_receipt_html, upload_receipt

logger = logging.getLogger(__name__)

SESSIONS_CONTAINER = os.environ.get("COSMOS_CONTAINER_SESSIONS", "sessions")


# ======================================================================
#  Pending-action helpers (Cosmos-backed)
# ======================================================================

def _pending_id(sender: str) -> str:
    return f"pending:{sender}"


def _save_pending(sender: str, action: dict):
    ctr = get_container(SESSIONS_CONTAINER)
    doc = {
        "id": _pending_id(sender),
        "sender": sender,
        "action": action,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ctr.upsert_item(doc)


def _load_pending(sender: str) -> dict | None:
    ctr = get_container(SESSIONS_CONTAINER)
    try:
        doc = ctr.read_item(_pending_id(sender), partition_key=_pending_id(sender))
        return doc.get("action")
    except CosmosResourceNotFoundError:
        return None


def _clear_pending(sender: str):
    ctr = get_container(SESSIONS_CONTAINER)
    pid = _pending_id(sender)
    try:
        ctr.delete_item(pid, partition_key=pid)
    except CosmosResourceNotFoundError:
        pass


# ======================================================================
#  Public API
# ======================================================================

class InventoryService:
    """Service for managing pharmacy inventory via WhatsApp commands."""

    # ------------------------------------------------------------------
    #  Entry point called by the router
    # ------------------------------------------------------------------

    def handle_intent(self, sender: str, intent: str, entities: dict) -> str:
        """
        Dispatch an LLM-classified intent to the correct handler.

        Returns the WhatsApp reply text.
        """
        logger.info("InventoryService.handle_intent  intent=%s  entities=%s", intent, entities)

        if intent == "sell_item":
            return self._initiate_sale(sender, entities)

        if intent == "add_item":
            return self._initiate_add(sender, entities)

        if intent == "delete_item":
            return self._initiate_delete(sender, entities)

        if intent == "update_item":
            return self._initiate_update(sender, entities)

        if intent == "query_stock":
            return self._query_stock(entities)

        return ""  # not an inventory intent

    # ------------------------------------------------------------------
    #  Confirmation handlers (YES / NO)
    # ------------------------------------------------------------------

    def handle_confirmation(self, sender: str, answer: str) -> str | None:
        """
        Process a YES / NO reply to a pending confirmation.

        Returns the response text, or *None* if there is no pending action
        (so the router can fall through to general chat).
        """
        pending = _load_pending(sender)
        if pending is None:
            return None

        upper = answer.strip().upper()

        if upper in ("YES", "Y", "CONFIRM"):
            return self._confirm(sender, pending)

        if upper in ("NO", "N", "CANCEL"):
            _clear_pending(sender)
            return "Cancelled ❌"

        # Anything else – remind
        return (
            "You have a pending action.\n"
            f"→ {pending.get('summary', '')}\n\n"
            "Reply *YES* to confirm or *NO* to cancel."
        )

    # ------------------------------------------------------------------
    #  Sale flow
    # ------------------------------------------------------------------

    def _initiate_sale(self, sender: str, entities: dict) -> str:
        # ----- Multi-item sale -----
        # 1. LLM returned an "items" array
        items_list = entities.get("items")
        if items_list and isinstance(items_list, list) and len(items_list) > 1:
            return self._initiate_multi_sale(sender, items_list)

        # 2. LLM returned quantity as a dict (fallback format)
        qty_raw = entities.get("quantity") or entities.get("qty") or 1
        if isinstance(qty_raw, dict):
            name_raw = entities.get("name") or entities.get("medicine_name") or ""
            names = [n.strip() for n in name_raw.split(",") if n.strip()]
            if len(names) > 1:
                items_list = []
                for n in names:
                    q = qty_raw.get(n, 1)
                    items_list.append({"name": n, "quantity": int(q)})
                return self._initiate_multi_sale(sender, items_list)
            # Single item with dict quantity – take the first value
            qty_raw = list(qty_raw.values())[0] if qty_raw else 1

        # ----- Single-item sale -----
        name = entities.get("name") or entities.get("medicine_name") or ""
        qty = int(qty_raw)

        if not name:
            return "Please specify which item you sold. Example: *sold 2 of belladonna*"

        # Look up in inventory (exact first, then fuzzy)
        item = self._resolve_item(sender, name, intent="sell_item", entities=entities)
        if isinstance(item, str):
            return item  # it's a message ("did you mean?" or "not found")
        if item is None:
            return ""  # pending confirmation saved
        mrp = item.get("mrp", 0)
        amount = qty * mrp

        summary = (
            f"Sell *{qty}x {item['name']}*\n"
            f"MRP: ₹{mrp}\n"
            f"Total: ₹{amount}"
        )

        # Save pending
        _save_pending(sender, {
            "type": "sell",
            "item_id": item["id"],
            "item_name": item["name"],
            "quantity": qty,
            "mrp": mrp,
            "amount": amount,
            "summary": summary,
        })

        return f"🛒 Confirm sale:\n\n{summary}\n\nReply *YES* to confirm or *NO* to cancel."

    # ------------------------------------------------------------------
    #  Multi-item sale
    # ------------------------------------------------------------------

    def _initiate_multi_sale(self, sender: str, items_list: list[dict]) -> str:
        """Build a combined sale confirmation for multiple items."""
        resolved_items = []
        errors = []

        for entry in items_list:
            name = entry.get("name", "")
            qty = int(entry.get("quantity", 1))
            if not name:
                continue

            item = self._resolve_item_direct(name)
            if item is None:
                errors.append(f"• *{name}* — not found in inventory")
                continue

            mrp = item.get("mrp", 0)
            amount = round(qty * mrp, 2)
            resolved_items.append({
                "item_id": item["id"],
                "item_name": item["name"],
                "quantity": qty,
                "mrp": mrp,
                "amount": amount,
            })

        if errors and not resolved_items:
            return "❌ None of the items were found:\n" + "\n".join(errors)

        # Build summary
        grand_total = round(sum(it["amount"] for it in resolved_items), 2)
        summary_lines = []
        for it in resolved_items:
            summary_lines.append(
                f"• *{it['quantity']}x {it['item_name']}* — "
                f"MRP ₹{it['mrp']} = ₹{it['amount']}"
            )
        summary_lines.append(f"\n*Grand total: ₹{grand_total}*")
        if errors:
            summary_lines.append("\n⚠ Skipped (not found):")
            summary_lines.extend(errors)
        summary = "\n".join(summary_lines)

        _save_pending(sender, {
            "type": "multi_sell",
            "items": resolved_items,
            "grand_total": grand_total,
            "summary": summary,
        })

        return f"🛒 Confirm sale:\n\n{summary}\n\nReply *YES* to confirm or *NO* to cancel."

    def _confirm_sale(self, sender: str, action: dict) -> str:
        """Execute the sale: deduct stock + record transaction + generate receipt."""
        item_id = action["item_id"]
        qty = action["quantity"]
        mrp = action["mrp"]
        amount = action["amount"]
        item_name = action["item_name"]

        # 1. Deduct stock
        updated = inventory_repo.deduct_stock(item_id, qty)
        if updated is None:
            return (
                f"❌ Cannot complete sale – *{item_name}* has insufficient stock.\n"
                "Check current stock with: *stock belladonna*"
            )

        remaining = updated.get("quantity", 0)

        # 2. Record transaction
        txn = transactions_repo.create_transaction({
            "type": "sale",
            "sender": sender,
            "items": [{
                "name": item_name,
                "quantity": qty,
                "mrp": mrp,
                "amount": amount,
            }],
            "total": amount,
        })
        txn_id = txn.get("id", "")

        # 3. Generate receipt HTML + upload to blob
        receipt_url = ""
        try:
            html = generate_receipt_html(
                txn_id=txn_id,
                items=[{
                    "name": item_name,
                    "quantity": qty,
                    "mrp": mrp,
                    "amount": amount,
                }],
                total=amount,
                timestamp=txn.get("created_at", ""),
            )
            receipt_url = upload_receipt(html, sender, txn_id)
        except Exception:
            logger.exception("Receipt generation failed")

        # 4. Build reply
        lines = [
            "✅ Sale recorded!",
            "",
            f"*{item_name}*",
            f"Qty sold: {qty}",
            f"MRP: ₹{mrp}",
            f"Total: ₹{amount}",
            f"Remaining stock: {remaining}",
        ]
        if receipt_url:
            lines.append(f"\n🧾 Receipt: {receipt_url}")

        return "\n".join(lines)

    def _confirm_multi_sale(self, sender: str, action: dict) -> str:
        """Execute a multi-item sale: deduct stock for each, record transaction, generate receipt."""
        items = action.get("items", [])
        grand_total = action.get("grand_total", 0)

        # 1. Deduct stock for each item
        sale_items = []   # items that succeeded
        reply_lines = ["\u2705 Sale recorded!", ""]
        failed = []

        for it in items:
            updated = inventory_repo.deduct_stock(it["item_id"], it["quantity"])
            if updated is None:
                failed.append(it["item_name"])
                continue
            remaining = updated.get("quantity", 0)
            sale_items.append(it)
            reply_lines.append(
                f"\u2022 *{it['item_name']}* — {it['quantity']} x \u20b9{it['mrp']} = \u20b9{it['amount']}  (remaining: {remaining})"
            )

        if not sale_items:
            return "\u274c Could not complete sale \u2014 all items have insufficient stock."

        actual_total = round(sum(it["amount"] for it in sale_items), 2)
        reply_lines.append(f"\n*Total: \u20b9{actual_total}*")

        if failed:
            reply_lines.append("\n\u26a0 Skipped (insufficient stock): " + ", ".join(failed))

        # 2. Record transaction
        txn = transactions_repo.create_transaction({
            "type": "sale",
            "sender": sender,
            "items": [
                {"name": it["item_name"], "quantity": it["quantity"],
                 "mrp": it["mrp"], "amount": it["amount"]}
                for it in sale_items
            ],
            "total": actual_total,
        })
        txn_id = txn.get("id", "")

        # 3. Generate receipt HTML + upload to blob
        receipt_url = ""
        try:
            html = generate_receipt_html(
                txn_id=txn_id,
                items=[
                    {"name": it["item_name"], "quantity": it["quantity"],
                     "mrp": it["mrp"], "amount": it["amount"]}
                    for it in sale_items
                ],
                total=actual_total,
                timestamp=txn.get("created_at", ""),
            )
            receipt_url = upload_receipt(html, sender, txn_id)
        except Exception:
            logger.exception("Receipt generation failed")

        if receipt_url:
            reply_lines.append(f"\n\U0001f9fe Receipt: {receipt_url}")

        return "\n".join(reply_lines)

    # ------------------------------------------------------------------
    #  Add stock flow
    # ------------------------------------------------------------------

    def _initiate_add(self, sender: str, entities: dict) -> str:
        name = entities.get("name") or entities.get("medicine_name") or ""
        qty = int(entities.get("quantity") or entities.get("qty") or 0)
        mrp = float(entities.get("mrp") or entities.get("price") or entities.get("unit_price") or 0)
        batch = entities.get("batch_no") or entities.get("batch") or ""
        expiry = entities.get("expiry_date") or entities.get("expiry") or ""

        if not name:
            return "Please specify the item name. Example: *add 50 belladonna at ₹120*"
        if qty <= 0:
            return "Please specify a quantity. Example: *add 50 belladonna at ₹120*"

        summary = f"Add *{qty}x {name}*"
        if mrp:
            summary += f" @ MRP ₹{mrp}"
        if batch:
            summary += f" (Batch: {batch})"
        if expiry:
            summary += f" (Exp: {expiry})"

        _save_pending(sender, {
            "type": "add",
            "item_name": name,
            "quantity": qty,
            "mrp": mrp,
            "batch_no": batch,
            "expiry_date": expiry,
            "summary": summary,
        })

        return f"📦 Confirm add:\n\n{summary}\n\nReply *YES* to confirm or *NO* to cancel."

    def _confirm_add(self, sender: str, action: dict) -> str:
        """Execute the add: upsert or create inventory item."""
        name = action["item_name"]
        qty = action["quantity"]
        mrp = action.get("mrp", 0)
        batch = action.get("batch_no", "")
        expiry = action.get("expiry_date", "")

        # See if item already exists
        matches = inventory_repo.search_by_name(name)
        if matches:
            doc = matches[0]
            doc["quantity"] = doc.get("quantity", 0) + qty
            if mrp:
                doc["mrp"] = mrp
            if batch:
                doc["batch_no"] = batch
            if expiry:
                doc["expiry_date"] = expiry
            inventory_repo.upsert_item(doc)
            return (
                f"✅ Stock updated!\n"
                f"*{doc['name']}* now has *{doc['quantity']}* units."
            )

        # New item
        item_id = name.lower().replace(" ", "_")
        inventory_repo.upsert_item({
            "id": item_id,
            "name": name,
            "quantity": qty,
            "mrp": mrp,
            "batch_no": batch,
            "expiry_date": expiry,
            "category": "",
        })
        return (
            f"✅ New item added!\n"
            f"*{name}* — {qty} units @ MRP ₹{mrp}"
        )

    # ------------------------------------------------------------------
    #  Delete flow
    # ------------------------------------------------------------------

    def _initiate_delete(self, sender: str, entities: dict) -> str:
        name = entities.get("name") or entities.get("medicine_name") or ""
        if not name:
            return "Please specify which item to delete."

        item = self._resolve_item_direct(name)
        if item is None:
            return f"❌ No item matching *{name}* found in inventory."
        summary = f"Delete *{item['name']}* from inventory"

        _save_pending(sender, {
            "type": "delete",
            "item_id": item["id"],
            "item_name": item["name"],
            "summary": summary,
        })

        return f"🗑 Confirm:\n\n{summary}\n\nReply *YES* to confirm or *NO* to cancel."

    def _confirm_delete(self, sender: str, action: dict) -> str:
        ok = inventory_repo.delete_item(action["item_id"])
        if ok:
            return f"✅ *{action['item_name']}* deleted from inventory."
        return f"❌ Could not delete *{action['item_name']}* — item not found."

    # ------------------------------------------------------------------
    #  Update item flow (e.g. update MRP, price, batch, expiry)
    # ------------------------------------------------------------------

    def _initiate_update(self, sender: str, entities: dict) -> str:
        name = entities.get("name") or entities.get("medicine_name") or ""
        if not name:
            return "Please specify which item to update. Example: *update mrp of belladonna to 170*"

        item = self._resolve_item_direct(name)
        if item is None:
            return f"❌ No item matching *{name}* found in inventory."

        # Gather fields to update
        updates = {}
        for key, aliases in [
            ("mrp", ["mrp", "price", "unit_price"]),
            ("batch_no", ["batch_no", "batch"]),
            ("expiry_date", ["expiry_date", "expiry"]),
            ("quantity", ["quantity", "qty"]),
        ]:
            for alias in aliases:
                val = entities.get(alias)
                if val is not None and val != "" and val != 0:
                    updates[key] = val
                    break

        if not updates:
            return (
                "Please specify what to update. Example:\n"
                "*update mrp of belladonna to 170*\n"
                "*change price of aspirin to 50*"
            )

        summary_parts = [f"{k}: {v}" for k, v in updates.items()]
        summary = f"Update *{item['name']}*\n" + "\n".join(f"• {p}" for p in summary_parts)

        _save_pending(sender, {
            "type": "update",
            "item_id": item["id"],
            "item_name": item["name"],
            "updates": updates,
            "summary": summary,
        })

        return f"✏️ Confirm update:\n\n{summary}\n\nReply *YES* to confirm or *NO* to cancel."

    def _confirm_update(self, sender: str, action: dict) -> str:
        """Apply field updates to an inventory item."""
        item_id = action["item_id"]
        item_name = action["item_name"]
        updates = action.get("updates", {})

        doc = inventory_repo.get_item_by_id(item_id)
        if doc is None:
            return f"❌ *{item_name}* not found in inventory."

        for key, val in updates.items():
            if key in ("mrp", "quantity"):
                doc[key] = float(val)
            else:
                doc[key] = val

        inventory_repo.upsert_item(doc)
        return f"✅ *{item_name}* updated successfully!\n" + "\n".join(
            f"• {k} → {v}" for k, v in updates.items()
        )

    # ------------------------------------------------------------------
    #  Query stock (no confirmation needed)
    # ------------------------------------------------------------------

    def _query_stock(self, entities: dict) -> str:
        name = entities.get("name") or entities.get("medicine_name") or ""
        if not name:
            # Return a summary of all inventory
            items = inventory_repo.list_all(limit=20)
            if not items:
                return "📦 Inventory is empty."
            lines = ["📦 *Current Inventory*"]
            lines.append("─" * 28)
            for idx, it in enumerate(items, 1):
                qty = it.get('quantity', 0)
                mrp = it.get('mrp', 0)
                batch = it.get('batch_no', '')
                expiry = it.get('expiry_date', '')
                total_val = round(qty * mrp, 2)
                lines.append(f"*{idx}. {it['name']}*")
                lines.append(f"   Qty: {qty}  |  MRP: \u20b9{mrp}")
                if batch or expiry:
                    lines.append(f"   Batch: {batch or 'N/A'}  |  Exp: {expiry or 'N/A'}")
                lines.append(f"   Stock value: ₹{total_val}")
                lines.append("")
            return "\n".join(lines)

        # Specific item query — try exact then fuzzy
        item = self._resolve_item_direct(name)
        if item is None:
            return f"No item matching *{name}* found in inventory."

        qty = item.get('quantity', 0)
        mrp = item.get('mrp', 0)
        total_val = round(qty * mrp, 2)
        return (
            f"📦 *{item['name']}*\n"
            f"────────────────────\n"
            f"  Stock:      {qty} units\n"
            f"  MRP:        ₹{mrp}\n"
            f"  Batch:      {item.get('batch_no') or 'N/A'}\n"
            f"  Expiry:     {item.get('expiry_date') or 'N/A'}\n"
            f"────────────────────\n"
            f"  Stock value: ₹{total_val}"
        )

    # ------------------------------------------------------------------
    #  Confirm dispatcher
    # ------------------------------------------------------------------

    def _confirm(self, sender: str, action: dict) -> str:
        action_type = action.get("type")
        _clear_pending(sender)

        if action_type == "sell":
            return self._confirm_sale(sender, action)
        if action_type == "multi_sell":
            return self._confirm_multi_sale(sender, action)
        if action_type == "add":
            return self._confirm_add(sender, action)
        if action_type == "delete":
            return self._confirm_delete(sender, action)
        if action_type == "update":
            return self._confirm_update(sender, action)
        if action_type == "fuzzy_confirm":
            return self._confirm_fuzzy(sender, action)

        return "Unknown pending action."

    # ------------------------------------------------------------------
    #  Fuzzy item resolution helpers
    # ------------------------------------------------------------------

    def _confirm_fuzzy(self, sender: str, action: dict) -> str:
        """
        User confirmed a fuzzy name match.  Re-dispatch the original intent
        using the corrected item name.
        """
        resolved_name = action.get("resolved_name", "")
        original_intent = action.get("original_intent", "")
        entities = dict(action.get("original_entities", {}))

        # Patch the entity name to the resolved (correct) name
        entities["name"] = resolved_name

        if original_intent and original_intent in (
            "sell_item", "add_item", "delete_item", "update_item", "query_stock"
        ):
            return self.handle_intent(sender, original_intent, entities)

        # Fallback: just confirm the name was found
        return f"✅ Matched *{resolved_name}*. Please repeat your request using this name."

    @staticmethod
    def _resolve_item_direct(name: str) -> dict | None:
        """
        Try exact DB search first; if nothing, try fuzzy.
        Returns the best-match doc, or None.
        """
        matches = inventory_repo.search_by_name(name)
        if matches:
            return matches[0]
        fuzzy = inventory_repo.fuzzy_search(name)
        if fuzzy:
            return fuzzy[0]
        return None

    def _resolve_item(self, sender: str, name: str,
                      intent: str = "", entities: dict | None = None) -> dict | str | None:
        """
        Look up an item by name with fuzzy fallback.

        Returns:
          - dict   → matched item (caller proceeds)
          - str    → message to send back (caller returns it)
          - None   → fuzzy "did you mean?" confirmation saved (caller returns "")
        """
        # 1. Exact / contains match
        matches = inventory_repo.search_by_name(name)
        if matches:
            return matches[0]

        # 2. Fuzzy match
        fuzzy = inventory_repo.fuzzy_search(name)
        if not fuzzy:
            return f"❌ No item matching *{name}* found in inventory."

        # Offer the best fuzzy match for confirmation
        best = fuzzy[0]
        _save_pending(sender, {
            "type": "fuzzy_confirm",
            "original_name": name,
            "resolved_name": best["name"],
            "resolved_id": best["id"],
            "original_intent": intent,
            "original_entities": entities or {},
            "summary": f"Did you mean *{best['name']}*?",
        })
        return f"🔍 Did you mean *{best['name']}*?\n\nReply *YES* to confirm or *NO* to cancel."

    # ------------------------------------------------------------------
    #  Seed inventory from a confirmed invoice (called by InvoiceService)
    # ------------------------------------------------------------------

    @staticmethod
    def seed_from_invoice(invoice: dict):
        """
        After an invoice is CONFIRMED, add its items to inventory.
        If an item already exists (by name match), increase quantity.
        """
        for item in invoice.get("items", []):
            name = item.get("description", {}).get("value", "")
            qty = int(item.get("quantity", {}).get("value") or 0)
            price = float(item.get("unit_price", {}).get("value") or 0)
            mrp = float(item.get("mrp", {}).get("value") or 0)
            # If OCR didn't extract MRP, default to unit_price
            if not mrp and price:
                mrp = price
            batch = item.get("batch_no", {}).get("value", "")
            expiry = item.get("expiry_date", {}).get("value", "")

            if not name or qty <= 0:
                continue

            matches = inventory_repo.search_by_name(name)
            if matches:
                doc = matches[0]
                doc["quantity"] = doc.get("quantity", 0) + qty
                if mrp:
                    doc["mrp"] = mrp
                if batch:
                    doc["batch_no"] = batch
                if expiry:
                    doc["expiry_date"] = expiry
                inventory_repo.upsert_item(doc)
            else:
                item_id = name.lower().replace(" ", "_").replace("/", "_")[:64]
                inventory_repo.upsert_item({
                    "id": item_id,
                    "name": name,
                    "quantity": qty,
                    "mrp": mrp,
                    "batch_no": batch,
                    "expiry_date": expiry,
                    "category": "",
                })
        logger.info("Inventory seeded from invoice (%d items)", len(invoice.get("items", [])))
