"""Agent tools for the `ecommerce2` team e-commerce support domain.

Plain functions on a ToolKitBase subclass decorated with @is_tool — the
harness parses their docstrings into OpenAI tool schemas. Store rules
implemented (mirrored by data/policy.md):

  * Identity: customers are looked up by email before any write.
  * Coupons: must exist, not be expired (expires_on, inclusive), meet the
    minimum order value, and the order must still be `pending`. Percent
    coupons round the discount to 2 decimals; a fixed coupon cannot exceed
    the subtotal. One coupon per order.
  * VAT invoices: the VAT ID must match the EU pattern (2-letter country
    prefix + 8-12 alphanumeric characters). The rate is looked up from the
    customer's country (DE 19%, FR 20%, IT 22%, NL 21%); net/vat are
    computed from the VAT-inclusive total and rounded to 2 decimals.
  * Returns: only `delivered` orders, within 30 days of delivered_on
    (inclusive); final-sale items cannot be returned; already-returned
    items cannot be returned twice. Refund = unit_price * quantity summed,
    rounded to 2 decimals; refunds go back to the original payment method.
  * Lost packages: only `shipped` orders; full refund of the order total
    (shipping included).
  * Shipping: address changes and express upgrades only on `pending`
    orders; express upgrade costs a flat 9.90 EUR on top; delivery
    countries are DE/FR/IT/NL/AT.
  * Cancellation: only `pending` orders can be cancelled.
"""

import re
from datetime import date, timedelta
from typing import List, Optional

from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

from .data_model import Address, Coupon, Customer, EcommerceDB, Invoice, Order

VAT_RATES = {"DE": 0.19, "FR": 0.20, "IT": 0.22, "NL": 0.21}
VAT_ID_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{8,12}$")
SHIP_COUNTRIES = {"DE", "FR", "IT", "NL", "AT"}
EXPRESS_FEE = 9.90
RETURN_WINDOW_DAYS = 30


def _round2(x: float) -> float:
    return round(x + 1e-9, 2)


