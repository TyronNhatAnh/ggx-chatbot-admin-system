"""Common tools exposed to the Gemini AI model.

Read-only wrappers around CommonServiceClient.
"""

from app.limits import MAX_LIST_RESULTS
from app.services.common_service_client import get_common_client


def get_vehicle_prices(order_type: str) -> dict:
    """Get vehicle prices by order type (GET /vehicles?orderType=).
    order_type must be one of: HomeMoving, Quick, Delivery."""
    return get_common_client().get_vehicle_prices(order_type=order_type)


def get_common_vehicle_pools() -> dict:
    """List vehicles and vehicle pools (GET /vehicles/vehicle-pools)."""
    return get_common_client().get_vehicle_pools()


def get_services_by_vehicle_pool(
    order_type: str,
    vehicle_pool_id: int,
    region_id: int = 0,
) -> dict:
    """Get available services for a vehicle pool (GET /vehicles/services).
    order_type: HomeMoving, Quick, Delivery. region_id is optional."""
    return get_common_client().get_services_by_vehicle_pool(
        order_type=order_type,
        vehicle_pool_id=vehicle_pool_id,
        region_id=region_id if region_id > 0 else None,
    )


def get_addresses(
    keyword: str,
    user_id: int = 0,
    page: int = 1,
    size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search saved addresses (GET /addresses).
    keyword is required. user_id optional; if omitted, service resolves from auth context."""
    return get_common_client().get_addresses(
        keyword=keyword,
        user_id=user_id if user_id > 0 else None,
        page=page,
        size=size,
    )


def search_api_addresses(
    keyword: str,
    page: int = 1,
    size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search external API addresses by keyword (GET /addresses/search)."""
    return get_common_client().search_api_addresses(
        keyword=keyword,
        page=page,
        size=size,
    )


def search_api_address_details(keyword: str, jibun_address: str = "") -> dict:
    """Get detailed external address results (GET /addresses/search-details).
    Optional jibun_address improves precision."""
    return get_common_client().search_api_address_details(
        keyword=keyword,
        jibun_address=jibun_address or None,
    )


def list_guest_ads() -> dict:
    """List active guest ads (GET /guest/ads)."""
    return get_common_client().list_guest_ads()


def list_home_moving_goods_categories() -> dict:
    """List home-moving goods categories (GET /guest/home-moving/goods-categories)."""
    return get_common_client().list_home_moving_goods_categories()


def list_home_moving_vehicles() -> dict:
    """List home-moving vehicles and pools (GET /guest/home-moving/vehicles)."""
    return get_common_client().list_home_moving_vehicles()
