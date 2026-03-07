"""
Cosmos Client – Shared Azure Cosmos DB client initialisation.

Uses the same env vars as the rest of the project:
  COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DB
"""
import logging
import os

from azure.cosmos import CosmosClient

logger = logging.getLogger(__name__)

# Module-level singleton
_client: CosmosClient | None = None
_database = None


def _init():
    global _client, _database
    if _client is None:
        endpoint = os.environ.get("COSMOS_ENDPOINT", "")
        key = os.environ.get("COSMOS_KEY", "")
        db_name = os.environ.get("COSMOS_DB", "pharmagent")
        _client = CosmosClient(endpoint, key)
        _database = _client.get_database_client(db_name)
        logger.info("CosmosDBClient initialised (db=%s)", db_name)


def get_container(name: str):
    """Return a container client by name (lazily initialises the DB)."""
    _init()
    return _database.get_container_client(name)


def get_database():
    """Return the database client (lazily initialises the DB)."""
    _init()
    return _database