class EcommerceTools(ToolKitBase):
    """Tools for the e-commerce support agent."""

    db: EcommerceDB

    @is_tool(ToolType.READ)
    def find_user_by_email(self, email: str) -> Customer:
        """
        Find the customer profile by email address. Use this first to verify
        who you are talking to before making any changes to an account.

        Args:
            email: The customer's email address, e.g. anna.meier@example.com

        Returns:
            The customer record.

        Raises:
            ValueError: If no customer with that email exists.
        """
        for c in self.db.customers.values():
            if c.email.lower() == email.lower():
                return c
        raise ValueError(f"No customer found with email {email}")

    @is_tool(ToolType.READ)
    def get_customer(self, customer_id: str) -> Customer:
        """
        Look up a customer profile by ID.

        Args:
            customer_id: The customer identifier, e.g. CUST-1001

        Returns:
            The customer record.

        Raises:
            ValueError: If the customer does not exist.
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer {customer_id} not found")
        return self.db.customers[customer_id]

    @is_tool(ToolType.READ)
    def get_order_details(self, order_id: str) -> Order:
        """
        Get full details of one order, including items, coupon, shipping and
        invoice data.

        Args:
            order_id: The order identifier, e.g. #ORD-1001

        Returns:
            The order record.

        Raises:
            ValueError: If the order does not exist.
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")
        return self.db.orders[order_id]

    @is_tool(ToolType.READ)
    def get_coupon_details(self, coupon_code: str) -> Coupon:
        """
        Get the terms of a coupon code (discount, minimum order value, expiry).

        Args:
            coupon_code: The coupon code, e.g. WELCOME10

        Returns:
            The coupon record.

        Raises:
            ValueError: If the coupon does not exist.
        """
        if coupon_code not in self.db.coupons:
            raise ValueError(f"Coupon {coupon_code} not found")
        return self.db.coupons[coupon_code]

    @is_tool(ToolType.WRITE)
    def apply_coupon_to_order(self, order_id: str, coupon_code: str) -> Order:
        """
        Apply a coupon to a pending order and recompute the payable total.
        The coupon must exist, be unexpired, meet its minimum order value,
        and the order must still be pending with no coupon already applied.

        Args:
            order_id: The order identifier, e.g. #ORD-1001
            coupon_code: The coupon code to apply, e.g. WELCOME10

        Returns:
            The updated order.

        Raises:
            ValueError: If the order or coupon does not exist, the order is
                not pending, a coupon is already applied, the coupon is
                expired, or the subtotal is below the coupon minimum.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "pending":
            raise ValueError(
                f"Order {order_id} is {order.status}; coupons only apply to pending orders"
            )
        if order.coupon_code is not None:
            raise ValueError(
                f"Coupon {order.coupon_code} is already applied to order "
                f"{order_id}; applied coupons cannot be removed or swapped"
            )
        coupon = self.db.coupons.get(coupon_code)
        if coupon is None:
            raise ValueError(f"Coupon {coupon_code} not found")
        today = date.fromisoformat(date.today().isoformat())
        if today > date.fromisoformat(coupon.expires_on):
            raise ValueError(
                f"Coupon {coupon_code} expired on {coupon.expires_on}"
            )
        if order.subtotal < coupon.min_order_value:
            raise ValueError(
                f"Order subtotal {order.subtotal} is below the coupon minimum "
                f"{coupon.min_order_value}"
            )
        if coupon.discount_type == "percent":
            discount = _round2(order.subtotal * coupon.value / 100.0)
        else:
            discount = _round2(min(coupon.value, order.subtotal))
        order.coupon_code = coupon.code
        order.discount = discount
        order.total = _round2(order.subtotal - discount + order.shipping_cost)
        return order

    @is_tool(ToolType.WRITE)
    def issue_invoice_with_vat(
        self, order_id: str, vat_id: Optional[str] = None
    ) -> Invoice:
        """
        Issue (or re-issue) the VAT invoice for an order. When a VAT ID is
        supplied it is printed on the invoice; the VAT rate follows the
        customer's country and net/VAT amounts are derived from the
        VAT-inclusive total.

        Args:
            order_id: The order identifier, e.g. #ORD-2002
            vat_id: Optional customer VAT ID, e.g. DE123456789

        Returns:
            The issued invoice.

        Raises:
            ValueError: If the order does not exist, or the VAT ID does not
                match the expected EU format.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if vat_id is not None:
            if not VAT_ID_PATTERN.match(vat_id):
                raise ValueError(
                    f"VAT ID {vat_id} is not a valid EU VAT number "
                    "(expected 2-letter country code + 8-12 alphanumeric characters)"
                )
        customer = self.db.customers[order.customer_id]
        rate = VAT_RATES.get(customer.country, 0.0)
        gross = order.total
        net = _round2(gross / (1.0 + rate))
        invoice = Invoice(
            invoice_id=f"INV-{order.order_id.lstrip('#')}",
            vat_id=vat_id,
            vat_rate=rate,
            net_amount=net,
            vat_amount=_round2(gross - net),
            gross_amount=gross,
        )
        order.invoice = invoice
        return invoice

    @is_tool(ToolType.WRITE)
    def return_order_items(self, order_id: str, item_ids: List[str]) -> Order:
        """
        Register a return for specific items of a delivered order and refund
        them to the original payment method. Returns are only possible within
        30 days of delivery (inclusive); final-sale items cannot be returned;
        items already returned cannot be returned again. The refund amount is
        the sum of unit_price * quantity of the returned items.

        Args:
            order_id: The order identifier, e.g. #ORD-5005
            item_ids: The line-item ids to return, e.g. ["it_5005_1"]

        Returns:
            The updated order with returned_items and refund_total set.

        Raises:
            ValueError: If the order does not exist or is not delivered, the
                30-day return window has passed, an item is final sale, an
                item is unknown, or an item was already returned.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "delivered":
            raise ValueError(
                f"Order {order_id} is {order.status}; only delivered orders "
                "can be returned"
            )
        if not order.delivered_on:
            raise ValueError(f"Order {order_id} has no delivery date recorded")
        window_end = date.fromisoformat(order.delivered_on) + timedelta(
            days=RETURN_WINDOW_DAYS
        )
        if date.today() > window_end:
            raise ValueError(
                f"Order {order_id} was delivered on {order.delivered_on}; the "
                f"{RETURN_WINDOW_DAYS}-day return window ended on "
                f"{window_end.isoformat()}"
            )
        by_id = {i.item_id: i for i in order.items}
        final_sale = [x for x in item_ids if x in by_id and by_id[x].final_sale]
        if final_sale:
            raise ValueError(
                f"Final-sale items cannot be returned: {', '.join(final_sale)}"
            )
        unknown = [x for x in item_ids if x not in by_id]
        if unknown:
            raise ValueError(f"Unknown item ids on order {order_id}: {', '.join(unknown)}")
        already = [x for x in item_ids if x in order.returned_items]
        if already:
            raise ValueError(
                f"Items already returned on order {order_id}: {', '.join(already)}"
            )
        refund = _round2(
            sum(by_id[x].unit_price * by_id[x].quantity for x in item_ids)
        )
        order.returned_items = order.returned_items + list(item_ids)
        order.refund_total = _round2(order.refund_total + refund)
        eligible = {i.item_id for i in order.items if not i.final_sale}
        if eligible.issubset(set(order.returned_items)):
            order.status = "returned"
        return order

    @is_tool(ToolType.WRITE)
    def refund_lost_package(self, order_id: str) -> Order:
        """
        Refund a package that was lost in transit. Only orders still in
        status `shipped` (never delivered) qualify; the refund is the full
        order total including shipping, to the original payment method.

        Args:
            order_id: The order identifier, e.g. #ORD-13013

        Returns:
            The updated order with status refunded and refund_total set.

        Raises:
            ValueError: If the order does not exist or is not in transit.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "shipped":
            raise ValueError(
                f"Order {order_id} is {order.status}; only packages lost in "
                "transit (status shipped) qualify for a lost-package refund"
            )
        order.status = "refunded"
        order.refund_total = _round2(order.refund_total + order.total)
        return order

    @is_tool(ToolType.WRITE)
    def change_shipping_address(
        self,
        order_id: str,
        street: str,
        city: str,
        postal_code: str,
        country: str,
    ) -> Order:
        """
        Change the delivery address of a pending order. Orders that have
        already shipped or been delivered cannot be re-routed. We deliver to
        DE, FR, IT, NL and AT only.

        Args:
            order_id: The order identifier, e.g. #ORD-8008
            street: Street and house number of the new address
            city: City of the new address
            postal_code: Postal code of the new address
            country: ISO country code of the new address (DE/FR/IT/NL/AT)

        Returns:
            The updated order.

        Raises:
            ValueError: If the order does not exist, is not pending, or the
                country is outside the delivery area.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "pending":
            raise ValueError(
                f"Order {order_id} is {order.status}; only pending orders can "
                "have their shipping address changed"
            )
        cc = country.upper()
        if cc not in SHIP_COUNTRIES:
            raise ValueError(
                f"We do not deliver to {country}; delivery countries are "
                f"{', '.join(sorted(SHIP_COUNTRIES))}"
            )
        order.shipping_address = Address(
            street=street, city=city, postal_code=postal_code, country=cc
        )
        return order

    @is_tool(ToolType.WRITE)
    def upgrade_shipping_method(self, order_id: str, shipping_method: str) -> Order:
        """
        Change the shipping method of a pending order. Express shipping is a
        flat 9.90 EUR upgrade on top of the order total; switching back to
        standard does not refund a paid express fee. Only pending orders can
        be changed.

        Args:
            order_id: The order identifier, e.g. #ORD-9009
            shipping_method: The new shipping method: "express" or "standard"

        Returns:
            The updated order with shipping_method, shipping_cost and total.

        Raises:
            ValueError: If the order does not exist, is not pending, the
                method name is unknown, or the order already uses that
                method.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "pending":
            raise ValueError(
                f"Order {order_id} is {order.status}; only pending orders can "
                "change the shipping method"
            )
        if shipping_method not in ("express", "standard"):
            raise ValueError(
                f"Unknown shipping method {shipping_method}; use express or standard"
            )
        if shipping_method == order.shipping_method:
            raise ValueError(
                f"Order {order_id} already uses {shipping_method} shipping"
            )
        order.shipping_method = shipping_method  # type: ignore[assignment]
        order.shipping_cost = _round2(EXPRESS_FEE if shipping_method == "express" else 0.0)
        order.total = _round2(order.subtotal - order.discount + order.shipping_cost)
        return order

    @is_tool(ToolType.WRITE)
    def cancel_order(self, order_id: str) -> Order:
        """
        Cancel a pending order. Shipped or delivered orders cannot be
        cancelled (they must be returned after delivery instead). The
        customer receives a cancellation confirmation by email.

        Args:
            order_id: The order identifier, e.g. #ORD-12012

        Returns:
            The updated order with status cancelled.

        Raises:
            ValueError: If the order does not exist or is not pending.
        """
        order = self.db.orders.get(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.status != "pending":
            raise ValueError(
                f"Order {order_id} is {order.status}; only pending orders can "
                "be cancelled"
            )
        order.status = "cancelled"
        return order
