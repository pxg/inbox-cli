"""Push vault reply files to Gmail via gog."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL | re.MULTILINE)
_ORIGINAL_SECTION_LEGACY = re.compile(r"\n## Original\b", re.IGNORECASE)
_ORIGINAL_SECTION_HR = re.compile(
    r"\n---\s*\n(?=From .+\([^)]+@[^)]+\),)",
    re.IGNORECASE,
)


class AlreadySentError(Exception):
    """Reply file frontmatter already has status: sent."""


@dataclass(frozen=True)
class ReplyMeta:
    mailbox: str
    send_from: str
    to: str
    subject: str
    reply_to_message_id: str
    status: str


def load_reply(path: Path) -> tuple[ReplyMeta, str]:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValueError(f"no YAML frontmatter in {path}")

    meta_raw = yaml.safe_load(match.group(1))
    if not isinstance(meta_raw, dict):
        raise ValueError("invalid frontmatter")

    mailbox = str(meta_raw.get("mailbox") or meta_raw.get("account") or "").strip()
    if not mailbox:
        raise ValueError("frontmatter missing mailbox")

    send_from = str(meta_raw.get("send_from") or mailbox).strip()
    to = str(meta_raw.get("to") or "").strip()
    subject = str(meta_raw.get("subject") or "").strip()
    reply_id = str(meta_raw.get("reply_to_message_id") or "").strip()

    if not to or not subject or not reply_id:
        raise ValueError("frontmatter missing to, subject, or reply_to_message_id")

    meta = ReplyMeta(
        mailbox=mailbox,
        send_from=send_from,
        to=to,
        subject=subject,
        reply_to_message_id=reply_id,
        status=str(meta_raw.get("status") or "editing"),
    )

    body = text[match.end() :].strip()
    body = _strip_quoted_original(body)
    if not body:
        raise ValueError("reply body is empty (write your message before sending)")

    return meta, body


def _strip_quoted_original(body: str) -> str:
    for pattern in (_ORIGINAL_SECTION_HR, _ORIGINAL_SECTION_LEGACY):
        parts = pattern.split(body, maxsplit=1)
        if len(parts) > 1:
            return parts[0].strip()
    return body.strip()


def reply_file_status(path: Path) -> str:
    """Read status from reply frontmatter without validating body."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        return ""
    meta_raw = yaml.safe_load(match.group(1))
    if not isinstance(meta_raw, dict):
        return ""
    return str(meta_raw.get("status") or "editing").strip().lower()


def is_reply_sent(path: Path) -> bool:
    return reply_file_status(path) == "sent"


def _ensure_not_sent(path: Path, meta: ReplyMeta, *, force: bool) -> None:
    if force:
        return
    if meta.status.strip().lower() != "sent":
        return
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    sent_at = ""
    if match:
        meta_raw = yaml.safe_load(match.group(1))
        if isinstance(meta_raw, dict) and meta_raw.get("sent_at"):
            sent_at = f" on {meta_raw.get('sent_at')}"
    raise AlreadySentError(
        f"Already sent{sent_at} — use inbox send --send --force to send again"
    )


def push_draft(path: Path) -> str:
    """Create Gmail draft; update vault file; mark read. Returns one-line success."""
    meta, body = load_reply(path)
    _ensure_not_sent(path, meta, force=False)
    draft_id = _gog_drafts_create(meta, body)
    _update_reply_file(path, status="gmail_draft", draft_id=draft_id)
    _mark_read(meta)
    return f"✓ Gmail draft · {meta.subject} → {meta.to} · from {meta.send_from}"


def push_send(path: Path, *, force: bool = False) -> str:
    """Send via Gmail; update vault file; mark read. Returns one-line success."""
    meta, body = load_reply(path)
    _ensure_not_sent(path, meta, force=force)
    _gog_send(meta, body)
    _update_reply_file(path, status="sent", draft_id=None)
    _mark_read(meta)
    return f"✓ Sent · {meta.subject} → {meta.to} · from {meta.send_from}"


def _gog_drafts_create(meta: ReplyMeta, body: str) -> str | None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(body)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "gog",
                "gmail",
                "drafts",
                "create",
                "-a",
                meta.mailbox,
                "--from",
                meta.send_from,
                "--to",
                meta.to,
                "--subject",
                meta.subject,
                "--reply-to-message-id",
                meta.reply_to_message_id,
                "--body-file",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"draft create failed: {err}")

    return _parse_draft_id(result.stdout)


def _gog_send(meta: ReplyMeta, body: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(body)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "gog",
                "gmail",
                "send",
                "-a",
                meta.mailbox,
                "--from",
                meta.send_from,
                "--to",
                meta.to,
                "--subject",
                meta.subject,
                "--reply-to-message-id",
                meta.reply_to_message_id,
                "--body-file",
                tmp_path,
                "-y",
                "--no-input",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"send failed: {err}")


def _mark_read(meta: ReplyMeta) -> None:
    from email_inbox.mark_read import gog_mark_read_message

    gog_mark_read_message(meta.mailbox, meta.reply_to_message_id)


def _update_reply_file(path: Path, *, status: str, draft_id: str | None) -> None:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        return
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        return
    meta["status"] = status
    if status == "sent":
        meta["sent_at"] = date.today().isoformat()
    if draft_id:
        meta["gmail_draft_id"] = draft_id
    elif status == "sent":
        meta["gmail_draft_id"] = meta.get("gmail_draft_id") or ""
    new_front = yaml.safe_dump(meta, sort_keys=False).strip()
    body = text[match.end() :]
    path.write_text(f"---\n{new_front}\n---{body}", encoding="utf-8")


def _parse_draft_id(stdout: str) -> str | None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    for key in ("draftId", "draft_id", "id"):
        if data.get(key):
            return str(data[key])
    draft = data.get("draft")
    if isinstance(draft, dict) and draft.get("id"):
        return str(draft["id"])
    return None
