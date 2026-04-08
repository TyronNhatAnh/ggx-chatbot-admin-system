"""Session 06 — User Lookup (get_user_profile, search_users)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'What is the profile of user name "tyron"?',
    'Find a user with phone or email 0106083106',
    'Is there a user named "TyronTestCreateAPICW" in the system? What is their ID?',
    'Find all users belonging to org ID 17',
]

if __name__ == "__main__":
    run_session(6, "User Lookup (get_user_profile, search_users)", QUESTIONS)
