"""Session 20 — Memory & Context Follow-up."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'From that list, which handlers are related to "driver"?',
    'Show the handler context for the first driver-related handler',
    'Is business registration number 1234567890 valid?',
    'Summarize: how many order types and payment methods does the system support?',
]

if __name__ == "__main__":
    run_session(20, "Memory & Context Follow-up", QUESTIONS)
