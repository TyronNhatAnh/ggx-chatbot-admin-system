"""Session 02 — Order List, Filter & Submit (get_orders_admin_panel, submit_order)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'List the 5 most recent orders in the system',
    'Show me all orders currently Completed (status 3) today',
    'List orders assigned to driver ID 360412 this week',
    'Are there any recently cancelled orders for org ID 17?',
    'Search for orders with keyword "mymy" — by customer or driver name',
    'What fields does submit_order need to create a Quick order? (describe without placing the order)',
]

if __name__ == "__main__":
    run_session(2, "Order List, Filter & Submit (get_orders_admin_panel, submit_order)", QUESTIONS)
