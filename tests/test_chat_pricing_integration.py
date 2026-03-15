import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.api_core.exceptions import ResourceExhausted

from app.main import app


class _StubOrchestrator:
    def __init__(self, reply: str, tools_called: list[str]) -> None:
        self._reply = reply
        self._tools_called = tools_called

    def chat(self, message: str) -> tuple[str, list[str]]:
        if "raise_quota" in message:
            raise ResourceExhausted("quota")
        return self._reply, self._tools_called


class ChatPricingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_chat_returns_pricing_tool_for_guest_estimate(self) -> None:
        stub = _StubOrchestrator(
            "Estimated base price is 12000 KRW.",
            ["estimate_guest_price"],
        )
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "estimate guest price from A to B"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["reply"], "Estimated base price is 12000 KRW.")
        self.assertEqual(body["tools_called"], ["estimate_guest_price"])

    def test_chat_returns_get_order_for_existing_order_price_reason(self) -> None:
        stub = _StubOrchestrator(
            "Order price includes base fee and surcharge components.",
            ["get_order"],
        )
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "why order 1317562 has this price"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tools_called"], ["get_order"])

    def test_chat_returns_pricing_tool_for_home_moving_estimate(self) -> None:
        stub = _StubOrchestrator(
            "Home-moving estimate is 56000 KRW.",
            ["estimate_guest_home_moving_price"],
        )
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "home moving estimate please"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tools_called"], ["estimate_guest_home_moving_price"])

    def test_chat_maps_quota_error_to_429(self) -> None:
        stub = _StubOrchestrator("", [])
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "raise_quota"},
            )

        self.assertEqual(response.status_code, 429)


if __name__ == "__main__":
    unittest.main()
