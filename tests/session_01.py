"""Session 01 — Order Detail (get_order_detail)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Show me the full details of order 1348180',
    'What is the current status of order 1348181? Which driver is assigned?',
    'What are the waypoints for order 1348182?',
    'What payment method does order 1348190 use? What is the total amount?',
    'What goods are in order 1348180? Are there any special notes?',
]

if __name__ == "__main__":
    run_session(1, "Order Detail (get_order_detail)", QUESTIONS)
