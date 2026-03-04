# WhatsApp Pharma AI System – Project Context

## Project Goal

Build a WhatsApp-based AI system for pharmacies that can:

1. Ingest invoices via images and update medicine inventory.
2. Allow pharmacists to sell medicines via voice commands.
3. Answer inventory questions via natural language.
4. Generate bills and update stock automatically.
5. Provide a web dashboard for monitoring inventory.

The system runs on Azure Functions and integrates with Azure AI services.

---

# High-Level Architecture

WhatsApp User
→ Twilio WhatsApp API
→ Azure Function Backend
→ Message Router

The router decides which pipeline to trigger:

1. Image → Invoice OCR pipeline
2. Voice → Billing pipeline
3. Text → Natural language query pipeline

---

# Pipelines

## 1. Invoice Pipeline (Stock-In)

Input: Invoice image from WhatsApp

Flow:
Image → Blob Storage → Azure Document Intelligence → Extract medicines → Update inventory in Cosmos DB

Responsible module:
services/invoice_service.py

---

## 2. Voice Billing Pipeline (Stock-Out)

Input: Voice message like:
"Sold 2 dolo and 1 paracetamol"

Flow:
Voice → Azure Speech-to-Text → LLM parser → JSON items → Billing engine → Reduce inventory → Generate PDF bill

Responsible modules:
services/voice_service.py
services/billing_service.py

---

## 3. Natural Language Queries

Example user queries:
"How many dolo left?"
"Show medicines expiring this month"

Flow:
Text → LLM intent parser → Query Cosmos DB → Return result

Responsible module:
services/nlp_service.py

---

# Database Design

Cosmos DB containers:

inventory

* medicine_name
* batch
* expiry
* quantity
* mrp

transactions

* items
* total
* timestamp
* source (voice/image)

invoices

* vendor
* invoice_number
* items

sessions

* temporary invoice editing

---

# Folder Structure

api/
Handles request routing.

services/
Contains business logic pipelines.

ai/
Handles Azure AI integrations.

database/
Handles Cosmos DB queries.

storage/
Handles Blob Storage uploads.

messaging/
Handles Twilio interactions.

models/
Defines structured objects.

utils/
Helper functions.

---

# Development Principles

1. Keep `function_app.py` minimal. It should only route requests.
2. Business logic must stay in `services/`.
3. AI integrations belong in `ai/`.
4. Database access must go through `database/`.
5. All services should be modular and testable.

---

# Current Status

Completed:

* Azure Function project created
* Folder architecture defined
* Twilio webhook endpoint planned
* Invoice extraction system exists in teammate module

Next steps:

1. Implement router logic.
2. Implement invoice service integration.
3. Implement voice pipeline using Azure Speech.
4. Implement billing engine.
5. Implement NLP query engine.

---

# Expected Flow

WhatsApp message arrives → router detects type → corresponding service runs → response sent via Twilio.
Always reuse logic from legacy_reference when possible instead of rewriting it.