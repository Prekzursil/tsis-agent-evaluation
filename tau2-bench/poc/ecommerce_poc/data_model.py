"""Agent-side database for the ecommerce_poc domain (full-scale version).

Grown from the 2-task POC into the complete Alpine Outfitters store:
returns, coupons, VAT invoices and shipping all live in this one DB.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.environment.db import DB

OrderStatus = Literal["processing", "delivered", "returned", "partially_returned"]
ShippingMethod = Literal["standard", "express"]


class User(BaseModel):
    user_id: str = Field(description="Unique identifier for the customer")
    name: str = Field(description="Customer full name")
    email: str = Field(description="Customer email address")


class OrderItem(BaseModel):
    item_id: str = Field(description="Unique line-item id within the order")
    product_id: str = Field(description="Product catalog id")
    product_name: str = Field(description="Human-readable product name")
    price: float = Field(description="Unit price in USD")
    quantity: int = Field(description="Number of units purchased")
    final_sale: bool = Field(
        default=False,
        description="Final-sale items are not returnable under store policy",
    )


class Order(BaseModel):
    order_id: str = Field(description="Unique order identifier, e.g. #AO-1001")
    user_id: str = Field(description="Customer who placed the order")
    status: OrderStatus = Field(description="Fulfilment status of the order")
    items: List[OrderItem] = Field(description="Line items in this order")
    payment_method_id: str = Field(description="Payment method used at checkout")
    delivered_on: Optional[str] = Field(
        default=None,
        description="Delivery date, ISO format YYYY-MM-DD (None until delivered)",
    )
    shipping_method: ShippingMethod = Field(
        default="standard", description="Shipping method chosen at checkout"
    )
    shipping_fee: float = Field(
        default=0.0, description="Shipping fee charged for this order, in USD"
    )
    ship_to: str = Field(
        default="", description="Full shipping address the order is routed to"
    )
    coupon_code: Optional[str] = Field(
        default=None, description="Coupon applied to this order, if any"
    )
    discount: float = Field(
        default=0.0, description="Discount amount applied to this order, in USD"
    )
    invoice_issued: bool = Field(
        default=False, description="Whether a VAT invoice has been issued"
    )
    invoice_vat_id: Optional[str] = Field(
        default=None, description="VAT id the invoice was issued with"
    )

    def subtotal(self) -> float:
        """Merchandise subtotal: sum of line totals, before any discount."""
        return round(sum(i.price * i.quantity for i in self.items), 2)


class Coupon(BaseModel):
    code: str = Field(description="Coupon code, e.g. WELCOME10")
    discount_type: Literal["percent", "fixed"] = Field(
        description="'percent' takes value% off the subtotal; 'fixed' takes a flat $value off"
    )
    value: float = Field(
        description="Percent points (0-100) for 'percent', USD amount for 'fixed'"
    )
    min_subtotal: float = Field(
        description="Minimum merchandise subtotal (USD, before discount) required to use the coupon"
    )
    expires_on: str = Field(
        description="Last valid date for the coupon, ISO YYYY-MM-DD (inclusive)"
    )
    one_per_customer: bool = Field(
        default=True,
        description="If true, each customer may redeem this coupon only once",
    )
    used_by: List[str] = Field(
        default_factory=list,
        description="user_ids that have already redeemed this coupon",
    )

    def discount_for(self, subtotal: float) -> float:
        if self.discount_type == "percent":
            return round(subtotal * self.value / 100.0, 2)
        return round(min(self.value, subtotal), 2)


class Refund(BaseModel):
    refund_id: str = Field(description="Unique refund identifier")
    order_id: str = Field(description="Order the refund applies to")
    amount: float = Field(description="Refunded amount in USD")
    payment_method_id: str = Field(description="Original payment method refunded")


class EcommerceDB(DB):
    """Alpine Outfitters store database (agent side)."""

    store_date: str = Field(
        description="The store's current date (ISO YYYY-MM-DD); fixed for determinism"
    )
    users: Dict[str, User] = Field(description="Customers indexed by user_id")
    orders: Dict[str, Order] = Field(description="Orders indexed by order_id")
    refunds: Dict[str, Refund] = Field(description="Refunds ledger indexed by refund_id")
    coupons: Dict[str, Coupon] = Field(
        default_factory=dict, description="Coupons indexed by code"
    )
