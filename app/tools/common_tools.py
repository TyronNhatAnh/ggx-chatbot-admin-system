"""Common tools exposed to the Gemini AI model.

Read-only wrappers around CommonServiceClient.
"""

from app.limits import MAX_LIST_RESULTS
from app.services.common_service_client import get_common_client


def get_vehicle_prices(order_type: str) -> dict:
    """Get vehicle prices by order type (GET /vehicles?orderType=).
    order_type must be one of: HomeMoving, Quick, Delivery."""
    return get_common_client().get_vehicle_prices(order_type=order_type)


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


def get_vehicle_goods(vehicle_id: int, vehicle_service_id: int, org_id: int) -> dict:
    """Get available goods types for a vehicle and organisation (GET /admin/vehicles/{vehicleId}/goods/{vehicleServiceId}?orgId=).
    Use vehiclePoolId as vehicle_id, 0 as vehicle_service_id, and the order's organizationId as org_id.
    Returns the list of valid goods type codes to use in waypoint goods items."""
    return get_common_client().get_vehicle_goods(
        vehicle_id=vehicle_id,
        vehicle_service_id=vehicle_service_id,
        org_id=org_id,
    )


