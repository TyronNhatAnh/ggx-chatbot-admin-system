"""Session 05 — Multi-turn Order Context (follow-up chain, shared conversation_id)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Find orders assigned to a driver named "TyronTest" — are there any results?',
    'Show me the full details of the first order in those results',
    'What is the payment status of that order?',
    'Is there a cancellation fee if we cancel it now?',
    'Any change history on that order?',
]

if __name__ == "__main__":
    run_session(5, "Multi-turn Order Context", QUESTIONS)
