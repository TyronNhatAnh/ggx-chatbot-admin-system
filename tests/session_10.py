"""Session 10 — Driver Profile & Search (get_driver, search_drivers)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'What is the profile of driver ID 225324',
    'Find a driver with name or phone "0106083106"',
    'What is the orderCap and creditAmount of driver "tyron.driver1"?',
    'Search for drivers named "tyron" — how many results come back?',
    'What level and vehicle type does driver ID 225324 have?',
]

if __name__ == "__main__":
    run_session(10, "Driver Profile & Search (get_driver, search_drivers)", QUESTIONS)
