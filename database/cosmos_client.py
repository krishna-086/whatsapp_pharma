"""
Cosmos Client - Azure Cosmos DB client initialization and configuration.
"""
import logging
import os
from azure.cosmos import CosmosClient, PartitionKey

logger = logging.getLogger(__name__)


class CosmosDBClient:
    """Singleton-style wrapper for Azure Cosmos DB client."""

    _instance = None

    def __init__(self):
        self.endpoint = os.environ.get("COSMOS_DB_ENDPOINT", "")
        self.key = os.environ.get("COSMOS_DB_KEY", "")
        self.database_name = os.environ.get("COSMOS_DB_DATABASE", "pharmacy")
        self._client = None
        self._database = None

    def get_client(self) -> CosmosClient:
        """Get or create the Cosmos DB client."""
        if self._client is None:
            logger.info("Initializing Cosmos DB client.")
            self._client = CosmosClient(self.endpoint, credential=self.key)
        return self._client

    def get_database(self):
        """Get or create the database reference."""
        if self._database is None:
            client = self.get_client()
            self._database = client.get_database_client(self.database_name)
        return self._database

    def get_container(self, container_name: str):
        """Get a container reference by name."""
        database = self.get_database()
        return database.get_container_client(container_name)
