"""Persist inbox session for pick-by-number."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from email_inbox.formatting import InboxRow


@dataclass(frozen=True)
class SessionRow:
    n: int
    mailbox: str
    thread_id: str
    from_header: str
    subject: str
    date: str
    label: str
    message_count: int = 1
    latest_message_id: str = ""
    snippet: str = ""


def build_session(
    rows: list[InboxRow],
    *,
    query: str,
) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "rows": [
            asdict(
                SessionRow(
                    n=i,
                    mailbox=r.mailbox,
                    thread_id=r.thread_id,
                    from_header=r.from_header,
                    subject=r.subject,
                    date=r.date,
                    label=r.label,
                    message_count=r.message_count,
                    latest_message_id=r.latest_message_id,
                    snippet=r.snippet,
                )
            )
            for i, r in enumerate(rows, start=1)
        ],
    }


def write_session(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_session(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"session not found: {path} (run `email-inbox list` first)")
    return json.loads(path.read_text(encoding="utf-8"))


def get_session_row(session: dict, n: int) -> SessionRow:
    rows = session.get("rows") or []
    for raw in rows:
        if int(raw.get("n", -1)) == n:
            return SessionRow(
                n=int(raw["n"]),
                mailbox=str(raw["mailbox"]),
                thread_id=str(raw["thread_id"]),
                from_header=str(raw.get("from") or raw.get("from_header") or ""),
                subject=str(raw["subject"]),
                date=str(raw["date"]),
                label=str(raw.get("label") or ""),
                message_count=int(raw.get("message_count") or raw.get("messageCount") or 1),
                latest_message_id=str(raw.get("latest_message_id") or ""),
                snippet=str(raw.get("snippet") or ""),
            )
    raise KeyError(f"row {n} not in session (have {len(rows)} row(s))")
