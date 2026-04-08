"""Session 12 — Driver Fare (calculate_driver_fare)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Calculate the fare for driver ID 225324 on order ID 123456',
    'How much will driver ID 225324 earn from order 654321?',
    'What does the fare breakdown look like for driver 225324 on order 111111?',
    'How much VAT is included in the fare for driver 225324 on order 123456?',
    'Find a driver named "Tran Van B", then calculate their fare on order 999',
]

if __name__ == "__main__":
    run_session(12, "Driver Fare (calculate_driver_fare)", QUESTIONS)
