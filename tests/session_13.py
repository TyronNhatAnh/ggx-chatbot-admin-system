"""Session 13 — Vehicle Prices (get_vehicle_prices)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'What are the vehicle prices for order type "Quick"?',
    'Show me the price list for order type "Delivery"',
    'What vehicle types and prices are available for "HomeMoving"?',
    'Compare vehicle prices between Quick and Delivery order types',
    'What vehicle tiers are available for a Quick order?',
]

if __name__ == "__main__":
    run_session(13, "Vehicle Prices (get_vehicle_prices)", QUESTIONS)
