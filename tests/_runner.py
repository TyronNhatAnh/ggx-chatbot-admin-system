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
import re
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
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJfYXV0aFR5cGUiOiJNVUxUSV9BVVRIIiwiX2lzU3lzdGVtQWRtaW4iOnRydWUsIl9kZXB0SWQiOjYsIl9hZG1pbklEIjoxODYsIl9pZFRva2VuIjoiIiwiX29yZ0lkIjowLCJfcGVybWlzc2lvblJlZnJlc2giOjE3NzYwNDU4MTAsIl9hZ2VudElkIjoxNzQ0LCJfYnJhbmNoQ29kZSI6MCwiX2FkbWluUGVybWlzc2lvbiI6InN5c3RlbSxwbGF0Zm9ybSxzdXBlcixhZG1pbiIsIl9yb2xlSWQiOjE2LCJfcGVybWlzc2lvbnMiOlsiUkVQT1JUX0ZJTkFOQ0VfTEVHOndyaXRlIiwiUkVQT1JUX0ZJTkFOQ0VfTkVXOndyaXRlIiwiUkVQT1JUX0RSSVZFUl9ORVc6d3JpdGUiLCJNR01UX0FETUlOOndyaXRlIiwiTUdNVF9CMkM6d3JpdGUiLCJNR01UX0IyQjp3cml0ZSIsIk1HTVRfRFJJVkVSOndyaXRlIiwiTUdNVF9PUkdBTklaRTp3cml0ZSIsIk1HTVRfRFJJVkVSX1JFVjp3cml0ZSIsIkFERFJFU1NCT09LOndyaXRlIiwiQ09VUE9OX01LVDp3cml0ZSIsIkNPVVBPTl9NQVNURVI6d3JpdGUiLCJDT1VQT05fSVNTVUU6d3JpdGUiLCJDT1VQT05fTElTVDp3cml0ZSIsIlZFSElDTEVfTElTVDp3cml0ZSIsIlZFSElDTEVfUE9PTDp3cml0ZSIsIk9SREVSX1JFUV9MSVNUOndyaXRlIiwiT1JERVJfUkVROndyaXRlIiwiT1JERVJfQlVMSzp3cml0ZSIsIk9SREVSX0NPTlRST0w6d3JpdGUiLCJPUkRFUl9IT01FX01PVklORzp3cml0ZSIsIlJFR0lPTjp3cml0ZSIsIlBSSUNFX1pPTkU6d3JpdGUiLCJQUklDRV9BMkI6d3JpdGUiLCJQUklDRV9WRUhJQ0xFOndyaXRlIiwiUFJJQ0VfRVhUUkE6d3JpdGUiLCJQUklDRV9TUEVDSUFMOndyaXRlIiwiUFJJQ0VfUkVHSU9OOndyaXRlIiwiUFJJQ0VfQ0hBUkdJTkc6d3JpdGUiLCJQUklDRV9ST1VORERPV046d3JpdGUiLCJQUklDRV9TRVQ6d3JpdGUiLCJQUklDRV9QQVJUTkVSOndyaXRlIiwiUFJJQ0VfVkFUOndyaXRlIiwiQ09OVEVOVFM6d3JpdGUiLCJUT09MU19IRUFUTUFQOndyaXRlIl0sIl9pZCI6MCwiX2FkbWluRW1haWwiOiJ0eXJvbi5uZ3V5ZW5AZ29nb3guY29tIiwiZXhwIjoxNzc2MDU2MzEwLCJpYXQiOjE3NzYwNDU1MTB9.7MFyviPEFAZc4oovoJ0tiMCRHcDnQoDS1L-0rIG1o58")
QUESTION_DELAY = float(os.getenv("QUESTION_DELAY_SECONDS", "10"))

LOGS_DIR = Path(__file__).parent / "logs"
SUMMARY_SLOW_THRESHOLD_SECONDS = float(os.getenv("SUMMARY_SLOW_THRESHOLD_SECONDS", "5.0"))


