"""ecommerce_poc — proof-of-contribution domain for tau2-bench.

An e-commerce customer-support domain ("Alpine Outfitters") exercising the two
reward styles the harness supports:

- Task ``ecomm_return_001``: single-control, DB+COMMUNICATE reward with a
  reference action trajectory (retail/airline style).
- Task ``ecomm_vat_001``: dual-control, ENV_ASSERTION reward where the fix
  requires BOTH the agent (re-issue invoice with VAT) and the user (correct
  the VAT id saved in their own account) to act (telecom style).

All code lives in the lane directory; the cloned repo is untouched.
"""

from tau2.environment.db import DB  # noqa: F401  (re-export convenience)
