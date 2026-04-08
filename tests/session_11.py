"""Session 11 — Vehicle Pools (get_vehicle_pools)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'What vehicle pools are available in the system?',
    'What are the vehicle pool IDs and their names?',
    'Which pool does a small truck belong to?',
    'What is the ID of that pool?',
    'List all vehicle pools and briefly describe each one',
]

if __name__ == "__main__":
    run_session(11, "Vehicle Pools (get_vehicle_pools)", QUESTIONS)
