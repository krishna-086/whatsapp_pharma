# Code Migration Context

This project previously had a working invoice OCR pipeline implemented in a single file.

File location:
legacy_reference/ocr_pipeline_reference.py

The pipeline already performs the following tasks:

1. Receive WhatsApp webhook request
2. Download invoice image from Twilio
3. Upload image to Azure Blob Storage
4. Send image to Azure Document Intelligence
5. Extract invoice fields and medicine table
6. Normalize pharma fields (expiry, batch, quantity)
7. Save temporary session in Cosmos DB
8. Allow user edits via WhatsApp commands
9. Save confirmed invoice

However the code currently has problems:

* Entire pipeline is implemented in one file
* Business logic mixed with API logic
* Hard to extend for voice billing and NLP queries

The goal is to refactor this logic into the new modular architecture.

New structure:

services/invoice_service.py
ai/document_ai.py
database/inventory_repo.py
storage/blob_storage.py
messaging/twilio_service.py

The refactored code should reuse the existing invoice extraction logic but move responsibilities into appropriate modules.
