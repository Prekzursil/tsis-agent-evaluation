"""Agent-side tools for the ecommerce_poc domain (full-scale version).

Alpine Outfitters support agent: returns, lost-package claims, coupons,
shipping and VAT invoices. Rules mirror data/policy.md exactly.
"""

import re
from datetime import date
from typing import List, Optional

from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

from .data_model import Coupon, EcommerceDB, Order, Refund, User

# A "valid" VAT id for this store: exactly 9 letters/digits (ISO-ish, kept
# deliberately simple and deterministic for assertions).
VAT_ID_PATTERN = re.compile(r"^[A-Z0-9]{9}$")

RETURN_WINDOW_DAYS = 30
LOST_PACKAGE_WINDOW_DAYS = 14
EXPRESS_UPGRADE_FEE = 12.90


def is_valid_vat_id(vat_id: str) -> bool:
    return bool(VAT_ID_PATTERN.match(vat_id or ""))


def _money(amount: float) -> str:
    return f"${amount:.2f}"


class EcommerceTools(ToolKitBase):
    """Alpine Outfitters support-agent tools."""

    db: EcommerceDB

    def __init__(self, db: EcommerceDB) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------ reads

    @is_tool(ToolType.READ)
    def find_user_by_email(self, email: str) -> User:
        """
        Look up a customer account by the email address used at checkout.

        Args:
            email: The customer's email address (case-insensitive).

        Returns:
            The customer record.

        Raises:
            ValueError: If no account matches the email.
        """
        for user in self.db.users.values():
            if user.email.lower() == email.lower():
                return user
        raise ValueError(f"No account found for email {email}")

    @is_tool(ToolType.READ)
    def get_order_details(self, order_id: str) -> Order:
        """
        Get full details of an order, including items, status, dates,
        shipping and any applied coupon.

        Args:
            order_id: The order identifier, e.g. '#AO-1001'.

        Returns:
            The order record.

        Raises:
            ValueError: If the order is not found.
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")
        return self.db.orders[order_id]

    @is_tool(ToolType.READ)
    def get_coupon_details(self, coupon_code: str) -> Coupon:
        """
        Look up a coupon's terms: discount, minimum subtotal, expiry date and
        whether it is limited to one use per customer. Always check this
        before applying a coupon.

        Args:
            coupon_code: The coupon code, e.g. 'WELCOME10'.

        Returns:
            The coupon record.

        Raises:
            ValueError: If the coupon code is unknown.
        """
        if coupon_code not in self.db.coupons:
            raise ValueError(f"Coupon code {coupon_code} not found")
        return self.db.coupons[coupon_code]

    # ----------------------------------------------------------------- writes

    @is_tool(ToolType.WRITE)
    def return_order_items(self, order_id: str, item_ids: List[str]) -> Refund:
        """
        Start a return for specific items of a delivered order and refund them
        to the original payment method. Store policy: returns are accepted
        within 30 days of delivery; final-sale items are never returnable.

        Args:
            order_id: The order to return items from.
            item_ids: The line-item ids to return.

        Returns:
            The created refund record.

        Raises:
            ValueError: If the order/items are not eligible for return.
        """
        order = self.get_order_details(order_id)
        if order.status not in ("delivered", "partially_returned"):
            raise ValueError(
                f"Order {order_id} has status '{order.status}' and cannot be returned"
            )
        delivered = date.fromisoformat(order.delivered_on)
        today = date.fromisoformat(self.db.store_date)
        if (today - delivered).days > RETURN_WINDOW_DAYS:
            raise ValueError(
                f"Order {order_id} was delivered more than {RETURN_WINDOW_DAYS} days ago "
                "and is outside the return window"
            )
        items = {i.item_id: i for i in order.items}
        for item_id in item_ids:
            if item_id not in items:
                raise ValueError(f"Item {item_id} not found in order {order_id}")
            if items[item_id].final_sale:
                raise ValueError(
                    f"Item {item_id} ({items[item_id].product_name}) is final-sale "
                    "and cannot be returned"
                )
        amount = round(
            sum(items[iid].price * items[iid].quantity for iid in item_ids), 2
        )
        refund_id = f"RF-{len(self.db.refunds) + 1:04d}"
        refund = Refund(
            refund_id=refund_id,
            order_id=order_id,
            amount=amount,
            payment_method_id=order.payment_method_id,
        )
        self.db.refunds[refund_id] = refund
        returned = {i.item_id for i in order.items if i.item_id in item_ids}
        fully_returned = all(
            i.final_sale or i.item_id in returned for i in order.items
        )
        order.status = "returned" if fully_returned else "partially_returned"
        return refund

    @is_tool(ToolType.WRITE)
    def refund_lost_package(self, order_id: str) -> Refund:
        """
        File a lost-package claim for an order that is marked delivered but
        was never received by the customer. Store policy: claims are accepted
        within 14 days of the recorded delivery date; the refund covers the
        full order value INCLUDING the shipping fee, to the original payment
        method.

        Args:
            order_id: The order the customer never received.

        Returns:
            The created refund record (order value + shipping fee).

        Raises:
            ValueError: If the order is not eligible for a lost-package claim.
        """
        order = self.get_order_details(order_id)
        if order.status != "delivered":
            raise ValueError(
                f"Order {order_id} has status '{order.status}'; lost-package claims "
                "only apply to orders marked delivered"
            )
        delivered = date.fromisoformat(order.delivered_on)
        today = date.fromisoformat(self.db.store_date)
        if (today - delivered).days > LOST_PACKAGE_WINDOW_DAYS:
            raise ValueError(
                f"Order {order_id} was delivered more than {LOST_PACKAGE_WINDOW_DAYS} "
                "days ago; the claim window is closed and the case must go to a human agent"
            )
        amount = round(order.subtotal() + order.shipping_fee, 2)
        refund_id = f"RF-{len(self.db.refunds) + 1:04d}"
        refund = Refund(
            refund_id=refund_id,
            order_id=order_id,
            amount=amount,
            payment_method_id=order.payment_method_id,
        )
        self.db.refunds[refund_id] = refund
        order.status = "returned"
        return refund

    @is_tool(ToolType.WRITE)
    def apply_coupon_to_order(self, order_id: str, coupon_code: str) -> str:
        """
        Apply a coupon to an order and record the discount. Store policy:
        verify the coupon terms with get_coupon_details first; expired
        coupons, coupons whose minimum subtotal is not met, and one-per-
        customer coupons already redeemed by this customer must be declined.

        Args:
            order_id: The order to apply the coupon to.
            coupon_code: The coupon code.

        Returns:
            A confirmation message with the applied discount.

        Raises:
            ValueError: If the coupon cannot be applied under store policy.
        """
        order = self.get_order_details(order_id)
        coupon = self.get_coupon_details(coupon_code)
        today = date.fromisoformat(self.db.store_date)
        expires = date.fromisoformat(coupon.expires_on)
        if today > expires:
            raise ValueError(
                f"Coupon {coupon_code} expired on {coupon.expires_on} and cannot be applied"
            )
        subtotal = order.subtotal()
        if subtotal < coupon.min_subtotal:
            raise ValueError(
                f"Coupon {coupon_code} requires a minimum subtotal of {_money(coupon.min_subtotal)}; "
                f"order {order_id} subtotal is only {_money(subtotal)}"
            )
        if coupon.one_per_customer and order.user_id in coupon.used_by:
            raise ValueError(
                f"Coupon {coupon_code} is limited to one use per customer and has "
                "already been redeemed by this customer"
            )
        discount = coupon.discount_for(subtotal)
        order.coupon_code = coupon_code
        order.discount = discount
        if coupon.one_per_customer:
            coupon.used_by.append(order.user_id)
        return (
            f"Coupon {coupon_code} applied to {order_id}: "
            f"discount {_money(discount)} off the {_money(subtotal)} subtotal"
        )

    @is_tool(ToolType.WRITE)
    def issue_invoice_with_vat(self, order_id: str, vat_id: str) -> str:
        """
        (Re-)issue the VAT invoice for an order using the given VAT id.
        The VAT id must be exactly 9 uppercase letters/digits.

        Args:
            order_id: The order to issue the invoice for.
            vat_id: The customer's VAT id to put on the invoice.

        Returns:
            Confirmation message with the invoice reference.

        Raises:
            ValueError: If the order is unknown or the VAT id is invalid.
        """
        order = self.get_order_details(order_id)
        if not is_valid_vat_id(vat_id):
            raise ValueError(
                f"VAT id '{vat_id}' is invalid: must be exactly 9 letters/digits"
            )
        order.invoice_issued = True
        order.invoice_vat_id = vat_id
        return f"Invoice INV-{order_id.lstrip('#')} issued with VAT id {vat_id}"

    @is_tool(ToolType.WRITE)
    def change_shipping_address(self, order_id: str, new_address: str) -> str:
        """
        Re-route an order that has not shipped yet to a new address. Store
        policy: address changes are only possible while the order status is
        'processing'; once an order has shipped or been delivered the address
        can no longer be changed.

        Args:
            order_id: The order to re-route.
            new_address: The full new shipping address.

        Returns:
            Confirmation message.

        Raises:
            ValueError: If the order has already shipped or was delivered.
        """
        order = self.get_order_details(order_id)
        if order.status != "processing":
            raise ValueError(
                f"Order {order_id} has status '{order.status}'; the shipping address "
                "can only be changed while an order is still processing"
            )
        order.ship_to = new_address
        return f"Order {order_id} re-routed to the new address"

    @is_tool(ToolType.WRITE)
    def upgrade_shipping_method(self, order_id: str) -> str:
        """
        Upgrade an order that has not shipped yet from standard to express
        shipping. Store policy: upgrades are only possible while the order
        status is 'processing' and add a flat $12.90 express fee.

        Args:
            order_id: The order to upgrade.

        Returns:
            Confirmation message with the added fee.

        Raises:
            ValueError: If the order has already shipped or is already express.
        """
        order = self.get_order_details(order_id)
        if order.status != "processing":
            raise ValueError(
                f"Order {order_id} has status '{order.status}'; shipping can only be "
                "upgraded while an order is still processing"
            )
        if order.shipping_method == "express":
            raise ValueError(f"Order {order_id} already ships express")
        order.shipping_method = "express"
        order.shipping_fee = round(order.shipping_fee + EXPRESS_UPGRADE_FEE, 2)
        return (
            f"Order {order_id} upgraded to express shipping; "
            f"{_money(EXPRESS_UPGRADE_FEE)} added to the order"
        )

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """
        Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if the user explicitly asks for a human agent, or if,
        given the policy and the available tools, you cannot solve the issue.

        Args:
            summary: A summary of the user's issue.

        Returns:
            A message indicating the user has been transferred.
        """
        return "Transfer successful"

    # ------------------------------------------------- assertion helpers
    # (not exposed to the LLM: no @is_tool; used by EnvAssertion checks)

    def assert_refund_issued(self, order_id: str, expected_amount: float) -> bool:
        """Check whether a refund of the expected amount exists for an order."""
        return any(
            r.order_id == order_id and abs(r.amount - expected_amount) < 1e-9
            for r in self.db.refunds.values()
        )

    def assert_no_refund_issued(self, order_id: str) -> bool:
        """Check that NO refund exists for an order (decline-task guard)."""
        return not any(r.order_id == order_id for r in self.db.refunds.values())

    def assert_invoice_issued(self, order_id: str, expected_vat_id: str) -> bool:
        """Check whether an invoice with the expected VAT id was issued."""
        o = self.db.orders.get(order_id)
        return bool(
            o and o.invoice_issued and o.invoice_vat_id == expected_vat_id
        )

    def assert_order_address(self, order_id: str, expected_address: str) -> bool:
        """Check whether an order is routed to the expected address."""
        o = self.db.orders.get(order_id)
        return bool(o and o.ship_to == expected_address)

    def assert_shipping_method(
        self, order_id: str, expected_method: str, expected_fee: float
    ) -> bool:
        """Check an order's shipping method and fee."""
        o = self.db.orders.get(order_id)
        return bool(
            o
            and o.shipping_method == expected_method
            and abs(o.shipping_fee - expected_fee) < 1e-9
        )

    def assert_order_discount(
        self, order_id: str, expected_coupon: str, expected_discount: float
    ) -> bool:
        """Check the coupon and discount recorded on an order."""
        o = self.db.orders.get(order_id)
        return bool(
            o
            and o.coupon_code == expected_coupon
            and abs(o.discount - expected_discount) < 1e-9
        )

    # ------------------------------------------------ init helpers
    # (task-initialization actions, telecom-style; not exposed to the LLM)

    def reset_invoice(self, order_id: str) -> str:
        """Clear any issued invoice on an order at task-initialization time."""
        order = self.get_order_details(order_id)
        order.invoice_issued = False
        order.invoice_vat_id = None
        return f"invoice reset for {order_id}"

    def set_order_status(self, order_id: str, status: str) -> str:
        """Force an order status at task-initialization time."""
        order = self.get_order_details(order_id)
        order.status = status
        return f"status of {order_id} set to {status}"
