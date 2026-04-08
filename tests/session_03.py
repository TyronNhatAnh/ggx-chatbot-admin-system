"""Session 03 — Payment & Cancel Fee (get_order_payment_status, get_order_cancel_fee)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Check the payment status of order 1348180',
    'Has order 1348181 been paid?',
    'How much is the cancellation fee for order 1348182 if cancelled now?',
    'Calculate the cancel fee for order 1348183',
    'Does order 1348184 have branchPay? What is the payment status?',
]

if __name__ == "__main__":
    run_session(3, "Payment & Cancel Fee (get_order_payment_status, get_order_cancel_fee)", QUESTIONS)
