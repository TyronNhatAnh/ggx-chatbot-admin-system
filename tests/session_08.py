"""Session 08 — Branch (search_branches)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Find a branch with "서울" in the name',
    'List all branches under org ID 17',
    'Which branches have "서울" in their name?',
    'What is the address of that branch?',
]

if __name__ == "__main__":
    run_session(8, "Branch (search_branches)", QUESTIONS)
