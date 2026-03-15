# ---------------------------------------------------------------------------
# Mock driver database
# In a real project these functions would query a database or an internal API.
# ---------------------------------------------------------------------------

MOCK_DRIVERS: dict[str, dict] = {
    "DRV-001": {
        "id": "DRV-001",
        "name": "James Nguyen",
        "status": "active",
        "current_order_id": "ORD-001",
        "rating": 4.9,
        "vehicle": "Toyota Vios",
        "phone": "+60-111-234-5678",
    },
    "DRV-002": {
        "id": "DRV-002",
        "name": "Maria Santos",
        "status": "active",
        "current_order_id": "ORD-004",
        "rating": 4.7,
        "vehicle": "Honda City",
        "phone": "+60-111-876-5432",
    },
    "DRV-003": {
        "id": "DRV-003",
        "name": "Kevin Park",
        "status": "active",
        "current_order_id": "ORD-005",
        "rating": 4.5,
        "vehicle": "Mitsubishi Attrage",
        "phone": "+60-111-555-9900",
    },
    "DRV-004": {
        "id": "DRV-004",
        "name": "Linda Tran",
        "status": "offline",
        "current_order_id": None,
        "rating": 4.8,
        "vehicle": "Toyota Vios",
        "phone": "+60-111-321-0987",
    },
}


def get_driver(driver_id: str) -> dict:
    """Fetch details for one driver by ID (e.g. 'DRV-001')."""
    driver = MOCK_DRIVERS.get(driver_id.upper())
    if driver:
        return driver
    return {"error": f"Driver '{driver_id}' not found."}


def list_active_drivers() -> dict:
    """List all currently active (on-duty) drivers."""
    active = [d for d in MOCK_DRIVERS.values() if d["status"] == "active"]
    return {"active_drivers": active, "count": len(active)}
