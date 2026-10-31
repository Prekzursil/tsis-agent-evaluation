"""Data model for the `ecommerce3` domain — the COMPLETE team e-commerce
support domain grown from the 2-task POC (session 4, 2026-10-24) for
tau2-bench v2.0.0 @ cc1df47.

Lineage: the rule set (returns / coupons / VAT / shipping / cancellation /
lost packages) is the lane's `ecommerce2` domain (v1.0.1 harness, 56-sim
k=4 sweep 2026-10-19, failure analysis in RESULTS.md section 3), ported to
the v2.0.0 `poc/ecommerce3` skeleton and re-validated. The two POC tasks
(`return_coupon_001`, `vat_invoice_002`) are superseded by the grown task
families: return_task_3 (full return to the original payment method) and
coupon_task_2 + vat_task_1 (expired-coupon decline + VAT receipt issue).

Field semantics (enforced server-side in tools.py, mirrored in data/policy.md):
  * Order.delivered_on starts the 30-day return window (inclusive).
  * OrderItem.final_sale marks items excluded from returns.
  * Coupon.expires_on is the last redeemable date (inclusive);
    min_order_value gates the order subtotal.
  * Invoice carries the country-derived VAT rate and net/VAT/gross split.
  * Order.total = subtotal - discount + shipping_cost (all EUR, VAT-inclusive).
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.environment.db import DB

DATA_DIR = None  # set by environment.py via __init__ paths below
from pathlib import Path as _Path

DATA_DIR = _Path(__file__).parent / "data"
ECOM_DB_PATH = DATA_DIR / "db.json"
ECOM_POLICY_PATH = DATA_DIR / "policy.md"
ECOM_TASK_SET_PATH = DATA_DIR / "tasks.json"

OrderStatus = Literal[
    "pending", "shipped", "delivered", "cancelled", "returned", "refunded"
]
ShippingMethod = Literal["standard", "express"]


class Address(BaseModel):
    street: str = Field(description="Street and house number")
    city: str = Field(description="City")
    postal_code: str = Field(description="Postal code")
    country: str = Field(description="ISO country code, e.g. DE")


class OrderItem(BaseModel):
    item_id: str = Field(description="Line-item identifier, e.g. it_5005_1")
    product_id: str = Field(description="Product identifier")
    name: str = Field(description="Product name shown to the customer")
    quantity: int = Field(description="Quantity ordered")
    unit_price: float = Field(description="Unit price in EUR, VAT-inclusive")
    final_sale: bool = Field(
        default=False,
        description="True when the item was sold as final sale and cannot be returned",
    )


class Invoice(BaseModel):
    invoice_id: Optional[str] = Field(
        default=None, description="Invoice number, None when not yet issued"
    )
    vat_id: Optional[str] = Field(
        default=None, description="Customer VAT ID printed on the invoice, if any"
    )
    vat_rate: Optional[float] = Field(
        default=None, description="VAT rate applied (e.g. 0.19 for Germany)"
    )
    net_amount: Optional[float] = Field(default=None, description="Net (ex-VAT) total")
    vat_amount: Optional[float] = Field(default=None, description="VAT charged")
    gross_amount: Optional[float] = Field(
        default=None, description="Gross total (= order total)"
    )


class Order(BaseModel):
    order_id: str = Field(description="Order identifier, e.g. #ORD-1001")
    customer_id: str = Field(description="Customer who placed the order")
    status: OrderStatus = Field(description="Fulfilment status of the order")
    items: List[OrderItem] = Field(description="Line items of the order")
    subtotal: float = Field(description="Sum of line items, EUR, VAT-inclusive")
    coupon_code: Optional[str] = Field(
        default=None, description="Coupon applied to the order, if any"
    )
    discount: float = Field(default=0.0, description="Discount amount, EUR")
    shipping_method: ShippingMethod = Field(
        default="standard", description="Shipping method chosen at checkout"
    )
    shipping_cost: float = Field(default=0.0, description="Shipping cost charged, EUR")
    total: float = Field(
        description="Payable total after discount plus shipping, EUR"
    )
    shipping_address: Address = Field(description="Delivery address")
    delivered_on: Optional[str] = Field(
        default=None,
        description="Delivery date (ISO) once delivered; starts the return window",
    )
    payment_method: str = Field(
        default="credit_card",
        description="Payment method used at checkout; refunds always go back to it",
    )
    returned_items: List[str] = Field(
        default_factory=list,
        description="item_ids already returned by the customer",
    )
    refund_total: float = Field(
        default=0.0, description="Total refunded to the customer, EUR"
    )
    invoice: Invoice = Field(default_factory=Invoice, description="Invoice data")


class Coupon(BaseModel):
    code: str = Field(description="Coupon code, e.g. WELCOME10")
    discount_type: Literal["percent", "fixed"] = Field(
        description="'percent' reduces the subtotal by a percentage, 'fixed' by a flat amount"
    )
    value: float = Field(
        description="Percent (0-100) when discount_type='percent', else EUR amount"
    )
    min_order_value: float = Field(
        default=0.0, description="Minimum subtotal the coupon requires, EUR"
    )
    expires_on: str = Field(
        description="Last date (inclusive) the coupon is redeemable, ISO format"
    )


class Customer(BaseModel):
    customer_id: str = Field(description="Customer identifier")
    name: str = Field(description="Customer full name")
    email: str = Field(description="Customer email")
    country: str = Field(description="ISO country code for place of supply")
    vat_id: Optional[str] = Field(
        default=None, description="Business VAT ID, None for consumers"
    )


class EcomDB(DB):
    """Store database: customers, coupons and orders."""

    customers: Dict[str, Customer] = Field(
        description="Customers indexed by customer_id"
    )
    coupons: Dict[str, Coupon] = Field(description="Coupons indexed by code")
    orders: Dict[str, Order] = Field(description="Orders indexed by order_id")
