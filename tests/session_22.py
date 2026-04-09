"""Session 22 — Customer Statement Detail."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    "Show me the order-level report customer statement detail for org 17, January 2026, Credit payment",
    "List individual orders in the report customer statement for org 17, March 2026, all payment types - page 1",
    "Show page 2 of those results",
    "For org 17 in January 2026 (Credit), which order had the highest totalPrice?",
    "Which orders in the report customer statement for org 17 in March 2026 had VAT applied?",
]

if __name__ == "__main__":
    run_session(22, "Customer Statement Detail", QUESTIONS)