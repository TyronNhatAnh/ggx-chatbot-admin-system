# TODO: connect each function to a real driver service client (similar to order_tools.py → OrderServiceClient).


def get_driver(driver_id: str) -> dict:
    """Fetch details for one driver by ID."""
    # TODO: call driver service client — e.g. get_driver_client().get_driver(driver_id)
    raise NotImplementedError("get_driver is not yet connected to a real service.")


def list_active_drivers() -> dict:
    """List all currently active (on-duty) drivers."""
    # TODO: call driver service client — e.g. get_driver_client().list_active_drivers()
    raise NotImplementedError("list_active_drivers is not yet connected to a real service.")
