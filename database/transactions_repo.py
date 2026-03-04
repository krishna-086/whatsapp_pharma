"""
Transactions Repository – CRUD for the *transactions* Cosmos container.

Each document represents a sale / purchase transaction::

    {
        "id":           "<uuid>",
        "type":         "sale" | "purchase",
        "sender":       "whatsapp:+91...",
        "items":        [ {name, quantity, unit_price, amount} ],
        "total":        250.0,
        "created_at":   "<ISO timestamp>"
    }

Partition key: ``/id``
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from database.cosmos_client import get_container

logger = logging.getLogger(__name__)

CONTAINER = os.environ.get("COSMOS_CONTAINER_TRANSACTIONS", "transactions")


def _ctr():
    return get_container(CONTAINER)


def create_transaction(data: dict) -> dict:
    """
    Persist a new transaction.

    *data* must contain at minimum ``items`` and ``total``.
    ``id`` is auto-generated if absent.
    """
    data.setdefault("id", str(uuid.uuid4()))
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    return _ctr().upsert_item(data)


def get_transaction(txn_id: str) -> dict | None:
    try:
        return _ctr().read_item(txn_id, partition_key=txn_id)
    except CosmosResourceNotFoundError:
        return None


def get_transactions_by_sender(sender: str, limit: int = 20) -> list[dict]:
    query = "SELECT * FROM c WHERE c.sender = @s ORDER BY c.created_at DESC OFFSET 0 LIMIT @lim"
    params = [
        {"name": "@s", "value": sender},
        {"name": "@lim", "value": limit},
    ]
    return list(_ctr().query_items(query, parameters=params, enable_cross_partition_query=True))
