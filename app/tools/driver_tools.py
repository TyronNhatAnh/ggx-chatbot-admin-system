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


def get_vehicle_pools() -> dict:
    """List all vehicle types and vehicle pools (GET /vehicles/vehicle-pools).
    Returns vehicle pool IDs, names, titles, and associated vehicle info."""
    return get_driver_client().get_vehicle_pools()


def calculate_driver_fare(
    order_id: int,
    user_id: int,
) -> dict:
    """Calculate fare for a driver on a specific order (POST /guest/price/{orderId}).
    user_id: the driver's user ID (userId of the driver, not the customer).
    Returns the driver's price breakdown including VAT."""
    return get_driver_client().get_driver_price(
        order_id=order_id,
        user_id=user_id,
    )
