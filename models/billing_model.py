"""
Billing Model - Data models for billing and transactions.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class BillItem(BaseModel):
    """Represents a single item on a customer bill."""
    medicine_name: str = Field(..., description="Medicine name")
    quantity: int = Field(default=1, description="Quantity sold")
    unit_price: float = Field(default=0.0, description="Price per unit")
    total_price: float = Field(default=0.0, description="Total line item price")


class Bill(BaseModel):
    """Represents a customer bill/transaction."""
    id: Optional[str] = Field(default=None, description="Unique bill ID")
    customer_name: Optional[str] = Field(default=None, description="Customer name")
    customer_phone: Optional[str] = Field(default=None, description="Customer phone number")
    items: List[BillItem] = Field(default_factory=list, description="Items purchased")
    subtotal: float = Field(default=0.0, description="Subtotal before tax/discount")
    discount: float = Field(default=0.0, description="Discount amount")
    tax: float = Field(default=0.0, description="Tax amount")
    total: float = Field(default=0.0, description="Total bill amount")
    payment_method: Optional[str] = Field(default=None, description="Payment method (cash, card, UPI, etc.)")
    paid: bool = Field(default=False, description="Whether the bill has been paid")
    status: str = Field(default="pending", description="Bill status")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentRecord(BaseModel):
    """Represents a payment made against a bill."""
    id: Optional[str] = Field(default=None, description="Unique payment ID")
    bill_id: str = Field(..., description="Associated bill ID")
    amount: float = Field(..., description="Payment amount")
    method: str = Field(default="cash", description="Payment method")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
