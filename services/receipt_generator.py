"""
Receipt Generator – Builds a styled HTML receipt and uploads it to Azure Blob
Storage so the pharmacist receives a clickable link on WhatsApp.

The HTML is self-contained (inline CSS) so it renders correctly in any browser.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from storage.blob_storage import BlobStorage

logger = logging.getLogger(__name__)

_blob: BlobStorage | None = None


def _get_blob() -> BlobStorage:
    global _blob
    if _blob is None:
        _blob = BlobStorage()
    return _blob


# ------------------------------------------------------------------
#  HTML template
# ------------------------------------------------------------------

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Receipt #{txn_id_short}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 480px; margin: 20px auto; padding: 0 16px; color: #222; }}
  h1 {{ text-align: center; font-size: 1.4em; margin-bottom: 4px; }}
  .subtitle {{ text-align: center; color: #666; font-size: 0.85em; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
  th, td {{ padding: 6px 8px; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #f5f5f5; font-size: 0.85em; text-transform: uppercase; }}
  .right {{ text-align: right; }}
  .total-row td {{ font-weight: bold; border-top: 2px solid #333; }}
  .footer {{ text-align: center; color: #888; font-size: 0.75em; margin-top: 20px; }}
</style>
</head>
<body>
<h1>🧾 Sale Receipt</h1>
<p class="subtitle">ID: {txn_id}<br>{timestamp}</p>
<table>
  <thead>
    <tr><th>Item</th><th class="right">Qty</th><th class="right">Unit ₹</th><th class="right">Amount ₹</th></tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
  <tfoot>
    <tr class="total-row"><td colspan="3">Total</td><td class="right">₹{total}</td></tr>
  </tfoot>
</table>
<p class="footer">PharmaBot – AI Pharmacy Assistant</p>
</body>
</html>
"""


def generate_receipt_html(
    txn_id: str,
    items: list[dict],
    total: float,
    timestamp: str = "",
) -> str:
    """Return a complete HTML string for the receipt."""
    if not timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for it in items:
        rows.append(
            f"<tr>"
            f"<td>{it.get('name', '')}</td>"
            f"<td class='right'>{it.get('quantity', 0)}</td>"
            f"<td class='right'>{it.get('unit_price', 0)}</td>"
            f"<td class='right'>{it.get('amount', 0)}</td>"
            f"</tr>"
        )

    return _TEMPLATE.format(
        txn_id=txn_id,
        txn_id_short=txn_id[:8],
        timestamp=timestamp,
        rows="\n    ".join(rows),
        total=total,
    )


def upload_receipt(html: str, sender: str, txn_id: str) -> str:
    """
    Upload receipt HTML to blob storage and return the public URL.

    Blob path: ``receipts/{sender_clean}/{txn_id}.html``
    """
    from azure.storage.blob import ContentSettings

    blob = _get_blob()
    sender_clean = sender.replace("whatsapp:", "").replace("+", "")
    blob_name = f"receipts/{sender_clean}/{txn_id}.html"

    client = blob._get_client()
    blob_client = client.get_blob_client(
        container=blob.container_name, blob=blob_name
    )
    blob_client.upload_blob(
        html.encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="text/html"),
    )
    url = blob_client.url
    logger.info("Receipt uploaded: %s", url)
    return url
