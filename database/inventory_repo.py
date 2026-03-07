"""
Inventory Repository – CRUD for the *inventory* Cosmos container.

Each document represents a medicine/product in stock::

    {
        "id":          "<auto or medicine_name_normalised>",
        "name":        "Belladonna 30C",
        "name_lower":  "belladonna 30c",
        "quantity":    50,
        "unit_price":  120.0,
        "mrp":         150.0,
        "batch_no":    "B-2024-001",
        "expiry_date": "03-2026",
        "category":    "Homeopathy",
        "updated_at":  "<ISO timestamp>"
    }

Partition key: ``/id``
"""
import logging
import os
from datetime import datetime, timezone
from difflib import SequenceMatcher

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from database.cosmos_client import get_container

logger = logging.getLogger(__name__)

CONTAINER = os.environ.get("COSMOS_CONTAINER_INVENTORY", "inventory")


def _ctr():
    return get_container(CONTAINER)


# ------------------------------------------------------------------
#  Read helpers
# ------------------------------------------------------------------

def get_item_by_id(item_id: str) -> dict | None:
    """Fetch a single inventory item, or *None* if not found."""
    try:
        return _ctr().read_item(item_id, partition_key=item_id)
    except CosmosResourceNotFoundError:
        return None


def search_by_name(name: str, limit: int = 10) -> list[dict]:
    """Case-insensitive CONTAINS search on name_lower."""
    query = (
        "SELECT * FROM c WHERE CONTAINS(c.name_lower, @term) "
        "OFFSET 0 LIMIT @lim"
    )
    params = [
        {"name": "@term", "value": name.strip().lower()},
        {"name": "@lim", "value": limit},
    ]
    return list(_ctr().query_items(query, parameters=params, enable_cross_partition_query=True))


def fuzzy_search(name: str, threshold: float = 0.55, limit: int = 5) -> list[dict]:
    """
    Fuzzy search: fetch all items then rank by string similarity.

    Uses ``difflib.SequenceMatcher`` so no extra dependencies needed.
    Returns items whose similarity ratio >= *threshold*, sorted best-first.
    """
    term = name.strip().lower()
    all_items = list_all(limit=200)
    scored = []
    for doc in all_items:
        doc_name = doc.get("name_lower", doc.get("name", "").lower())
        ratio = SequenceMatcher(None, term, doc_name).ratio()
        if ratio >= threshold:
            scored.append((ratio, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:limit]]


def list_all(limit: int = 50) -> list[dict]:
    """Return up to *limit* inventory items."""
    query = "SELECT * FROM c OFFSET 0 LIMIT @lim"
    params = [{"name": "@lim", "value": limit}]
    return list(_ctr().query_items(query, parameters=params, enable_cross_partition_query=True))


def get_low_stock(threshold: int = 10) -> list[dict]:
    """Return items whose quantity is below *threshold*."""
    query = "SELECT * FROM c WHERE c.quantity < @thr"
    params = [{"name": "@thr", "value": threshold}]
    return list(_ctr().query_items(query, parameters=params, enable_cross_partition_query=True))


def get_expiring_items(within_days: int = 30) -> list[dict]:
    """
    Return items whose expiry_date falls within *within_days* from today.

    Expiry dates are stored as strings like ``"03-2026"`` (MM-YYYY) or
    ``"03/2026"`` or ``"2026-03"``.  We parse them, treat as last day of
    that month, and compare against today + within_days.
    """
    from datetime import timedelta
    import calendar
    import re

    cutoff = datetime.now(timezone.utc).date() + timedelta(days=within_days)
    today = datetime.now(timezone.utc).date()
    all_items = list_all(limit=500)
    results = []

    for doc in all_items:
        raw = (doc.get("expiry_date") or "").strip()
        if not raw:
            continue
        parsed = _parse_expiry(raw)
        if parsed is None:
            continue
        if parsed <= cutoff:
            doc["_expiry_parsed"] = parsed.isoformat()
            doc["_expired"] = parsed < today
            results.append(doc)

    results.sort(key=lambda d: d.get("_expiry_parsed", ""))
    return results


def _parse_expiry(raw: str):
    """Parse common expiry date formats into a date (last day of month)."""
    import calendar
    import re

    raw = raw.strip()
    # MM-YYYY  or  MM/YYYY
    m = re.match(r"^(\d{1,2})[\-/](\d{4})$", raw)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, last_day, tzinfo=timezone.utc).date()
    # YYYY-MM
    m = re.match(r"^(\d{4})[\-/](\d{1,2})$", raw)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, last_day, tzinfo=timezone.utc).date()
    return None


# ------------------------------------------------------------------
#  Write helpers
# ------------------------------------------------------------------

def upsert_item(doc: dict) -> dict:
    """Insert or replace an inventory document (must include ``id``)."""
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc.setdefault("name_lower", doc.get("name", "").lower())
    return _ctr().upsert_item(doc)


def add_stock(item_id: str, qty: int) -> dict | None:
    """Increase stock for an existing item. Returns updated doc or None."""
    doc = get_item_by_id(item_id)
    if doc is None:
        return None
    doc["quantity"] = doc.get("quantity", 0) + qty
    return upsert_item(doc)


def deduct_stock(item_id: str, qty: int) -> dict | None:
    """
    Decrease stock for an existing item.
    Returns updated doc, or None if item not found or insufficient stock.
    """
    doc = get_item_by_id(item_id)
    if doc is None:
        return None
    current = doc.get("quantity", 0)
    if current < qty:
        return None          # caller should interpret as "insufficient stock"
    doc["quantity"] = current - qty
    return upsert_item(doc)


def delete_item(item_id: str) -> bool:
    """Delete an inventory item. Returns True on success."""
    try:
        _ctr().delete_item(item_id, partition_key=item_id)
        return True
    except CosmosResourceNotFoundError:
        return False