_SESSION_HEADER_RE = re.compile(r"^# Session (?P<session_id>\d{2}) — (?P<label>.+)$")
_QUESTION_RE = re.compile(r"^## Q(?P<question_number>\d+)$")
_QUESTION_TEXT_RE = re.compile(r"^\*\*Question:\*\* (?P<question>.+)$")
_TOOLS_RE = re.compile(r"^\*\*Tools called:\*\* (?P<tools>.+?)\s*$")
_ELAPSED_RE = re.compile(r"^\*\*Elapsed:\*\* (?P<elapsed>[0-9.]+)s\s*$")
_STATUS_RE = re.compile(r"^\*\*Status:\*\* (?P<status>.+?)\s*$")
_ERROR_RE = re.compile(r"^\*\*Error:\*\* (?P<error>.+)$")


def _parse_session_log(log_path: Path) -> dict:
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()

    session_id: int | None = None
    label = ""
    questions: list[dict] = []
    current_question: dict | None = None

    for line in content:
        if match := _SESSION_HEADER_RE.match(line):
            session_id = int(match.group("session_id"))
            label = match.group("label")
            continue

        if match := _QUESTION_RE.match(line):
            if current_question:
                questions.append(current_question)
            current_question = {
                "number": int(match.group("question_number")),
                "question": "",
                "tools": "_none_",
                "elapsed": None,
                "status": "",
                "error": "",
            }
            continue

        if current_question is None:
            continue

        if match := _QUESTION_TEXT_RE.match(line):
            current_question["question"] = match.group("question")
        elif match := _TOOLS_RE.match(line):
            current_question["tools"] = match.group("tools")
        elif match := _ELAPSED_RE.match(line):
            current_question["elapsed"] = float(match.group("elapsed"))
        elif match := _STATUS_RE.match(line):
            current_question["status"] = match.group("status")
        elif match := _ERROR_RE.match(line):
            current_question["error"] = match.group("error")

    if current_question:
        questions.append(current_question)

    return {
        "session_id": session_id,
        "label": label,
        "log_path": log_path,
        "questions": questions,
    }


def summarize_session_logs(log_paths: list[Path], output_dir: Path | None = None) -> Path | None:
    if not log_paths:
        print("\nNo session logs found to summarize.")
        return None

    runs = [_parse_session_log(path) for path in sorted(log_paths)]
    slow_threshold = SUMMARY_SLOW_THRESHOLD_SECONDS

    errors: list[dict] = []
    slow_questions: list[dict] = []
    total_questions = 0

    for run in runs:
        session_id = run["session_id"]
        label = run["label"]
        for question in run["questions"]:
            total_questions += 1
            elapsed = question["elapsed"]
            status = (question["status"] or "").upper()

            if status == "ERROR" or question["error"]:
                errors.append({
                    "session_id": session_id,
                    "label": label,
                    "question_number": question["number"],
                    "question": question["question"],
                    "elapsed": elapsed,
                    "error": question["error"],
                })

            if isinstance(elapsed, float) and elapsed >= slow_threshold:
                slow_questions.append({
                    "session_id": session_id,
                    "label": label,
                    "question_number": question["number"],
                    "question": question["question"],
                    "tools": question["tools"],
                    "elapsed": elapsed,
                })

    errors.sort(key=lambda item: (item["session_id"], item["question_number"]))
    slow_questions.sort(key=lambda item: item["elapsed"], reverse=True)

    output_dir = output_dir or LOGS_DIR
    output_dir.mkdir(exist_ok=True)
    summary_path = output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    lines = [
        "# Session Run Summary",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Logs scanned:** {len(runs)}  ",
        f"**Questions scanned:** {total_questions}  ",
        f"**API errors:** {len(errors)}  ",
        f"**Slow threshold:** >= {slow_threshold:.2f}s  ",
        f"**Slow questions:** {len(slow_questions)}  ",
        "",
        "---",
        "",
        "## API Errors",
    ]

    if errors:
        for item in errors:
            elapsed = f"{item['elapsed']:.2f}s" if isinstance(item["elapsed"], float) else "n/a"
            lines.append(
                f"- Session {item['session_id']:02d} Q{item['question_number']}: {elapsed} — {item['error'] or 'ERROR'}"
            )
            if item["question"]:
                lines.append(f"  - Question: {item['question']}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Slow Questions",
    ])

    if slow_questions:
        for item in slow_questions:
            lines.append(
                f"- Session {item['session_id']:02d} Q{item['question_number']}: {item['elapsed']:.2f}s — {item['label']}"
            )
            lines.append(f"  - Tools: {item['tools']}")
            if item["question"]:
                lines.append(f"  - Question: {item['question']}")
    else:
        lines.append("- None")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


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
