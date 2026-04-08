"""Session 19 — Cross-domain Multi-tool."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'What is the name of org ID 10? How many completed orders does it have this month?',
    'Who is driver ID 225324? Do they have any active orders right now?',
    'Who is the customer and org for order 1348180?',
    'Look up more details about that organization',
    'statusCd=5 is Cancelled — list the 3 most recently cancelled orders for org ID 10',
]

if __name__ == "__main__":
    run_session(19, "Cross-domain Multi-tool", QUESTIONS)
