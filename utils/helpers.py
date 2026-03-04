"""
Helpers - Utility functions used across the application.
"""
import json
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


def get_timestamp() -> str:
    """Get the current UTC timestamp as an ISO string."""
    return datetime.utcnow().isoformat()


def safe_json_loads(text: str) -> dict:
    """Safely parse a JSON string, returning an empty dict on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return {}


def format_currency(amount: float, currency: str = "₹") -> str:
    """Format a number as currency."""
    return f"{currency}{amount:,.2f}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def sanitize_phone_number(phone: str) -> str:
    """Normalize a phone number by removing non-digit characters (except leading +)."""
    if phone.startswith("+"):
        return "+" + "".join(filter(str.isdigit, phone[1:]))
    return "".join(filter(str.isdigit, phone))
