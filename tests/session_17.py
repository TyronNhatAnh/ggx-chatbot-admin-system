"""Session 17 — Code Search (search_codebase)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Search the codebase for the B2COrderDetail struct definition and its fields',
    'Search the codebase: what does the Order struct look like in the backend?',
    'Search the codebase: "how is pricing calculated?"',
    'Search the codebase: which struct contains the appointmentAt field?',
    'Search for: "order cancellation validation logic"',
]

if __name__ == "__main__":
    run_session(17, "Code Search (search_codebase)", QUESTIONS)
