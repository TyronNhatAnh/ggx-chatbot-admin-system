import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from app.orchestrator.ai_orchestrator import AIOrchestrator


@dataclass
class _FakeFunctionCall:
    name: str
    args: dict


class _FakePart:
    def __init__(self, *, function_call=None, text: str | None = None) -> None:
        self.function_call = function_call
        self.text = text


class _FakeResponse:
    def __init__(self, *, text: str = "", function_calls: list[_FakeFunctionCall] | None = None) -> None:
        self.text = text
        calls = function_calls or []
        parts = [_FakePart(function_call=fc) for fc in calls]
        if text:
            parts.append(_FakePart(text=text))
        self.candidates = [SimpleNamespace(content=SimpleNamespace(parts=parts))]


class _FakeChatSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self._index = 0
        self.sent_messages: list[object] = []

    def send_message(self, message):
        self.sent_messages.append(message)
        response = self._responses[self._index]
        self._index += 1
        return response


class _FakeModel:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses

    def start_chat(self, enable_automatic_function_calling: bool = False):
        return _FakeChatSession(self._responses)


class OrchestratorRegressionTests(unittest.TestCase):
    def test_duplicate_tool_calls_are_suppressed(self) -> None:
        tool_calls = [
            _FakeFunctionCall("get_order", {"order_id": "1347944"}),
            _FakeFunctionCall("get_order", {"order_id": "1347944"}),
        ]
        responses = [
            _FakeResponse(function_calls=tool_calls),
            _FakeResponse(text="done"),
        ]

        call_count = {"get_order": 0}

        def get_order_stub(order_id: str):
            call_count["get_order"] += 1
            return {"orderId": order_id, "status": "Transit"}

        with patch("app.orchestrator.ai_orchestrator.create_gemini_model", return_value=_FakeModel(responses)):
            with patch.dict("app.orchestrator.ai_orchestrator.TOOL_REGISTRY", {"get_order": get_order_stub}, clear=False):
                orchestrator = AIOrchestrator()
                reply, tools_called, _ = orchestrator.chat("check order 1347944")

        self.assertEqual(reply, "done")
        self.assertEqual(call_count["get_order"], 1)
        self.assertEqual(tools_called, ["get_order"])

    def test_max_tool_loop_returns_fallback(self) -> None:
        responses = [
            _FakeResponse(function_calls=[_FakeFunctionCall("get_order", {"order_id": "11111"})]),
            _FakeResponse(function_calls=[_FakeFunctionCall("get_order", {"order_id": "22222"})]),
            _FakeResponse(function_calls=[_FakeFunctionCall("get_order", {"order_id": "33333"})]),
        ]

        call_count = {"get_order": 0}

        def get_order_stub(order_id: str):
            call_count["get_order"] += 1
            return {"orderId": order_id, "status": "Transit"}

        with patch("app.orchestrator.ai_orchestrator.create_gemini_model", return_value=_FakeModel(responses)):
            with patch.dict("app.orchestrator.ai_orchestrator.TOOL_REGISTRY", {"get_order": get_order_stub}, clear=False):
                orchestrator = AIOrchestrator()
                reply, tools_called, _ = orchestrator.chat("check orders")

        self.assertIn("tool-calling cycle became too long", reply)
        self.assertEqual(call_count["get_order"], 2)
        self.assertEqual(tools_called, ["get_order", "get_order"])


if __name__ == "__main__":
    unittest.main()
