"""gog CLI subprocess helpers."""

from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from email_inbox.formatting import InboxRow

GOG_TIMEOUT_SEC = 60

def authorized_gmail_accounts() -> set[str]:
    result = subprocess.run(
        ["gog", "auth", "list", "-j"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return set()
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()
    emails: set[str] = set()
    for account in data.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        email = account.get("email")
        services = account.get("services") or []
        if email and "gmail" in services:
            emails.add(str(email))
    return emails


def gmail_search_unread(
    mailbox: str,
    *,
    max_results: int,
    newer_than: str | None = None,
) -> list[dict[str, Any]]:
    query = "in:inbox is:unread"
    if newer_than:
        query = f"{query} newer_than:{newer_than}"

    result = subprocess.run(
        [
            "gog",
            "gmail",
            "search",
            query,
            "-a",
            mailbox,
            "--json",
            "--max",
            str(max_results),
        ],
        capture_output=True,
        text=True,
        timeout=GOG_TIMEOUT_SEC,
        check=False,
    )
    if result.returncode != 0:
        raise GogError(mailbox, result.stderr.strip() or f"exit {result.returncode}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GogError(mailbox, "invalid JSON from gog") from exc

    threads = data.get("threads") or []
    if not isinstance(threads, list):
        return []
    return [t for t in threads if isinstance(t, dict)]


def gmail_thread_get(mailbox: str, thread_id: str, *, full: bool = False) -> dict[str, Any]:
    cmd = ["gog", "gmail", "thread", "get", thread_id, "-a", mailbox, "-j"]
    if full:
        cmd.append("--full")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=GOG_TIMEOUT_SEC,
        check=False,
    )
    if result.returncode != 0:
        raise GogError(mailbox, result.stderr.strip() or f"exit {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GogError(mailbox, "invalid JSON from gog thread get") from exc


@dataclass
class ThreadMessage:
    message_id: str
    from_header: str
    to_header: str
    subject: str
    snippet: str
    date_header: str
    body: str = ""


def message_count_from_search(thread: dict[str, Any]) -> int:
    raw = thread.get("messageCount", thread.get("message_count", 1))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def inbox_row_message_fields_from_search(thread: dict[str, Any]) -> tuple[int, str, str]:
    """
    Derive cache fields from gog search JSON (no extra API call).

    For single-message threads, gog uses the thread id as the message id.
    """
    message_count = message_count_from_search(thread)
    thread_id = str(thread.get("id") or "")
    latest_message_id = thread_id if message_count == 1 and thread_id else ""
    snippet = _decode_snippet(str(thread.get("snippet") or ""))
    return message_count, latest_message_id, snippet


def thread_message_from_inbox_row(row: InboxRow) -> ThreadMessage | None:
    """Build ThreadMessage from list-time cache, or None if thread get is required."""
    if row.message_count > 1 or not row.latest_message_id:
        return None
    return ThreadMessage(
        message_id=row.latest_message_id,
        from_header=row.from_header,
        to_header="",
        subject=row.subject,
        snippet=row.snippet,
        date_header=row.date,
    )


def latest_message_for_inbox_row(row: InboxRow) -> ThreadMessage:
    """Latest thread message from cache or gog thread get."""
    cached = thread_message_from_inbox_row(row)
    if cached is not None:
        return cached
    thread_json = gmail_thread_get(row.mailbox, row.thread_id)
    return parse_latest_message(thread_json)


def latest_message_for_reply(row: InboxRow) -> ThreadMessage:
    """Latest thread message with full body for vault reply drafts."""
    thread_json = gmail_thread_get(row.mailbox, row.thread_id, full=True)
    return parse_latest_message(thread_json)


def parse_latest_message(thread_json: dict[str, Any]) -> ThreadMessage:
    thread = thread_json.get("thread") or {}
    messages = thread.get("messages") or []
    if not messages:
        raise ValueError("thread has no messages")
    latest = messages[-1]
    headers = _message_headers(latest)
    return ThreadMessage(
        message_id=str(latest.get("id") or ""),
        from_header=headers.get("from", ""),
        to_header=headers.get("to", ""),
        subject=headers.get("subject", ""),
        snippet=_decode_snippet(str(latest.get("snippet") or "")),
        date_header=headers.get("date", ""),
        body=_message_body(latest),
    )


def _message_headers(message: dict[str, Any]) -> dict[str, str]:
    raw = message.get("headers")
    if isinstance(raw, dict):
        return {str(k).lower(): str(v) for k, v in raw.items()}
    headers: dict[str, str] = {}
    for item in (message.get("payload") or {}).get("headers") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").lower()
        value = str(item.get("value") or "")
        if name:
            headers[name] = value
    return headers


def _message_body(message: dict[str, Any]) -> str:
    body = str(message.get("body") or "").strip()
    if body:
        return _decode_snippet(body)
    return _plain_text_from_payload(message.get("payload") or {})


def _plain_text_from_payload(payload: dict[str, Any]) -> str:
    mime = str(payload.get("mimeType") or "").lower()
    if mime == "text/plain":
        return _decode_body_data((payload.get("body") or {}).get("data") or "")
    for part in payload.get("parts") or []:
        if not isinstance(part, dict):
            continue
        text = _plain_text_from_payload(part)
        if text:
            return text
    return ""


def _decode_body_data(data: str) -> str:
    if not data:
        return ""
    try:
        raw = base64.urlsafe_b64decode(data + "==")
    except (ValueError, TypeError):
        return ""
    return raw.decode("utf-8", errors="replace").strip()


def _decode_snippet(text: str) -> str:
    return (
        text.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
    )


def parse_email_address(header: str) -> str:
    match = re.search(r"<([^>]+)>", header)
    if match:
        return match.group(1).strip().lower()
    value = header.strip().lower()
    if "@" in value:
        return value
    return value


class GogError(Exception):
    def __init__(self, mailbox: str, message: str) -> None:
        self.mailbox = mailbox
        super().__init__(message)
