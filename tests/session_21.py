"""Session 21 — Customer Statement Summary."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    "Show me the customer usage summary for January 2025 - all payment methods",
    "How many orders did org ID 17 place in January 2025? What was the total customer fare?",
    "Give me the customer statement summary for org 17, Credit payment only, last month (March 2026)",
    "Which organization had the highest total fare in Q1 2025 (Jan-Mar)? Use payment Credit + Cash",
    "What was the totalCustomerFare across all orgs for that period?",
]

if __name__ == "__main__":
    run_session(21, "Customer Statement Summary", QUESTIONS)