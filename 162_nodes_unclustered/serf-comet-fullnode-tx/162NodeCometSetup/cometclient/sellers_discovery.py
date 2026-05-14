from typing import Any
import requests
import logging
import math

BUYER_URL = "http://localhost:8090"
HILBERT_URL = "http://localhost:4041/hilbert-output"
logger = logging.getLogger(__name__)

RESOURCE_MAP = {
    "vcpu": {"price": "price_per_cpu", "score": "score_per_cpu", "available": "cpu"},
    "ram": {"price": "price_per_ram", "score": "score_per_ram", "available": "ram"},
    "storage": {"price": "price_per_storage", "score": "score_per_storage", "available": "storage"},
    "vgpu": {"price": "price_per_gpu", "score": "score_per_gpu", "available": "gpu"},
}

SIGMA_SCORE_A = 1.0  # shape parameter for score sigmoid
SIGMA_SCORE_B = 7.6  # steepness for score sigmoid
SIGMA_CARBON_A = 1.0  # shape parameter for carbon sigmoid
SIGMA_CARBON_B = 76.0  # steepness for carbon sigmoid

# Utility weights (α, β, γ) — all 1 per paper Section 2
ALPHA = 1.0  # weight for score satisfaction
BETA = 1.0  # weight for carbon satisfaction
GAMMA = 1.0  # weight for price


def _sigmoid(x: float, a: float, b: float) -> float:
    """
    Sigmoid function from the paper:
        σ(x) = 1 / (1 + a * exp(-b * x))

    Clipped to avoid overflow on extreme inputs.
    """
    exponent = -b * x
    # Clip to avoid math.exp overflow (beyond ~709 is inf for float64)
    exponent = max(-500.0, min(500.0, exponent))
    return 1.0 / (1.0 + a * math.exp(exponent))


def _compute_utility(
        price: float,
        quantity: float,
        provider_score: float,
        buyer_score_expectation: float,
        provider_carbon: float,
        buyer_carbon_tolerance: float,
) -> float:
    """
    Computes buyer utility for a single provider (Equation 1 from the paper):

        U_i(p_j, S_j, E_j) = α * σ_s(S_j − D_i)
                            + β * σ_e(E_i − E_j)
                            − γ * p_j * Q_i

    Args:
        price:                   p_j  — provider's unit price for the primary resource
        quantity:                Q_i  — buyer's demanded quantity
        provider_score:          S_j  — provider's performance score
        buyer_score_expectation: D_i  — buyer's expected score threshold
        provider_carbon:         E_j  — provider's carbon intensity
        buyer_carbon_tolerance:  E_i  — buyer's carbon tolerance threshold

    Returns:
        Scalar utility value (higher = more preferred).
    """
    # Score satisfaction: σ_s(S_j − D_i)
    # Positive when provider score exceeds buyer expectation
    score_satisfaction = _sigmoid(
        provider_score - buyer_score_expectation,
        a=SIGMA_SCORE_A,
        b=SIGMA_SCORE_B,
    )

    # Carbon satisfaction: σ_e(E_i − E_j)
    # Positive when provider emits less than buyer's tolerance
    carbon_satisfaction = _sigmoid(
        buyer_carbon_tolerance - provider_carbon,
        a=SIGMA_CARBON_A,
        b=SIGMA_CARBON_B,
    )

    # Price cost term: γ * p_j * Q_i
    price_cost = GAMMA * price * quantity

    utility = (
            ALPHA * score_satisfaction
            + BETA * carbon_satisfaction
            - price_cost
    )

    logger.info(
        f"  Utility components — "
        f"score_sat={score_satisfaction:.6f} (S_j={provider_score}, D_i={buyer_score_expectation}), "
        f"carbon_sat={carbon_satisfaction:.6f} (E_i={buyer_carbon_tolerance}, E_j={provider_carbon}), "
        f"price_cost={price_cost:.6f} (p={price}, Q={quantity}) "
        f"=> U={utility:.6f}"
    )
    return utility


