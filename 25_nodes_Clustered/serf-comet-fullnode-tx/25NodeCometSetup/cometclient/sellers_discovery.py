import requests
import logging
import math

BUYER_URL = "http://localhost:8090"
HILBERT_URL = "http://localhost:4041/hilbert-output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

RESOURCE_MAP = {
    "vcpu": {"price": "price_per_cpu", "score": "score_per_cpu", "available": "cpu"},
    "ram": {"price": "price_per_ram", "score": "score_per_ram", "available": "ram"},
    "storage": {"price": "price_per_storage", "score": "score_per_storage", "available": "storage"},
    "vgpu": {"price": "price_per_gpu", "score": "score_per_gpu", "available": "gpu"},
}


def notify_buyer(ip: str, resources: dict) -> dict:
    url = f"{BUYER_URL}/buyer"
    payload = {
        "ip": ip,
        "resources": resources
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


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
    # Step 1: Active resources
    active = {
        k: v for k, v in resources.items()
        if v.get("demand_per_unit", 0) > 0
    }

    if not active:
        logger.warning("No active resources in buyer request")
        return None
    if not discovery_results:
        logger.warning("No sellers available after discovery")
        return None
    primary_resource = max(active, key=lambda k: active[k]["demand_per_unit"])
    price_field = RESOURCE_MAP[primary_resource]["price"]
    logger.info(f"Primary resource: {primary_resource}, filtering sellers by: {price_field}")
    valid_sellers = [
        s for s in discovery_results
        if s.get(price_field) is not None
    ]

    if not valid_sellers:
        logger.warning(f"No sellers have valid price for {primary_resource}")
        return None
    selected = min(valid_sellers, key=lambda s: s[price_field])

    # Step 4: calculate total amount
    amount = 0.0
    for resource_key, resource_val in active.items():
        demand = resource_val.get("demand_per_unit", 0)
        price_field_for_resource = RESOURCE_MAP[resource_key]["price"]
        price = selected.get(price_field_for_resource, 0.0)

        cost = demand * price
        amount += cost

        logger.info(f"{resource_key}: demand={demand} x price={price} = {cost}")

    amount = math.ceil(amount)

    logger.info(
        f"Selected seller: {selected.get('name')} at {selected.get('ip')} | "
        f"{price_field}: {selected.get(price_field)} | Total amount: {amount}"
    )

    return {
        "seller": selected,
        "amount": amount
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
        "score": score
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
        "score": score
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