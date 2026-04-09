"""Session 25 — Report Multi-turn & Edge Cases."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    "Give me both the summary and detail for customer org 17, March 2026, Credit payment",
    # "I need a driver settlement report for org 17 last month - summary first, then detail breakdown for the top earner",
    # "What was the payToDriver amount for that driver?",
    # "What does the \"CustomerFare\" field mean in the driver detail report?",
    # "Why are the residentRegistrationNumber and phoneNumber masked in driver reports?",
]

if __name__ == "__main__":
    run_session(25, "Report Multi-turn & Edge Cases", QUESTIONS)