def notify_buyer(ip: str, resources: dict) -> Any | None:
    try:
        url = f"{BUYER_URL}/buyer"
        payload = {
            "ip": ip,
            "resources": resources
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")


def notify_fail_tx_buyer(tx: dict):
    try:
        url = f"{BUYER_URL}/fail_tx"
        payload = {
            "tx": tx
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        if response.status_code in (200, 204):
            logger.info("Tx details sent successfully")
        else:
            logger.error(f"Tx details couldn't be sent due to status code: {response.status_code}")
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")


def find_sellers() -> dict:
    try:
        logger.info("Fetching sellers from Hilbert...")
        response = requests.get(HILBERT_URL, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching Hilbert data: {e}")
        return {}


def select_seller(resources: dict, discovery_results: list) -> dict | None:
    """
    Selects the best seller using the buyer utility model (Eq. 1 & 2):

        j* = argmax_{j ∈ P_feasible} U_i(p_j, S_j, E_j)

    The utility is computed for the PRIMARY resource — the one with the
    highest demand_per_unit — using:
      - Provider score (score_per_<resource>) vs buyer's score expectation (D_i)
      - Provider carbon (score_carbon) vs buyer's carbon tolerance (E_i)
      - Provider price (price_per_<resource>) and buyer's demanded quantity (Q_i)

    Hard constraint: providers missing the primary-resource price field
    are excluded (utility = -∞).
    """
    # ----------------------------------------------------------------
    # Step 1: Identify active resources (demand_per_unit > 0)
    # ----------------------------------------------------------------
    active = {
        k: v for k, v in resources.items()
        if isinstance(v, dict) and v.get("demand_per_unit", 0) > 0
    }

    # ----------------------------------------------------------------
    # Step 2: Identify primary resource (highest demand_per_unit)
    # ----------------------------------------------------------------
    primary_resource = max(active, key=lambda k: active[k]["demand_per_unit"])
    primary_demand = active[primary_resource]["demand_per_unit"]
    price_field = RESOURCE_MAP[primary_resource]["price"]
    score_field = RESOURCE_MAP[primary_resource]["score"]

    # Buyer's score expectation (D_i) and carbon tolerance (E_i) for primary resource
    buyer_score_expectation = active[primary_resource].get("score", 0.0)
    buyer_carbon_tolerance = resources.get("carbon", {}).get("score", 0.0)
    logger.info(f"Buyer Carbon tolerance: {buyer_carbon_tolerance}")

    logger.info(
        f"[select_seller] Primary resource: '{primary_resource}' | "
        f"demand Q_i={primary_demand} | price_field='{price_field}' | "
        f"score_field='{score_field}'"
    )
    logger.info(
        f"[select_seller] Buyer parameters — "
        f"D_i (score expectation)={buyer_score_expectation}, "
        f"E_i (carbon tolerance)={buyer_carbon_tolerance}"
    )

    # ----------------------------------------------------------------
    # Step 3: Evaluate utility for each provider (hard-constraint filter
    #         + argmax as per Eq. 2)
    # ----------------------------------------------------------------
    best_seller = None
    best_utility = float("-inf")

    for provider in discovery_results:
        name = provider.get("name", provider.get("ip", "unknown"))

        # Hard constraint: provider must have a price for the primary resource
        price = provider.get(price_field)
        if price is None:
            logger.info(
                f"[select_seller] Provider '{name}' excluded — "
                f"missing price field '{price_field}' (utility = -∞)"
            )
            continue

        provider_score = provider.get(score_field, 0.0)
        provider_carbon = provider.get("score_carbon", 0.0)

        logger.info(
            f"[select_seller] Evaluating provider '{name}' — "
            f"p_j={price}, S_j={provider_score}, E_j={provider_carbon}"
        )

        utility = _compute_utility(
            price=price,
            quantity=primary_demand,
            provider_score=provider_score,
            buyer_score_expectation=buyer_score_expectation,
            provider_carbon=provider_carbon,
            buyer_carbon_tolerance=buyer_carbon_tolerance,
        )

        logger.info(f"[select_seller] Provider '{name}' → utility U={utility:.6f}")

        if utility > best_utility:
            best_utility = utility
            best_seller = provider

    if best_seller is None:
        logger.warning(
            "[select_seller] All providers failed hard constraints — no seller selected"
        )
        return None

    # ----------------------------------------------------------------
    # Step 4: Compute total transaction amount across ALL active resources
    #         using the winning seller's prices
    # ----------------------------------------------------------------
    amount = 0.0
    logger.info(
        f"[select_seller] Winner: '{best_seller.get('name')}' "
        f"(U={best_utility:.6f}) — computing total transaction amount"
    )

    for resource_key, resource_val in active.items():
        demand = resource_val.get("demand_per_unit", 0)
        res_price_field = RESOURCE_MAP[resource_key]["price"]
        price = best_seller.get(res_price_field, 0.0)
        cost = demand * price
        amount += cost
        logger.info(
            f"[select_seller]   {resource_key}: "
            f"Q={demand} × p={price} = {cost:.4f}"
        )

    amount = math.ceil(amount)
    logger.info(
        f"[select_seller] Final — seller='{best_seller.get('name')}' "
        f"at {best_seller.get('ip')} | "
        f"utility={best_utility:.6f} | total_amount={amount}"
    )

    return {
        "seller": best_seller,
        "amount": amount,
    }


def create_empty_sellers():
    price, score = create_price_score(
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0
    )

    return {
        "name": "",
        "ip": "",
        "cpu": 0,
        "ram": 0.0,
        "storage": 0,
        "gpu": 0,
        "price": price,
        "score": score,
        "score_carbon": 0.0
    }


def create_seller(raw_seller):
    price, score = create_price_score(
        raw_seller.get("price_per_cpu", 0.0),
        raw_seller.get("price_per_ram", 0.0),
        raw_seller.get("price_per_storage", 0.0),
        raw_seller.get("price_per_gpu", 0.0),
        raw_seller.get("score_per_cpu", 0.0),
        raw_seller.get("score_per_ram", 0.0),
        raw_seller.get("score_per_storage", 0.0),
        raw_seller.get("score_per_gpu", 0.0)
    )

    return {
        "name": raw_seller.get("name", ""),
        "ip": raw_seller.get("ip", ""),
        "cpu": raw_seller.get("cpu", 0),
        "ram": raw_seller.get("ram", 0.0),
        "storage": raw_seller.get("storage", 0),
        "gpu": raw_seller.get("gpu", 0),
        "price": price,
        "score": score,
        "score_carbon": raw_seller.get("score_carbon", 0.0)
    }


def create_price_score(price_per_cpu, price_per_ram, price_per_storage, price_per_gpu,
                       score_per_cpu, score_per_ram, score_per_storage, score_per_gpu):
    price = {
        "vcpu": price_per_cpu,
        "ram": price_per_ram,
        "storage": price_per_storage,
        "vgpu": price_per_gpu
    }

    score = {
        "vcpu": score_per_cpu,
        "ram": score_per_ram,
        "storage": score_per_storage,
        "vgpu": score_per_gpu
    }

    return price, score
