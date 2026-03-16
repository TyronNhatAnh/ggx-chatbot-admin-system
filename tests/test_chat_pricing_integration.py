import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.api_core.exceptions import ResourceExhausted

import app.main as main
from app.main import app


class _StubOrchestrator:
    def __init__(self, reply: str, tools_called: list[str], conversation_id: str = "test-conv-1") -> None:
        self._reply = reply
        self._tools_called = tools_called
        self._conversation_id = conversation_id

    def chat(self, message: str, conversation_id: str | None = None) -> tuple[str, list[str], str]:
        if "raise_quota" in message:
            raise ResourceExhausted("quota")
        return self._reply, self._tools_called, conversation_id or self._conversation_id


class ChatPricingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        main._reset_chat_rate_limiter()
        self._settings_backup = {
            "chat_auth_enabled": main.settings.chat_auth_enabled,
            "chat_api_key": main.settings.chat_api_key,
            "chat_rate_limit_enabled": main.settings.chat_rate_limit_enabled,
            "chat_rate_limit_requests": main.settings.chat_rate_limit_requests,
            "chat_rate_limit_window_seconds": main.settings.chat_rate_limit_window_seconds,
        }
        main.settings.chat_auth_enabled = True
        main.settings.chat_api_key = "test-chat-key"
        main.settings.chat_rate_limit_enabled = True
        main.settings.chat_rate_limit_requests = 50
        main.settings.chat_rate_limit_window_seconds = 60

    def tearDown(self) -> None:
        main.settings.chat_auth_enabled = self._settings_backup["chat_auth_enabled"]
        main.settings.chat_api_key = self._settings_backup["chat_api_key"]
        main.settings.chat_rate_limit_enabled = self._settings_backup["chat_rate_limit_enabled"]
        main.settings.chat_rate_limit_requests = self._settings_backup["chat_rate_limit_requests"]
        main.settings.chat_rate_limit_window_seconds = self._settings_backup["chat_rate_limit_window_seconds"]
        main._reset_chat_rate_limiter()

    @staticmethod
    def _auth_headers() -> dict[str, str]:
        return {"x-api-key": "test-chat-key"}

    def test_chat_returns_pricing_tool_for_guest_estimate(self) -> None:
        stub = _StubOrchestrator(
            "Estimated base price is 12000 KRW.",
            ["estimate_guest_price"],
        )
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "estimate guest price from A to B"},
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["reply"], "Estimated base price is 12000 KRW.")
        self.assertEqual(body["tools_called"], ["estimate_guest_price"])
        self.assertEqual(body["conversation_id"], "test-conv-1")

    def test_chat_returns_get_order_for_existing_order_price_reason(self) -> None:
        stub = _StubOrchestrator(
            "Order price includes base fee and surcharge components.",
            ["get_order_detail"],
        )
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "why order 1317562 has this price"},
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tools_called"], ["get_order_detail"])
        self.assertEqual(body["conversation_id"], "test-conv-1")

    def test_chat_returns_pricing_tool_for_home_moving_estimate(self) -> None:
        stub = _StubOrchestrator(
            "Home-moving estimate is 56000 KRW.",
            ["estimate_guest_home_moving_price"],
        )
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "home moving estimate please"},
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tools_called"], ["estimate_guest_home_moving_price"])
        self.assertEqual(body["conversation_id"], "test-conv-1")

    def test_chat_maps_quota_error_to_429(self) -> None:
        stub = _StubOrchestrator("", [])
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "raise_quota"},
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 429)

    def test_chat_requires_api_key_when_auth_enabled(self) -> None:
        stub = _StubOrchestrator("ok", ["get_order_detail"])
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "status ORD-1"},
            )

        self.assertEqual(response.status_code, 401)

    def test_chat_rate_limit_returns_429(self) -> None:
        main.settings.chat_rate_limit_requests = 2
        main.settings.chat_rate_limit_window_seconds = 60

        stub = _StubOrchestrator("ok", ["get_order_detail"])
        with patch("app.main.get_orchestrator", return_value=stub):
            first = self.client.post(
                "/chat",
                json={"message": "status ORD-1"},
                headers=self._auth_headers(),
            )
            second = self.client.post(
                "/chat",
                json={"message": "status ORD-2"},
                headers=self._auth_headers(),
            )
            third = self.client.post(
                "/chat",
                json={"message": "status ORD-3"},
                headers=self._auth_headers(),
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)
        self.assertIn("Retry-After", third.headers)

    def test_chat_echoes_request_id_header(self) -> None:
        stub = _StubOrchestrator("ok", ["get_order_detail"])
        with patch("app.main.get_orchestrator", return_value=stub):
            response = self.client.post(
                "/chat",
                json={"message": "status ORD-1"},
                headers={
                    **self._auth_headers(),
                    "x-request-id": "req-e2e-123",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), "req-e2e-123")


if __name__ == "__main__":
    unittest.main()
