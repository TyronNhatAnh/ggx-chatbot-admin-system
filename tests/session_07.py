"""Session 07 — Organization (search_organizations)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Search for an organization named "GoGoX"',
    'List all B2B organizations in the system',
    'Which organizations have "Logistics" in their name?',
    'How many branches does org ID 17 have?',
]

if __name__ == "__main__":
    run_session(7, "Organization (search_organizations)", QUESTIONS)
