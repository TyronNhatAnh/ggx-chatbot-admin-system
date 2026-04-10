"""Shared session runner for tool verification tests.

Usage: called by each session_XX.py file.
Env vars (or .env):
  CHAT_BASE_URL           default: http://localhost:8000
  CHAT_API_KEY            required
  SERVICE_TOKEN           Bearer ...token...
  QUESTION_DELAY_SECONDS  seconds to wait between questions (default: 10, set 0 to disable)
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# Load .env from project root
_ROOT = Path(__file__).parent.parent
_env_file = _ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BASE_URL = os.getenv("CHAT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("CHAT_API_KEY", "69b768d2-ad24-8321-96e4-86ec1b32d448-1232edmke132e")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJfYXV0aFR5cGUiOiJNVUxUSV9BVVRIIiwiX2lzU3lzdGVtQWRtaW4iOnRydWUsIl9kZXB0SWQiOjYsIl9hZG1pbklEIjoxODYsIl9pZFRva2VuIjoiIiwiX29yZ0lkIjowLCJfcGVybWlzc2lvblJlZnJlc2giOjE3NzU3OTAyMTMsIl9hZ2VudElkIjoxNzQ0LCJfYnJhbmNoQ29kZSI6MCwiX2FkbWluUGVybWlzc2lvbiI6InN5c3RlbSxwbGF0Zm9ybSxzdXBlcixhZG1pbiIsIl9yb2xlSWQiOjE2LCJfcGVybWlzc2lvbnMiOlsiUkVQT1JUX0ZJTkFOQ0VfTEVHOndyaXRlIiwiUkVQT1JUX0ZJTkFOQ0VfTkVXOndyaXRlIiwiUkVQT1JUX0RSSVZFUl9ORVc6d3JpdGUiLCJNR01UX0FETUlOOndyaXRlIiwiTUdNVF9CMkM6d3JpdGUiLCJNR01UX0IyQjp3cml0ZSIsIk1HTVRfRFJJVkVSOndyaXRlIiwiTUdNVF9PUkdBTklaRTp3cml0ZSIsIk1HTVRfRFJJVkVSX1JFVjp3cml0ZSIsIkFERFJFU1NCT09LOndyaXRlIiwiQ09VUE9OX01LVDp3cml0ZSIsIkNPVVBPTl9NQVNURVI6d3JpdGUiLCJDT1VQT05fSVNTVUU6d3JpdGUiLCJDT1VQT05fTElTVDp3cml0ZSIsIlZFSElDTEVfTElTVDp3cml0ZSIsIlZFSElDTEVfUE9PTDp3cml0ZSIsIk9SREVSX1JFUV9MSVNUOndyaXRlIiwiT1JERVJfUkVROndyaXRlIiwiT1JERVJfQlVMSzp3cml0ZSIsIk9SREVSX0NPTlRST0w6d3JpdGUiLCJPUkRFUl9IT01FX01PVklORzp3cml0ZSIsIlJFR0lPTjp3cml0ZSIsIlBSSUNFX1pPTkU6d3JpdGUiLCJQUklDRV9BMkI6d3JpdGUiLCJQUklDRV9WRUhJQ0xFOndyaXRlIiwiUFJJQ0VfRVhUUkE6d3JpdGUiLCJQUklDRV9TUEVDSUFMOndyaXRlIiwiUFJJQ0VfUkVHSU9OOndyaXRlIiwiUFJJQ0VfQ0hBUkdJTkc6d3JpdGUiLCJQUklDRV9ST1VORERPV046d3JpdGUiLCJQUklDRV9TRVQ6d3JpdGUiLCJQUklDRV9QQVJUTkVSOndyaXRlIiwiUFJJQ0VfVkFUOndyaXRlIiwiQ09OVEVOVFM6d3JpdGUiLCJUT09MU19IRUFUTUFQOndyaXRlIl0sIl9pZCI6MCwiX2FkbWluRW1haWwiOiJ0eXJvbi5uZ3V5ZW5AZ29nb3guY29tIiwiZXhwIjoxNzc1ODAwNzE3LCJpYXQiOjE3NzU3ODk5MTN9.lerGMrupska_lmCE-n4tO8CDaVzR8qBbjO5h2R0oq8M")
QUESTION_DELAY = float(os.getenv("QUESTION_DELAY_SECONDS", "10"))

LOGS_DIR = Path(__file__).parent / "logs"


def run_session(session_id: int, label: str, questions: list[str]) -> None:
    if not API_KEY:
        print("ERROR: CHAT_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)
    if not SERVICE_TOKEN:
        print("ERROR: SERVICE_TOKEN is not set.", file=sys.stderr)
        sys.exit(1)

    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"session_{session_id:02d}_{timestamp}.md"

    client = httpx.Client(timeout=90.0)
    conversation_id: str | None = None

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Session {session_id:02d} — {label}",
        f"",
        f"**Date:** {now_str}  ",
        f"**Base URL:** {BASE_URL}  ",
        f"**Conversation ID:** _(assigned after Q1)_",
        f"",
        f"---",
        f"",
    ]

    print(f"\n{'=' * 64}")
    print(f"  Session {session_id:02d} — {label}")
    print(f"{'=' * 64}")

    for i, question in enumerate(questions, 1):
        print(f"\nQ{i}: {question}")
        lines.append(f"## Q{i}")
        lines.append(f"**Question:** {question}")
        lines.append(f"")

        payload: dict = {
            "message": question,
            "service_token": SERVICE_TOKEN,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        t0 = time.perf_counter()
        try:
            resp = client.post(
                f"{BASE_URL}/chat",
                headers={"X-API-Key": API_KEY},
                json=payload,
            )
            elapsed = time.perf_counter() - t0

            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            conversation_id = data.get("conversation_id", conversation_id)
            reply: str = data.get("reply", "")
            tools_called: list = data.get("tools_called", [])

            status = "OK"
            tools_str = ", ".join(f"`{t}`" for t in tools_called) if tools_called else "_none_"
            print(f"  Tools  : {tools_called}")
            print(f"  Elapsed: {elapsed:.2f}s")
            print(f"  Reply  : {reply[:200]}{'...' if len(reply) > 200 else ''}")

            lines.append(f"**Tools called:** {tools_str}  ")
            lines.append(f"**Elapsed:** {elapsed:.2f}s  ")
            lines.append(f"**Status:** {status}")
            lines.append(f"")
            lines.append(f"**Reply:**")
            lines.append(f"")
            lines.append(reply)

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            err = str(exc)
            print(f"  ERROR  : {err}")
            lines.append(f"**Status:** ERROR  ")
            lines.append(f"**Elapsed:** {elapsed:.2f}s  ")
            lines.append(f"**Error:** {err}")

        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        if QUESTION_DELAY > 0 and i < len(questions):
            print(f"  [delay {QUESTION_DELAY:.0f}s to avoid rate limit]")
            time.sleep(QUESTION_DELAY)

    # Patch conversation_id into header
    content = "\n".join(lines)
    if conversation_id:
        content = content.replace(
            "**Conversation ID:** _(assigned after Q1)_",
            f"**Conversation ID:** `{conversation_id}`",
        )

    log_path.write_text(content, encoding="utf-8")
    print(f"\nLog saved → {log_path.relative_to(_ROOT)}")
