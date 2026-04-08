"""Session 16 — Endpoint Search & Handler Context (search_endpoints, get_handler_context, list_available_docs)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Which API handles fetching order details?',
    'Which handler is responsible for cancelling an order?',
    'What handler processes the /admin/orders endpoint?',
    'What does the GetOrderDetail handler do? Which services does it call?',
    'What steps does the CancelOrderB2C handler perform?',
]

if __name__ == "__main__":
    run_session(16, "Endpoint Search & Handler Context (search_endpoints, get_handler_context, list_available_docs)", QUESTIONS)
