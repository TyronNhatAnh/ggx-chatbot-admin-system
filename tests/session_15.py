"""Session 15 — Enum & Status Code (lookup_enum, explain_status)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'What does statusCd=3 mean?',
    'Look up the "OrderStatus" enum — what values does it have?',
    'What payment method is PayCd=2?',
    'What does statusCd=7 mean, and which entity does it apply to?',
    'What vehicle types are defined in the "VehicleType" enum?',
]

if __name__ == "__main__":
    run_session(15, "Enum & Status Code (lookup_enum, explain_status)", QUESTIONS)
