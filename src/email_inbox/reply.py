"""Create vault reply draft files."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import yaml
from zoneinfo import ZoneInfo

from email_inbox.formatting import display_name
from email_inbox.gog import ThreadMessage, parse_email_address
from email_inbox.session import SessionRow

_LOCAL_TZ = ZoneInfo("Europe/London")
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL | re.MULTILINE)
ORIGINAL_SECTION_MARKER = "---"
_QUOTED_REPLY_BOUNDARIES = (
    re.compile(r"\n_{5,}\s*\n\s*From: ", re.IGNORECASE),
    re.compile(r"\nFrom: .+\nSent: ", re.IGNORECASE),
    re.compile(r"\n-----Original Message-----\s*\n", re.IGNORECASE),
    re.compile(r"\nOn .+ wrote:\s*\n", re.IGNORECASE),
)
_MAILTO_SUFFIX = re.compile(r"<mailto:[^>]+>", re.IGNORECASE)
_OUTLOOK_IMAGE_PLACEHOLDER = re.compile(
    r"\[Text\s+Description automatically generated\]",
    re.IGNORECASE,
)


def reply_subject(original: str) -> str:
    if original.strip().lower().startswith("re:"):
        return original.strip()
    return f"Re: {original.strip()}"


_SUBJECT_PREFIX = re.compile(r"^(re|fwd|fw)\s*:\s*", re.IGNORECASE)
_FILENAME_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify_subject(subject: str, *, max_len: int = 48) -> str:
    text = _SUBJECT_PREFIX.sub("", subject.strip()).strip()
    text = _FILENAME_BAD.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "No subject"
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def reply_note_basename(*, from_header: str, subject: str, thread_id: str) -> str:
    """Human-readable, unique filename for a thread reply note."""
    name = display_name(from_header) or "Unknown"
    slug = slugify_subject(subject)
    tid = thread_id.strip()
    suffix = tid[-8:] if len(tid) >= 8 else (tid or "thread")
    return _sanitize_filename(f"{name} — {slug} ({suffix}).md")


def _sanitize_filename(name: str) -> str:
    cleaned = _FILENAME_BAD.sub("", name).strip().strip(".")
    return cleaned or "email-reply.md"


def _reply_emails_directory(vault_root: Path, project: str | None) -> Path:
    if project:
        return vault_root / "Projects" / project / "emails"
    return vault_root / "emails"


def choose_reply_path(
    vault_root: Path,
    *,
    project: str | None,
    from_header: str,
    subject: str,
    thread_id: str,
) -> Path:
    directory = _reply_emails_directory(vault_root, project)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / reply_note_basename(
        from_header=from_header,
        subject=subject,
        thread_id=thread_id,
    )
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    n = 2
    while True:
        path = directory / f"{stem} ({n}).md"
        if not path.exists():
            return path
        n += 1


def find_existing_reply(
    vault_root: Path,
    *,
    mailbox: str,
    thread_id: str,
    project: str | None = None,
) -> Path | None:
    """Return an existing email-reply note for this mailbox + thread, if any."""
    del project  # always search whole vault (project-scoped search missed notes)
    note_paths: list[Path] = []
    emails_root = vault_root / "emails"
    if emails_root.is_dir():
        note_paths.extend(emails_root.glob("*.md"))

    projects_dir = vault_root / "Projects"
    if projects_dir.is_dir():
        for project_dir in projects_dir.iterdir():
            emails_dir = project_dir / "emails"
            if emails_dir.is_dir():
                note_paths.extend(emails_dir.glob("*.md"))

    matches: list[Path] = []
    for path in note_paths:
        meta = _read_reply_meta(path)
        if not meta:
            continue
        if str(meta.get("thread_id") or "").strip() != thread_id:
            continue
        mb = str(meta.get("mailbox") or meta.get("send_from") or "").strip()
        if mb != mailbox:
            continue
        matches.append(path)

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return max(matches, key=lambda p: p.stat().st_mtime)


def build_reply_document(
    *,
    mailbox: str,
    project: str | None,
    thread_id: str,
    message: ThreadMessage,
    session_row: SessionRow | None = None,
) -> str:
    reply_to = parse_email_address(message.from_header)
    created = datetime.now(_LOCAL_TZ).date().isoformat()
    subject = reply_subject(message.subject)
    short = display_name(message.from_header)

    project_line = f"project: {project}\n" if project else ""

    original = _format_original(short, message, session_row)

    return (
        "---\n"
        "type: email-reply\n"
        "status: editing\n"
        f"mailbox: {mailbox}\n"
        f"send_from: {mailbox}\n"
        f"{project_line}"
        f'thread_id: "{thread_id}"\n'
        f'reply_to_message_id: "{message.message_id}"\n'
        f'from: "{_yaml_escape(message.from_header)}"\n'
        f"to: \"{reply_to}\"\n"
        f'subject: "{_yaml_escape(subject)}"\n'
        f"created: {created}\n"
        "sent_at:\n"
        "gmail_draft_id:\n"
        "---\n"
        "\n"
        f"{original}"
    )


def _read_reply_meta(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = _FRONTMATTER.match(text)
    if not match:
        return None
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        return None
    if meta.get("type") != "email-reply":
        return None
    return meta


def _yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _prepare_quoted_body(text: str) -> str:
    """Keep the latest reply text: preserve line breaks and drop embedded thread quotes."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    cut_at = len(normalized)
    for pattern in _QUOTED_REPLY_BOUNDARIES:
        match = pattern.search(normalized)
        if match and match.start() < cut_at:
            cut_at = match.start()
    normalized = normalized[:cut_at].strip()
    normalized = _MAILTO_SUFFIX.sub("", normalized)
    normalized = _OUTLOOK_IMAGE_PLACEHOLDER.sub("", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def _format_original(
    short_name: str,
    message: ThreadMessage,
    session_row: SessionRow | None,
) -> str:
    addr = parse_email_address(message.from_header)
    date_line = _original_date_line(message, session_row)
    text = _prepare_quoted_body(message.body or message.snippet)
    if text:
        quote = f"> {text.replace(chr(10), chr(10) + '> ')}"
    else:
        quote = "> …"

    return (
        f"\n{ORIGINAL_SECTION_MARKER}\n\n"
        f"From {short_name} ({addr}), {date_line}:\n\n"
        f"{quote}\n"
    )


def _original_date_line(message: ThreadMessage, session_row: SessionRow | None) -> str:
    if session_row and session_row.date:
        try:
            dt = datetime.strptime(session_row.date, "%Y-%m-%d %H:%M")
            return dt.strftime("%-d %b %Y") if _has_strftime_d() else dt.strftime("%d %b %Y").lstrip("0")
        except ValueError:
            pass
    if message.date_header:
        return message.date_header.split(",")[-1].strip()[:20] or "recent"
    return datetime.now(_LOCAL_TZ).strftime("%d %b %Y").lstrip("0")


def _has_strftime_d() -> bool:
    try:
        datetime.now().strftime("%-d")
        return True
    except ValueError:
        return False


def write_reply_file(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path.resolve()
