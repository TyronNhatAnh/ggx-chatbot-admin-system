"""Session 23 — Driver Statement Summary."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    "Show me the driver report summary for January 2026, org ID 17",
    "What is the total payToDriver amount across all drivers for org 17 in January 2026?",
    "Which driver had the highest finalPrice in January 2026 for org 17?",
    "Show me the driver report summary for driver ID 225324 in January 2026",
    "How many distinct drivers settled orders for org 17 in January 2026?",
]

if __name__ == "__main__":
    run_session(23, "Driver Statement Summary", QUESTIONS)