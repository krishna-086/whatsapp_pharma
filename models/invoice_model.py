"""
Invoice Model - Data models for invoice processing.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class InvoiceItem(BaseModel):
    """Represents a single line item on an invoice."""
    name: str = Field(..., description="Medicine/product name")
    quantity: int = Field(default=1, description="Quantity ordered")
    unit_price: float = Field(default=0.0, description="Price per unit")
    total_price: float = Field(default=0.0, description="Total line item price")
    batch_number: Optional[str] = Field(default=None, description="Batch/lot number")
    expiry_date: Optional[str] = Field(default=None, description="Expiry date")


class Invoice(BaseModel):
    """Represents a pharmacy invoice."""
    id: Optional[str] = Field(default=None, description="Unique invoice ID")
    vendor_name: str = Field(default="", description="Supplier/vendor name")
    invoice_number: Optional[str] = Field(default=None, description="Invoice number from vendor")
    invoice_date: datetime = Field(default_factory=datetime.utcnow, description="Date of invoice")
    items: List[InvoiceItem] = Field(default_factory=list, description="Line items")
    subtotal: float = Field(default=0.0, description="Subtotal before tax")
    tax: float = Field(default=0.0, description="Tax amount")
    total: float = Field(default=0.0, description="Total invoice amount")
    status: str = Field(default="pending", description="Invoice processing status")
    raw_text: Optional[str] = Field(default=None, description="Raw extracted text from document")
    created_at: datetime = Field(default_factory=datetime.utcnow)
