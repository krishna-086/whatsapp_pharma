# 💊 WhatsApp PharmAgent — AI Pharmacy Assistant
<p align="center">

<a href="https://your-dashboard-link">
<img src="https://img.shields.io/badge/Web%20Dashboard-Live-blue?style=for-the-badge&logo=vercel">
</a>

<a href="https://wa.me/14155238886?text=join%20be-continued">
<img src="https://img.shields.io/badge/WhatsApp%20Bot-Open%20Chat-25D366?style=for-the-badge&logo=whatsapp">
</a>

<a href="https://your-function-app.azurewebsites.net/api/whatsapp_webhook">
<img src="https://img.shields.io/badge/Azure%20Function-API-blue?style=for-the-badge&logo=microsoftazure">
</a>

</p>
An AI-powered WhatsApp chatbot for pharmacy inventory management, built on **Azure Functions** and integrated with **Azure AI services**. Pharmacists can manage stock, process invoices, record sales, and query inventory — all through WhatsApp text, voice notes, or invoice images.

---

## 📖 Table of Contents

- [Project Overview](#-project-overview)
- [System Architecture](#-system-architecture)
- [Features](#-features)
- [Technologies Used](#-technologies-used)
- [Azure Services Used](#-azure-services-used)
- [Project Folder Structure](#-project-folder-structure)
- [How the System Works](#-how-the-system-works)
- [Setup Instructions](#-setup-instructions-local-development)
- [Environment Variables Required](#-environment-variables-required)
- [Running the Project Locally](#-running-the-project-locally)
- [Connecting the Twilio Webhook](#-connecting-the-twilio-webhook)
- [Deployment to Azure](#-deployment-to-azure)
- [Example Usage](#-example-usage)
- [Future Improvements](#-future-improvements)

---

## 🧭 Project Overview

**WhatsApp PharmAgent** is a conversational AI system that enables pharmacists to manage their day-to-day inventory operations entirely through WhatsApp. Instead of using desktop software, pharmacists can:

- **Ingest supplier purchase invoices** — Send a photo of a distributor invoice and the system automatically extracts medicine names, quantities, batch numbers, expiry dates, and prices using OCR to add incoming stock.
- **Record sales via voice** — Send a voice note like *"Sold 2 Dolo and 1 Paracetamol"* and the system transcribes it, classifies the intent, deducts stock, and generates an HTML receipt.
- **Query inventory via text** — Ask questions like *"How many Dolo left?"* or *"Show all stock"* and get instant responses.
- **Add, update, or delete stock** — Use natural language commands to manage inventory without touching a database.
- **Mobile-Responsive Dashboard** — A sleek, modern web interface to monitor stock levels, view transaction history, and perform manual billing on the go.

The backend is a serverless **Azure Function** that receives messages via a **Twilio WhatsApp webhook**, routes them through the appropriate AI pipeline, and sends responses back through WhatsApp.

---

## 🏗 System Architecture

This system follows an **agentic, event-driven architecture** where **Azure Functions** is the serverless orchestration entry point.

When a WhatsApp event arrives from Twilio, the **Master Orchestrator** classifies the input type (image, voice, text, or confirmation command), invokes an **Azure OpenAI reasoning layer** for intent interpretation, and then activates the appropriate specialized agent.

```
                           ┌──────────────────────────┐
                           │       PHARMACIST         │
                           └────────────┬─────────────┘
                                        │
                ┌───────────────────────┴───────────────────────┐
                ▼                                               ▼
      [ WHATSAPP CHANNEL ]                            [ WEB DASHBOARD ]
        Text / Voice / Img                              Next.js (React)
                │                                               │
                ▼                                               ▼
      ┌──────────────────┐                            ┌──────────────────┐
      │     TWILIO       │                            │   WEB HOSTING    │
      │  WhatsApp API    │                            │  (App Service)   │
      └─────────┬────────┘                            └─────────┬────────┘
                │                                               │
           { HTTP POST }                                  { HTTPS API }
                │                                               │
                ▼                                               ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │      AZURE FUNCTIONS (MASTER ORCHESTRATOR, EVENT-DRIVEN)         │
   │  1) Detect input type  2) Call reasoning layer  3) Dispatch      │
   └───────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │        REASONING LAYER (AZURE OPENAI - INTENT DECISION)          │
   │     Interprets message intent and selects the execution agent    │
   └───────────────────────────────┬──────────────────────────────────┘
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ INVOICE PROCESSING   │   │      VOICE AGENT     │   │   INVENTORY AGENT    │
│ AGENT                │   │                      │   │                      │
│ • Supplier invoice   │   │ • Speech-to-Text     │   │ • Stock query/update │
│   OCR (Doc Intel)    │   │ • Billing intent     │   │ • Cosmos DB CRUD     │
│ • Stock-in ingestion │   │   to stock-out flow  │   │ • Inventory actions  │
└───────────┬──────────┘   └──────────────────────┘   └───────────┬──────────┘
            │                                                     │
            ▼                                                     ▼
   ┌──────────────────┐                                   ┌──────────────────┐
   │   AZURE BLOB     │                                   │ AZURE COSMOS DB  │
   │    STORAGE       │                                   │     (NoSQL)      │
   │ • Invoice images │                                   │ • Inventory      │
   │ • Voice notes    │                                   │ • Transactions   │
   │ • HTML receipts  │                                   │ • Invoices       │
   └─────────┬────────┘                                   │ • Sessions       │
             │                                            └─────────┬────────┘
             ▼                                                      │
   ┌──────────────────────┐                                         │
   │    RECEIPT AGENT     │◄──────────────────────────   ───────────┘
   │ • Generate receipts  │
   │ • Store in Blob      │
   └──────────────────────┘
```

This architecture keeps the system modular: the orchestrator centralizes control, Azure OpenAI provides reasoning, and each agent executes a focused domain task.

---

## ✨ Features

### 📷 Invoice OCR Pipeline (Stock-In)
- Receive supplier purchase invoice photos via WhatsApp
- Upload images to Azure Blob Storage
- Extract structured data using Azure Document Intelligence (prebuilt-invoice model + table extraction)
- Parse pharma-specific stock fields: batch number, expiry date, manufacturer, MRP, free quantity, HSN code
- Interactive editing via WhatsApp commands (`EDIT 2 qty=10`, `SHOW`, `CONFIRM`)
- Auto-seed inventory on supplier invoice confirmation

### 🎙 Voice Billing Pipeline (Stock-Out)
- Receive WhatsApp voice notes
- Transcribe using Azure Speech-to-Text REST API (supports OGG, MP3, WAV, M4A)
- Classify intent using Azure OpenAI (GPT-4.1)
- Support single-item and multi-item sales in one voice command
- Deduct stock automatically and record transactions
- Generate styled HTML receipts uploaded to Blob Storage

### 💬 Natural Language Queries
- Ask inventory questions in plain English
- Intent classification via Azure OpenAI with structured JSON output
- Supported intents: `sell_item`, `add_item`, `delete_item`, `update_item`, `query_stock`, `general_chat`
- Fuzzy name matching with confirmation ("Did you mean *Belladonna 30C*?")

### 📦 Inventory Management
- Add, update, delete, and query stock via text or voice
- Confirmation flow before destructive actions (YES / NO)
- Pending-action state persisted in Cosmos DB (survives function restarts)
- Low-stock detection

### 🧾 Receipt Generation
- Styled HTML receipts generated for every sale
- Uploaded to Azure Blob Storage with a public URL
- Receipt link sent directly to WhatsApp

---

## 🛠 Technologies Used

| Technology | Purpose |
|---|---|
| **Python 3.11+** | Primary programming language |
| **Azure Functions v4** | Serverless compute (HTTP trigger) |
| **Azure Cosmos DB** | NoSQL database for inventory, transactions, invoices, sessions |
| **Azure Blob Storage** | File storage for invoice images, voice notes, receipts |
| **Azure Document Intelligence** | OCR for invoice image extraction |
| **Azure Speech-to-Text** | Voice note transcription (REST API) |
| **Azure OpenAI (GPT-4.1)** | Intent classification and natural language understanding |
| **Twilio WhatsApp API** | WhatsApp messaging (send/receive) |
| **Pydantic** | Data model validation |
| **Requests** | HTTP calls to Azure REST APIs and Twilio CDN |

---

## ☁️ Azure Services Used

| Azure Service | How It's Used |
|---|---|
| **Azure Functions** | Hosts the HTTP webhook endpoint that receives WhatsApp messages from Twilio |
| **Azure Cosmos DB (NoSQL)** | Stores 4 containers: `inventory` (medicine stock), `transactions` (sale records), `invoices` (confirmed invoices), `sessions` (temporary editing state and pending confirmations) |
| **Azure Blob Storage** | Stores uploaded invoice images, voice note recordings, and generated HTML receipts in the `invoices` container |
| **Azure Document Intelligence** | Analyses invoice images using the `prebuilt-invoice` model with custom table extraction for pharma-specific columns |
| **Azure Cognitive Services — Speech** | Transcribes WhatsApp voice notes to text using the short-audio REST endpoint (up to 60 seconds) |
| **Azure OpenAI Service** | Runs GPT-4.1 for intent classification, entity extraction, and conversational replies |

---

## 📁 Project Folder Structure

```
whatsapp_pharma/
│
├── function_app.py              # Azure Functions entry point (thin – delegates to router)
├── host.json                    # Azure Functions host configuration
├── local.settings.json          # Local environment variables (not committed to git)
├── requirements.txt             # Python dependencies
│
├── web_dashboard/               # Next.js Web Dashboard
│   ├── app/                     
│   │   ├── layout.js            # Root layout (Server Component)
│   │   ├── ClientLayout.js      # Main layout wrapper (Client Component)
│   │   ├── page.js              # Overview dashboard page
│   │   ├── globals.css          # Core design system & responsive styles
│   │   ├── inventory/           # Medicine stock management pages
│   │   ├── transactions/        # Transaction & sales history pages
│   │   ├── invoices/            # Invoice management & OCR review pages
│   │   ├── billing/             # Web-based POS / billing pages
│   │   └── api/                 # Next.js API routes (Cosmos DB proxy)
│   ├── components/              
│   │   ├── Sidebar.js           # Responsive navigation sidebar
│   │   └── Header.js            # Header with mobile menu toggle
│   ├── lib/                     # Cosmos DB clients & PDF generation
│   └── public/                  # Static assets and icons
│
├── api/
│   └── router.py                # Central message dispatcher – routes messages by type
│
├── services/
│   ├── invoice_service.py       # Invoice OCR pipeline orchestrator
│   ├── voice_service.py         # Voice pipeline: download → STT → intent
│   ├── nlp_service.py           # Text intent classification via LLM
│   ├── inventory_service.py     # Stock CRUD: sell, add, delete, update, query
│   ├── billing_service.py       # Billing operations (payment tracking)
│   └── receipt_generator.py     # HTML receipt generation and blob upload
│
├── ai/
│   ├── document_ai.py           # Azure Document Intelligence OCR integration
│   ├── speech_to_text.py        # Azure Speech REST API integration
│   └── llm_parser.py            # Azure OpenAI intent classification and chat
│
├── database/
│   ├── cosmos_client.py         # Shared Cosmos DB client (singleton)
│   ├── inventory_repo.py        # CRUD for the inventory container
│   └── transactions_repo.py     # CRUD for the transactions container
│
├── storage/
│   └── blob_storage.py          # Azure Blob Storage upload/download operations
│
├── messaging/
│   └── twilio_service.py        # Twilio WhatsApp API: parse, send, download media
│
├── models/
│   ├── invoice_model.py         # Pydantic models for invoice data
│   └── billing_model.py         # Pydantic models for billing and transactions
│
├── utils/
│   └── helpers.py               # Utility functions (ID generation, formatting, etc.)
│
└── markdowns/
    ├── project_context.md       # Project goals and architecture overview
    ├── system_overview.md       # High-level system description
    ├── code_migration_context.md # Migration notes from legacy codebase
    └── todo_roadmap.md          # Development roadmap and task tracking
```

---

## ⚙️ How the System Works

### Message Routing

When a WhatsApp message arrives, Twilio sends an HTTP POST to the Azure Function webhook. The router (`api/router.py`) inspects the message and dispatches it:

| Message Type | Detection | Handler |
|---|---|---|
| **Image** | `num_media > 0` and non-audio MIME type | `InvoiceService.process_invoice_image()` |
| **Voice note** | `num_media > 0` and `audio/*` MIME type | `VoiceService.process_voice_message()` |
| **YES / NO** | Text matches confirmation keywords | `InventoryService.handle_confirmation()` |
| **SHOW / OK / EDIT / CONFIRM** | Text matches invoice session commands | `InvoiceService.handle_command()` |
| **Free text** | Everything else | `NLPService.parse_message()` → intent routing |

### Pipeline 1: Invoice OCR (Stock-In)

```
Invoice photo (WhatsApp)
  → Download from Twilio CDN
  → Upload to Azure Blob Storage
  → Send blob URL to Azure Document Intelligence (prebuilt-invoice)
  → Extract vendor info + line items
  → Robust table extraction for pharma fields (batch, expiry, MRP, manufacturer)
  → Fallback: regex scan raw page text for missing batch/expiry
  → Recalculate totals (qty × unit_price)
  → Flag missing fields (⚠ batch missing, ⚠ expiry missing)
  → Save editable session in Cosmos DB (sessions container)
  → User can EDIT fields, SHOW the invoice, or CONFIRM to finalize
  → On CONFIRM: save to invoices container + seed inventory with new stock
```

### Pipeline 2: Voice Billing (Stock-Out)

```
Voice note (WhatsApp)
  → Download audio bytes from Twilio
  → Upload to Azure Blob Storage (voice notes)
  → Transcribe via Azure Speech REST API (OGG/MP3/WAV supported)
  → Send transcript to Azure OpenAI for intent classification
  → If intent = sell_item:
      → Resolve item(s) in inventory (exact match → fuzzy match → "did you mean?")
      → Build confirmation prompt with prices and totals
      → On YES: deduct stock → record transaction → generate HTML receipt → send receipt URL
  → If intent = query_stock / add_item / etc.:
      → Route to appropriate InventoryService handler
```

### Pipeline 3: Natural Language Queries

```
Text message (WhatsApp)
  → Send to Azure OpenAI (GPT-4.1) with pharmacy-specific system prompt
  → LLM returns JSON: { intent, confidence, entities, reply }
  → Router dispatches based on intent:
      • sell_item    → InventoryService (sale flow with confirmation)
      • add_item     → InventoryService (add stock with confirmation)
      • delete_item  → InventoryService (delete with confirmation)
      • update_item  → InventoryService (update fields with confirmation)
      • query_stock  → InventoryService (instant stock lookup)
      • send_invoice → Prompt user to send an image
      • general_chat → Return LLM's conversational reply
```

---

## 🚀 Setup Instructions (Local Development)

### Prerequisites

- **Python 3.11+** installed
- **Azure Functions Core Tools v4** installed ([Install guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local))
- **Azure account** with the following resources provisioned:
  - Azure Cosmos DB (NoSQL API)
  - Azure Storage Account (Blob)
  - Azure Document Intelligence (Form Recognizer)
  - Azure Cognitive Services — Speech
  - Azure OpenAI Service (with GPT-4.1 deployment)
- **Twilio account** with a WhatsApp Sandbox or approved WhatsApp sender
- **ngrok** (for local webhook tunnelling)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/whatsapp_pharma.git
cd whatsapp_pharma
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `local.settings.json` file in the project root (this file is gitignored):

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",

    "AZURE_FORM_RECOGNIZER_ENDPOINT": "https://<your-resource>.cognitiveservices.azure.com/",
    "AZURE_FORM_RECOGNIZER_KEY": "<your-key>",

    "AZURE_STORAGE_CONNECTION_STRING": "<your-connection-string>",
    "BLOB_CONTAINER_NAME": "invoices",

    "COSMOS_ENDPOINT": "https://<your-cosmos>.documents.azure.com:443/",
    "COSMOS_KEY": "<your-cosmos-key>",
    "COSMOS_DB": "pharmagent",
    "COSMOS_CONTAINER_SESSIONS": "sessions",
    "COSMOS_CONTAINER_INVOICES": "invoices",
    "COSMOS_CONTAINER_INVENTORY": "inventory",
    "COSMOS_CONTAINER_TRANSACTIONS": "transactions",

    "TWILIO_ACCOUNT_SID": "<your-twilio-sid>",
    "TWILIO_AUTH_TOKEN": "<your-twilio-auth-token>",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",

    "AZURE_SPEECH_KEY": "<your-speech-key>",
    "AZURE_SPEECH_REGION": "southeastasia",

    "AZURE_OPENAI_ENDPOINT": "https://<your-openai>.cognitiveservices.azure.com/",
    "AZURE_OPENAI_KEY": "<your-openai-key>",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",

    "CONF_THRESHOLD": "0.85"
  }
}
```

### 5. Provision Azure Resources

#### Cosmos DB

Create a Cosmos DB account (NoSQL API) and add these containers (all with partition key `/id`):

| Container | Purpose |
|---|---|
| `inventory` | Medicine stock records |
| `transactions` | Sale/purchase transaction logs |
| `invoices` | Confirmed invoice documents |
| `sessions` | Temporary invoice editing sessions and pending action state |

#### Blob Storage

Create a storage account and a blob container named `invoices` (or your preferred name).

#### Document Intelligence

Create a Document Intelligence resource. The system uses the `prebuilt-invoice` model — no custom training needed.

#### Speech Service

Create a Speech resource in a supported region (e.g., `southeastasia`).

#### Azure OpenAI

Deploy a model (GPT-4.1 recommended) and note the deployment name, endpoint, and key.

---

## 🔑 Environment Variables Required

| Variable | Description |
|---|---|
| `AZURE_FORM_RECOGNIZER_ENDPOINT` | Azure Document Intelligence endpoint URL |
| `AZURE_FORM_RECOGNIZER_KEY` | Document Intelligence API key |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection string |
| `BLOB_CONTAINER_NAME` | Blob container name (default: `invoices`) |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint URL |
| `COSMOS_KEY` | Cosmos DB primary key |
| `COSMOS_DB` | Database name (default: `pharmagent`) |
| `COSMOS_CONTAINER_SESSIONS` | Sessions container name |
| `COSMOS_CONTAINER_INVOICES` | Invoices container name |
| `COSMOS_CONTAINER_INVENTORY` | Inventory container name |
| `COSMOS_CONTAINER_TRANSACTIONS` | Transactions container name |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender number (e.g., `whatsapp:+14155238886`) |
| `AZURE_SPEECH_KEY` | Azure Speech Services API key |
| `AZURE_SPEECH_REGION` | Azure Speech region (e.g., `southeastasia`) |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI model deployment name (e.g., `gpt-4.1`) |
| `CONF_THRESHOLD` | OCR confidence threshold for flagging fields (default: `0.85`) |

---

## ▶️ Running the Project Locally

### 1. Start the Azure Function

```bash
func start
```

The function will start on `http://localhost:7071`. The webhook endpoint will be available at:

```
http://localhost:7071/api/whatsapp_webhook
```

### 2. Expose via ngrok

Twilio needs a publicly accessible URL to send webhook events. Use ngrok to tunnel:

```bash
ngrok http 7071
```

Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok-free.app`).

### 3. Configure Twilio Webhook

Set your Twilio WhatsApp sandbox webhook to:

```
https://abc123.ngrok-free.app/api/whatsapp_webhook
```

(See the [Connecting Twilio Webhook](#-connecting-the-twilio-webhook) section for details.)

---

## 📱 Connecting the Twilio Webhook

1. Go to the [Twilio Console](https://console.twilio.com/)
2. Navigate to **Messaging** → **Try it out** → **Send a WhatsApp message**
3. Follow the instructions to join the WhatsApp sandbox (send the join code from your phone)
4. Under **Sandbox Configuration**, set:
   - **When a message comes in**: `https://<your-ngrok-or-azure-url>/api/whatsapp_webhook`
   - **HTTP Method**: `POST`
5. Save the configuration

Now, any WhatsApp message sent to the sandbox number will be forwarded to your Azure Function.

> **Tip:** For production, apply for a Twilio WhatsApp Business number and configure the webhook in the **Senders** section.

---

---

## 📊 Web Dashboard

The project includes a modern **Next.js Web Dashboard** for real-time inventory monitoring, manual billing, and transaction history.

### Dashboard Features
- **Real-time Stats:** Charts for revenue trends and stock status.
- **Inventory Management:** Full CRUD interface for medicine stock.
- **Manual Billing:** Create new sales directly from the web UI.
- **Transaction History:** View all sales/purchases with detailed item breakdowns.
- **PDF Receipts:** Download professional PDF invoices for any transaction.

### Web Dashboard Setup (Local)
1. Navigate to the dashboard directory:
   ```bash
   cd web_dashboard
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Set up `.env.local`:
   ```env
   COSMOS_ENDPOINT="your-cosmos-url"
   COSMOS_KEY="your-cosmos-key"
   COSMOS_DB="pharmagent"
   ```
4. Run development server:
   ```bash
   npm run dev
   ```

### Web Dashboard Deployment (Azure App Service)
The dashboard is deployed as a **Linux Web App** using the Azure CLI.

1. **Build the project:**
   ```bash
   npm run build
   ```
2. **Deploy via Azure CLI:**
   ```bash
   az webapp up --name <your-app-name> --resource-group <your-rg> --plan <your-plan> --location centralindia
   ```
3. **Configure Environment Variables:**
   In the Azure Portal, go to **Settings** → **Environment variables** and add:
   - `COSMOS_ENDPOINT`
   - `COSMOS_KEY`
   - `COSMOS_DB`

---

## ☁️ Deployment to Azure

### Option 1: Azure Functions Core Tools

```bash
# Login to Azure
az login

# Create a Function App (if not already created)
az functionapp create \
  --resource-group <your-resource-group> \
  --consumption-plan-location <region> \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name <your-function-app-name> \
  --storage-account <your-storage-account>

# Deploy
func azure functionapp publish <your-function-app-name>
```

### Option 2: VS Code

1. Install the **Azure Functions** VS Code extension
2. Sign in to Azure
3. Right-click the project → **Deploy to Function App**
4. Select or create a Function App

### Post-Deployment

1. Set all environment variables in the Azure Function App **Configuration** → **Application settings**
2. Update the Twilio webhook URL to your Azure Function URL:
   ```
   https://<your-function-app>.azurewebsites.net/api/whatsapp_webhook
   ```

---

## 💬 Example Usage

### Sending a Supplier Invoice Image

> **You:** *(send a photo of a supplier purchase invoice from a distributor)*
>
> **PharmAgent:**
> ```
> Supplier invoice received ✅
> Vendor: ABC Pharma Distributors
> Invoice No: INV-2026-1234
> Total: ₹5,420.00
>
> Items:
> 1) Paracetamol 500mg
>    Qty: 100 × MRP ₹25.00 = ₹2,500.00
>    Batch: B-2026-01 | Exp: 03-2027
> 2) Dolo 650
>    Qty: 50 × MRP ₹58.40 = ₹2,920.00
>    Batch: (missing) ⚠ | Exp: 06-2027
>
> Needs confirmation ⚠
> - Item 2 batch missing
>
> Reply: OK | EDIT 2 batch=D-2026-05 | SHOW | CONFIRM
> ```

After `CONFIRM`, the extracted line items are written to the invoices record and added to inventory as incoming stock.

### Voice Sale

> **You:** *(send a voice note: "Sold 2 Dolo and 1 Paracetamol")*
>
> **PharmAgent:**
> ```
> 🎙 "Sold 2 Dolo and 1 Paracetamol."
>
> 🛒 Confirm sale:
>
> • 2x Dolo 650 — MRP ₹58.40 = ₹116.80
> • 1x Paracetamol 500mg — MRP ₹25.00 = ₹25.00
>
> Grand total: ₹141.80
>
> Reply YES to confirm or NO to cancel.
> ```

### Text Query

> **You:** *How much Dolo do we have?*
>
> **PharmAgent:**
> ```
> 📦 Dolo 650
> ────────────────────
>   Stock:      48 units
>   MRP:        ₹58.40
>   Batch:      D-2026-05
>   Expiry:     06-2027
> ────────────────────
>   Stock value: ₹2,803.20
> ```

### Adding Stock

> **You:** *Add 100 Aspirin at ₹12*
>
> **PharmAgent:**
> ```
> 📦 Confirm add:
>
> Add 100x Aspirin @ MRP ₹12.0
>
> Reply YES to confirm or NO to cancel.
> ```

---

## 🔮 Future Improvements

- [ ] **Web Dashboard** — Real-time inventory monitoring UI with charts and alerts
- [ ] **Expiry Alerts** — Automated WhatsApp notifications for medicines nearing expiry
- [ ] **Low-Stock Alerts** — Auto-notify when stock falls below configurable thresholds
- [ ] **PDF Bill Generation** — Generate downloadable PDF bills in addition to HTML receipts
- [ ] **Multi-language Support** — Hindi and regional language support for voice and text
- [ ] **Barcode/QR Scanning** — Scan medicine barcodes via WhatsApp camera for quick lookups
- [ ] **Customer Management** — Track customer purchase history and credit accounts
- [ ] **GST/Tax Reports** — Generate periodic tax reports from transaction data
- [ ] **Role-based Access** — Support multiple staff members with different permission levels
- [ ] **Offline Queue** — Queue messages when Azure services are temporarily unavailable
- [ ] **Analytics & Insights** — Sales trends, fast-moving items, and demand forecasting

---

## 📄 License

This project is for educational and demonstration purposes.

---

<p align="center">
  Built with ❤️ using Azure AI Services, Twilio, and Python
</p>
