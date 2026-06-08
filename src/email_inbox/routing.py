"""Resolve vault project folder for a reply."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from email_inbox.gog import parse_email_address

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL | re.MULTILINE)
_EMAIL_IN_FROM = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def resolve_project(
    vault_root: Path,
    *,
    from_header: str,
    subject: str,
    explicit: str | None = None,
) -> tuple[str | None, list[str]]:
    """
    Return (project_name or None for vault emails/, candidates if ambiguous).
    """
    if explicit is not None:
        return _normalize_explicit(explicit), []

    candidates: set[str] = set()

    candidates |= _routing_yaml_matches(vault_root, from_header)
    candidates |= _learned_matches(vault_root, from_header)
    candidates |= _subject_keyword_matches(vault_root, subject)

    ordered = sorted(candidates)
    if len(ordered) == 1:
        return ordered[0], []
    if len(ordered) > 1:
        return None, ordered
    return None, []


def _normalize_explicit(value: str) -> str | None:
    name = value.strip()
    if name == "0" or name.lower() in ("emails", "default", ""):
        return None
    return name


def project_from_input(
    vault_root: Path,
    raw: str,
    *,
    candidates: list[str] | None = None,
) -> str | None | str:
    """Return project name, None for emails/, or 'invalid'."""
    text = raw.strip()
    if not text:
        return "invalid"
    if text == "0" or text.lower() in ("emails", "default"):
        return None

    if candidates and text in candidates:
        return text

    for oid, _label in list_project_options(vault_root):
        if text == oid:
            return None if oid == "0" else oid
        if text.lower() == oid.lower():
            return None if oid == "0" else oid

    projects_dir = vault_root / "Projects"
    if projects_dir.is_dir():
        for path in projects_dir.iterdir():
            if path.is_dir() and path.name.lower() == text.lower():
                return path.name

    return "invalid"


def format_project_menu(vault_root: Path, candidates: list[str]) -> str:
    lines = ["Project:"]
    for oid, label in list_project_options(vault_root):
        if oid == "0":
            lines.append(f"  {oid}  {label}")
        elif oid in candidates:
            lines.append(f"  {oid}  {label}")
    known = {o[0] for o in list_project_options(vault_root)}
    for name in candidates:
        if name not in known:
            lines.append(f"      {name}")
    return "\n".join(lines)


def list_project_options(vault_root: Path) -> list[tuple[str, str]]:
    """Numbered options: (id, display) with 0 = default emails/."""
    options: list[tuple[str, str]] = [("0", "emails/")]
    projects_dir = vault_root / "Projects"
    if projects_dir.is_dir():
        for path in sorted(projects_dir.iterdir()):
            if path.is_dir() and (path / "emails").is_dir():
                options.append((path.name, f"Projects/{path.name}/emails/"))
    return options


def _routing_yaml_matches(vault_root: Path, from_header: str) -> set[str]:
    path = vault_root / "Projects" / "Inbox-CLI" / "routing.yaml"
    if not path.is_file():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set()

    sender = parse_email_address(from_header)
    domain = sender.split("@")[-1] if "@" in sender else ""

    matches: set[str] = set()
    for email, project in (data.get("senders") or {}).items():
        if str(email).lower() == sender:
            matches.add(str(project))
    for dom, project in (data.get("domains") or {}).items():
        if str(dom).lower() == domain:
            matches.add(str(project))
    return matches


def _learned_matches(vault_root: Path, from_header: str) -> set[str]:
    sender = parse_email_address(from_header)
    domain = sender.split("@")[-1] if "@" in sender else ""
    email_to_projects: dict[str, set[str]] = {}

    projects_dir = vault_root / "Projects"
    if not projects_dir.is_dir():
        return set()

    for email_file in projects_dir.glob("*/emails/*.md"):
        meta = _read_reply_frontmatter(email_file)
        if not meta:
            continue
        project = meta.get("project") or email_file.parent.parent.name
        for key in ("from", "to"):
            raw = meta.get(key) or ""
            for addr in _emails_in_text(raw):
                email_to_projects.setdefault(addr, set()).add(str(project))

    return email_to_projects.get(sender, set())


def _subject_keyword_matches(vault_root: Path, subject: str) -> set[str]:
    subject_l = subject.lower()
    matches: set[str] = set()
    projects_dir = vault_root / "Projects"
    if not projects_dir.is_dir():
        return matches
    for path in projects_dir.iterdir():
        if path.is_dir() and (path / "emails").is_dir():
            name = path.name
            if name.lower() in subject_l:
                matches.add(name)
    return matches


def _read_reply_frontmatter(path: Path) -> dict | None:
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


def _emails_in_text(text: str) -> set[str]:
    found: set[str] = set()
    for match in _EMAIL_IN_FROM.finditer(text):
        found.add(match.group(0).lower())
    if "@" in text and "<" not in text:
        found.add(text.strip().lower())
    return found
