"""User-side tools for the ecommerce_poc domain (dual-control, full-scale).

Mirrors the tau2-bench user-simulation constraint: outputs are human-readable
strings, and the user only acts reactively (when the agent asks them to check
or fix something in their own account).
"""

from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

from .tools import is_valid_vat_id
from .user_data_model import ShopperAppDB


class ShopperAppTools(ToolKitBase):
    """The customer's account app (what the user can see and do themselves)."""

    db: ShopperAppDB

    def __init__(self, db: ShopperAppDB) -> None:
        super().__init__(db)

    @is_tool(ToolType.READ)
    def view_saved_details(self) -> str:
        """
        Open the account page of the shopping app and read the saved checkout
        details: email, VAT id and default shipping address currently on file.

        Returns:
            A human-readable summary of the saved details.
        """
        p = self.db._active()
        return (
            "Your account currently has:\n"
            f"- Email: {p.email}\n"
            f"- VAT id: {p.vat_id or '(none saved)'}\n"
            f"- Shipping address: {p.address or '(none saved)'}"
        )

    @is_tool(ToolType.READ)
    def view_my_coupons(self) -> str:
        """
        Open the coupon wallet in the shopping app and list the personal
        coupon codes saved there.

        Returns:
            A human-readable list of the saved coupon codes.
        """
        p = self.db._active()
        if not p.coupon_codes:
            return "Your coupon wallet is empty."
        return "Your coupon wallet contains: " + ", ".join(p.coupon_codes)

    @is_tool(ToolType.WRITE)
    def update_saved_vat_id(self, vat_id: str) -> str:
        """
        Change the VAT id saved in the account's checkout profile.
        The VAT id must be exactly 9 uppercase letters/digits.

        Args:
            vat_id: The new VAT id to save.

        Returns:
            A human-readable confirmation shown in the app.

        Raises:
            ValueError: If the VAT id is not in a valid format.
        """
        if not is_valid_vat_id(vat_id):
            raise ValueError(
                f"VAT id '{vat_id}' is invalid: must be exactly 9 letters/digits"
            )
        p = self.db._active()
        p.vat_id = vat_id
        return f"Saved. Your new VAT id is {vat_id}"

    @is_tool(ToolType.WRITE)
    def update_saved_address(self, address: str) -> str:
        """
        Change the default shipping address saved in the account.

        Args:
            address: The full new shipping address to save.

        Returns:
            A human-readable confirmation shown in the app.
        """
        p = self.db._active()
        p.address = address
        return f"Saved. Your new default shipping address is: {address}"

    # --------------------------------------------- assertion helpers
    # (not exposed to the LLM: no @is_tool)

    def assert_saved_vat_id(self, user_id: str, expected_vat_id: str) -> bool:
        """Check whether a customer's saved VAT id equals the expected one."""
        p = self.db.profiles.get(user_id)
        return bool(p and p.vat_id == expected_vat_id)

    def assert_saved_address(self, user_id: str, expected_address: str) -> bool:
        """Check whether a customer's saved address equals the expected one."""
        p = self.db.profiles.get(user_id)
        return bool(p and p.address == expected_address)

    # ------------------------------------------------ init helpers
    # (task-initialization actions, telecom-style; not exposed to the LLM)

    def login_as(self, user_id: str) -> str:
        """Log the given customer into the app at task-initialization time."""
        if user_id not in self.db.profiles:
            raise ValueError(f"Unknown user {user_id}")
        self.db.active_user_id = user_id
        return f"app logged in as {user_id}"

    def set_saved_vat_id(self, user_id: str, vat_id: str) -> str:
        """Set a customer's saved VAT id at task-initialization time."""
        self.db.profiles[user_id].vat_id = vat_id
        return f"saved_vat_id of {user_id} set to {vat_id}"

    def set_saved_address(self, user_id: str, address: str) -> str:
        """Set a customer's saved address at task-initialization time."""
        self.db.profiles[user_id].address = address
        return f"saved address of {user_id} set"
