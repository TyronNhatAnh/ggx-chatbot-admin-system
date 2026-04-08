"""Session 14 — Address Search (get_addresses, search_api_addresses, search_api_address_details)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Search for the address "서울 종로구 새문안로" in the system',
    'Search external addresses with keyword "서울 종로구 새문안로"',
    'Find saved addresses for user ID 10001 with keyword "서울 종로구 새문안로"',
    'Get detailed address results for "서울 종로구 새문안로"',
    'What addresses match the keyword "서울 종로구 새문안로"?',
]

if __name__ == "__main__":
    run_session(14, "Address Search (get_addresses, search_api_addresses, search_api_address_details)", QUESTIONS)
