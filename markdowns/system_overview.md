# System Overview

This project builds a WhatsApp-based pharmacy AI assistant.

Users interact through WhatsApp.

Three pipelines exist:

Invoice Pipeline (Stock-In)
Image → OCR → Inventory update

Voice Billing Pipeline (Stock-Out)
Voice → Speech-to-text → JSON → Billing engine

Natural Language Queries
Text → Intent parser → Inventory lookup

The backend runs on Azure Functions.

Cosmos DB stores inventory and transactions.

Azure Blob Storage stores invoice images and generated bills.
