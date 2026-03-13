# AI Admin Assistant

Simple AI chatbot service for admin systems.

Phase 1 goal:
- Read-only assistant
- Query order data
- Explain system data

---

# Architecture

Admin UI
   │
   ▼
AI Service (FastAPI)
   │
   ▼
LLM (Gemini / OpenAI)
   │
   ▼
Tools
   │
   ▼
Order APIs

---

# Setup

Install dependencies:

make install

---

# Run

Run server:

make run

Debug mode:

make debug

---

# API

Swagger docs:

http://localhost:8000/docs

---

# Example request

POST /chat

{
 "message": "order 123 status"
}

---

# Tools

get_order(order_id)

search_orders(status)
