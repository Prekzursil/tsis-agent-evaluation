"""User-side database for the ecommerce_poc domain (dual-control, full-scale).

One profile per customer, mirroring what each shopper sees in their own
account app: saved email, VAT id, shipping address and personal coupon
codes. Only the customer can change these (support cannot), and only the
customer knows some of these values — the complexity asymmetry the
tau2-bench user-simulation design calls for.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from tau2.environment.db import DB


class ShopperProfile(BaseModel):
    """A single customer's saved account data in the shopper app."""

    email: str = Field(description="Email saved in the shopper's account")
    vat_id: Optional[str] = Field(
        default=None, description="VAT id saved in the checkout profile"
    )
    address: Optional[str] = Field(
        default=None, description="Default shipping address saved in the app"
    )
    coupon_codes: List[str] = Field(
        default_factory=list,
        description="Personal coupon codes visible in the app's coupon wallet",
    )


class ShopperAppDB(DB):
    """Mocked shopper account app (user side)."""

    active_user_id: Optional[str] = Field(
        default=None,
        description="Which customer is logged into the app for this task",
    )
    profiles: Dict[str, ShopperProfile] = Field(
        description="Per-customer saved data, keyed by user_id"
    )

    def _active(self) -> ShopperProfile:
        if self.active_user_id is None:
            if len(self.profiles) == 1:
                return next(iter(self.profiles.values()))
            raise ValueError("No shopper logged into the app")
        return self.profiles[self.active_user_id]
