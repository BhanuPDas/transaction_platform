"""
For every resource the buyer actually demands (demand_per_unit > 0), the
buyer's budget for that resource must be >= the seller's price for that
resource. carbon is intentionally excluded -- it's a scoring signal, not a
priced/demanded resource (mirrors the Go resourceMapping, which only covers
vcpu/ram/storage/vgpu).
"""

from __future__ import annotations

PRICED_RESOURCES = ("vcpu", "ram", "storage", "vgpu")


class PricingMissingError(Exception):
    """Seller has no price quoted for a resource the buyer demands."""


def has_high_budget(resources: dict, seller_obj: dict, logger) -> bool:
    seller_price = seller_obj.get("price", {})
    seller_ip = seller_obj.get("ip", "unknown")

    for resource in PRICED_RESOURCES:
        demand = resources.get(resource, {})
        demand_per_unit = demand.get("demand_per_unit", 0)
        if not demand_per_unit:
            continue

        if resource not in seller_price:
            raise PricingMissingError(
                f"Seller {seller_ip} does not have pricing for resource: {resource}"
            )

        budget = demand.get("budget", 0)
        price = seller_price[resource]

        logger.info(
            f"Resource={resource} DemandPerUnit={demand_per_unit} "
            f"Budget={budget:.4f} SellerPrice={price:.4f}"
        )

        if budget < price:
            logger.info(
                f"Budget check FAILED for resource={resource}: "
                f"buyer budget {budget:.4f} < seller price {price:.4f}"
            )
            return False

        logger.info(
            f"Budget check PASSED for resource={resource}: "
            f"buyer budget {budget:.4f} >= seller price {price:.4f}"
        )

    return True
