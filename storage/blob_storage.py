"""
Blob Storage - Azure Blob Storage integration for file uploads/downloads.

Extracted from legacy_reference/function_app.py (blob_save_invoice_image).
Handles invoice image uploads and general blob operations.
"""
import logging
import os
import uuid

from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


class BlobStorage:
    """Wrapper for Azure Blob Storage operations."""

    def __init__(self):
        self.connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
        self.container_name = os.environ.get("BLOB_CONTAINER_NAME", "invoices")
        self._client = None

    def _get_client(self) -> BlobServiceClient:
        """Get or create the Blob Service client (lazy init)."""
        if self._client is None:
            logger.info("Initializing Blob Storage client.")
            self._client = BlobServiceClient.from_connection_string(self.connection_string)
        return self._client

    # ------------------------------------------------------------------
    #  Invoice-specific upload
    # ------------------------------------------------------------------

    def upload_invoice_image(self, image_bytes: bytes, sender: str) -> str:
        """
        Upload an invoice image to blob storage.

        Path convention: {sender_sanitised}/{uuid}.jpg
        Returns the public blob URL (used by Document Intelligence).

        Extracted from legacy blob_save_invoice_image().
        """
        sanitised_sender = sender.replace(":", "")
        blob_name = f"{sanitised_sender}/{uuid.uuid4()}.jpg"
        logger.info("Uploading invoice image as blob: %s", blob_name)

        client = self._get_client()
        blob_client = client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        blob_client.upload_blob(image_bytes, overwrite=True)
        return blob_client.url

    # ------------------------------------------------------------------
    #  Generic blob operations
    # ------------------------------------------------------------------

    def upload_file(self, file_data: bytes, blob_name: str) -> str:
        """
        Upload arbitrary file data and return the blob URL.
        """
        logger.info("Uploading blob: %s", blob_name)
        client = self._get_client()
        blob_client = client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        blob_client.upload_blob(file_data, overwrite=True)
        return blob_client.url

    def download_file(self, blob_name: str) -> bytes:
        """
        Download a blob and return its bytes.
        """
        logger.info("Downloading blob: %s", blob_name)
        client = self._get_client()
        blob_client = client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        download = blob_client.download_blob()
        return download.readall()

    def delete_file(self, blob_name: str) -> bool:
        """
        Delete a blob.
        """
        logger.info("Deleting blob: %s", blob_name)
        client = self._get_client()
        blob_client = client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        blob_client.delete_blob()
        return True
