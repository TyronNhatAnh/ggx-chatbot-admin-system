"""Driver tools exposed to the Gemini AI model.

Read-only wrappers around DriverServiceClient.
"""

from app.services.driver_service_client import get_driver_client
from app.limits import MAX_LIST_RESULTS


def get_driver(driver_id: int) -> dict:
    """Get driver profile by driver/user ID (GET /driver?id=).
    Returns operational fields: orderCap, creditAmount, driverLevelId, licenseNumber, vehicleInfo."""
    return get_driver_client().get_driver(driver_id)


def search_drivers(
    keyword: str,
    page_index: int = 1,
    page_size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search drivers by keyword (GET /driver/search). Matches name or phone number.
    Results paginated (default page_size=5). Use page_index to get additional pages."""
    return get_driver_client().search_drivers(
        keyword=keyword,
        page_index=page_index,
        page_size=page_size,
    )


def get_driver_location_history(
    driver_user_id: int,
    from_time: str,
    to_time: str,
) -> dict:
    """Get driver GPS location history (GET /driver/location-history).
    Times must be in Seoul timezone, format: YYYY-MM-DD HH:MM:SS (e.g. 2024-01-15 09:00:00).
    Returns list of lat/lon points with timestamps."""
    return get_driver_client().get_driver_location_history(
        driver_user_id=driver_user_id,
        from_time=from_time,
        to_time=to_time,
    )


def search_driver_report(
    driver_type: str,
    keyword: str,
    page_index: int = 1,
    page_size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search drivers in driver-report context (GET /driver-report/driver/search).
    driver_type: 'normalDriver' for platform drivers, 'externalDriver' for vendor/external drivers.
    Returns id, name, phoneNumber. Paginated."""
    return get_driver_client().search_driver_report(
        driver_type=driver_type,
        keyword=keyword,
        page_index=page_index,
        page_size=page_size,
    )


def get_vehicle_pools() -> dict:
    """List all vehicle types and vehicle pools (GET /vehicles/vehicle-pools).
    Returns vehicle pool IDs, names, titles, and associated vehicle info."""
    return get_driver_client().get_vehicle_pools()


def calculate_driver_fare(
    order_id: int,
    user_id: int,
    price_request: dict,
) -> dict:
    """Calculate fare for driver (POST /guest/price/{orderId}).
    price_request: dict with required fields (see driver_handler.go model.DriverCalcPriceOrderRequest).
    Returns price breakdown and driver fare."""
    return get_driver_client().get_driver_price(
        order_id=order_id,
        user_id=user_id,
        price_request=price_request,
    )
