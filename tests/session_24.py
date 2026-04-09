"""Session 24 — Driver Statement Detail."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    "Show me the per-order driver settlement detail for driver ID 225324, January 2026, org 17",
    "List driver payout records for org 17 in January 2026 - page 1, 20 rows",
    "Show page 2 of those results",
    "For driver 225324 in January 2026, which order had the highest commissionPrice?",
    "Show driver settled orders for org 17 in January 2026 with e-tax status \"발급완료\"",
]

if __name__ == "__main__":
    run_session(24, "Driver Statement Detail", QUESTIONS)