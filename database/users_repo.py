"""
Users Repository – tracks seen WhatsApp users in Cosmos DB.

Each document::

    {
        "id":          "whatsapp:+91...",
        "first_seen":  "<ISO timestamp>"
    }

Partition key: ``/id``
"""
import logging
import os
from datetime import datetime, timezone

from azure.cosmos import PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from database.cosmos_client import get_container, get_database

logger = logging.getLogger(__name__)

CONTAINER = os.environ.get("COSMOS_CONTAINER_USERS", "users")

_container = None


def _ctr():
    """Return the users container, creating it on first access if needed."""
    global _container
    if _container is None:
        try:
            c = get_container(CONTAINER)
            c.read()  # verify it actually exists
            _container = c
        except CosmosResourceNotFoundError:
            logger.info("Container '%s' not found – creating it.", CONTAINER)
            db = get_database()
            _container = db.create_container_if_not_exists(
                id=CONTAINER,
                partition_key=PartitionKey(path="/id"),
            )
    return _container


def is_new_user(sender: str) -> bool:
    """Return True if *sender* has never been seen before, and register them."""
    try:
        _ctr().read_item(sender, partition_key=sender)
        return False
    except CosmosResourceNotFoundError:
        _ctr().upsert_item({
            "id": sender,
            "first_seen": datetime.now(timezone.utc).isoformat(),
        })
        return True
