"""Session 04 — Order History (get_order_history)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Show me the change history for order 1348185',
    'Was the price of order 1348186 ever modified? Who changed it?',
    'What statuses has order 1348187 gone through over time?',
    'Show the 10 most recent changes for order 1348188',
    'Which user last updated the details of order 1348189?',
]

if __name__ == "__main__":
    run_session(4, "Order History (get_order_history)", QUESTIONS)
