import json

import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.tools.order_tools import get_order, search_orders

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Configure the Gemini client with our API key
genai.configure(api_key=settings.gemini_api_key)

app = FastAPI(title="AI Admin Assistant")

# Maps tool names (as the LLM sees them) to the actual Python functions.
# When Gemini asks to call "get_order", we look it up here and run it.
TOOL_REGISTRY = {
    "get_order": get_order,
    "search_orders": search_orders,
}

# Build the Gemini model once at startup.
# Passing the functions directly lets Gemini auto-generate the JSON schema
# from the function signatures and docstrings.
model = genai.GenerativeModel(
    model_name=settings.model_name,
    tools=[get_order, search_orders],
    system_instruction=(
        "You are a helpful admin assistant for a logistics company. "
        "Use the available tools to answer questions about orders. "
        "Always be concise and factual."
    ),
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    The main chat endpoint. Follows this flow:
      1. Receive the user's message.
      2. Send it to Gemini.
      3. If Gemini wants to call a tool, detect and execute it.
      4. Send the tool result back to Gemini.
      5. Repeat until Gemini produces a plain-text final answer.
    """

    # Start a fresh chat session for each request.
    # enable_automatic_function_calling=False means WE handle the tool loop,
    # which makes the flow explicit and easy to understand / extend.
    chat_session = model.start_chat(enable_automatic_function_calling=False)

    # Step 1 & 2 — send the user message to Gemini
    response = chat_session.send_message(request.message)

    # Step 3-5 — tool-calling loop
    # Gemini may ask to call one or more tools before giving a final answer.
    while True:
        # Collect all function calls the model wants to make in this turn
        function_calls = []
        for part in response.parts:
            fc = getattr(part, "function_call", None)
            if fc and fc.name:  # non-empty name means it's a real tool call
                function_calls.append(fc)

        # No tool calls → Gemini is done; return the final text answer
        if not function_calls:
            break

        # Step 4 — execute each requested tool and collect the results
        tool_response_parts = []
        for fc in function_calls:
            print(f"[Tool Call]   {fc.name}({dict(fc.args)})")  # useful for debugging

            tool_fn = TOOL_REGISTRY.get(fc.name)
            if tool_fn is None:
                raise HTTPException(
                    status_code=500, detail=f"LLM requested unknown tool: {fc.name}"
                )

            result = tool_fn(**dict(fc.args))
            print(f"[Tool Result] {result}")

            # Wrap the result in the format Gemini expects
            tool_response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )
            )

        # Step 5 — send all tool results back to Gemini in one message
        response = chat_session.send_message(tool_response_parts)

    return ChatResponse(reply=response.text)
