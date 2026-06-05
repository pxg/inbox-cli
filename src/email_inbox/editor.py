"""Open reply files in the user's editor (default: Obsidian)."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from email_inbox.obsidian import open_in_obsidian

ENV_EDITOR = "INBOX_EDITOR"
PATH_PLACEHOLDER = "{path}"

_BUILTIN_SHORTCUTS: dict[str, list[str]] = {
    "cursor": ["cursor", PATH_PLACEHOLDER],
    "code": ["code", "-r", PATH_PLACEHOLDER],
    "vscode": ["code", "-r", PATH_PLACEHOLDER],
}


@dataclass(frozen=True)
class EditorConfig:
    """How to open a reply file after pick."""

    kind: str  # "none", "obsidian", "command"
    command: tuple[str, ...] = ()

    @property
    def opens(self) -> bool:
        return self.kind != "none"

    @classmethod
    def none(cls) -> EditorConfig:
        return cls("none")

    @classmethod
    def obsidian(cls) -> EditorConfig:
        return cls("obsidian")

    @classmethod
    def command(cls, parts: tuple[str, ...]) -> EditorConfig:
        if not parts:
            raise ValueError("editor command must not be empty")
        return cls("command", parts)

    def success_message(self) -> str:
        if self.kind == "obsidian":
            return "Opened in Obsidian"
        if self.kind == "command" and self.command:
            return f"Opened in {self.command[0]}"
        return "Opened"


def parse_editor_string(value: str) -> EditorConfig:
    """Parse editor name from config string or INBOX_EDITOR."""
    key = value.strip().lower()
    if key == "none":
        return EditorConfig.none()
    if key == "obsidian":
        return EditorConfig.obsidian()
    if key in _BUILTIN_SHORTCUTS:
        return EditorConfig.command(tuple(_BUILTIN_SHORTCUTS[key]))
    raise ValueError(
        f"unknown editor {value!r} (use none, obsidian, cursor, code, or a command list in config.toml)"
    )


def parse_editor_toml(value: object) -> EditorConfig:
    """Parse editor from config.toml (string or command array)."""
    if isinstance(value, str):
        return parse_editor_string(value)
    if isinstance(value, list):
        if not value or not all(isinstance(part, str) for part in value):
            raise ValueError("editor command list must be non-empty strings")
        return EditorConfig.command(tuple(value))
    raise ValueError("editor must be a string or array of strings")


def resolve_editor(
    *,
    cli_no_open: bool = False,
    cli_open: bool = False,
) -> EditorConfig:
    """CLI flags > INBOX_EDITOR > config.toml > default obsidian."""
    if cli_no_open:
        return EditorConfig.none()
    if cli_open:
        return EditorConfig.obsidian()
    env = os.environ.get(ENV_EDITOR, "").strip()
    if env:
        return parse_editor_string(env)
    from email_inbox.config import load_config

    return load_config().editor


def open_reply_file(path: Path, editor: EditorConfig) -> bool:
    """Launch editor for path. Returns True if a launcher started."""
    if not editor.opens:
        return False
    if editor.kind == "obsidian":
        return open_in_obsidian(path)
    if editor.kind == "command":
        return _launch_command(path, editor.command)
    return False


def _launch_command(path: Path, template: tuple[str, ...]) -> bool:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        print(f"file not found: {resolved}", file=sys.stderr)
        return False
    path_str = str(resolved)
    cmd = [part.replace(PATH_PLACEHOLDER, path_str) for part in template]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        print(f"could not open editor ({' '.join(cmd)}): {exc}", file=sys.stderr)
        return False
    return True
