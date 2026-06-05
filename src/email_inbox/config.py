"""Optional user config (~/.config/inbox-cli/config.toml)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from email_inbox.editor import EditorConfig, parse_editor_toml

_CONFIG_BASE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_CONFIG_NAMES = ("inbox-cli", "email-inbox")
ENV_AUTO_REFRESH = "INBOX_AUTO_REFRESH"
DEFAULT_AUTO_REFRESH_SECONDS = 60


def config_file() -> Path:
    """Prefer inbox-cli; fall back to legacy email-inbox path."""
    for name in _CONFIG_NAMES:
        path = _CONFIG_BASE / name / "config.toml"
        if path.is_file():
            return path
    return _CONFIG_BASE / _CONFIG_NAMES[0] / "config.toml"


CONFIG_DIR = config_file().parent
CONFIG_FILE = config_file()


@dataclass(frozen=True)
class AppConfig:
    vault_root: Path | None = None
    editor: EditorConfig = EditorConfig.obsidian()
    auto_refresh_seconds: int = DEFAULT_AUTO_REFRESH_SECONDS

    @property
    def open_obsidian(self) -> bool:
        """Legacy: true when editor is Obsidian (not none/custom)."""
        return self.editor.kind == "obsidian"


def _editor_from_config(data: dict) -> EditorConfig:
    if "editor" in data:
        return parse_editor_toml(data["editor"])
    if "open_obsidian" in data:
        return EditorConfig.obsidian() if bool(data["open_obsidian"]) else EditorConfig.none()
    return EditorConfig.obsidian()


def load_config() -> AppConfig:
    if not CONFIG_FILE.is_file():
        return AppConfig()
    data = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return AppConfig()
    vault = data.get("vault_root")
    auto_refresh = data.get("auto_refresh_seconds", DEFAULT_AUTO_REFRESH_SECONDS)
    return AppConfig(
        vault_root=Path(str(vault)).expanduser().resolve() if vault else None,
        editor=_editor_from_config(data),
        auto_refresh_seconds=max(0, int(auto_refresh)),
    )


def resolve_auto_refresh_seconds() -> int:
    """Env > config.toml > default (60). Zero disables auto-refresh."""
    env = os.environ.get(ENV_AUTO_REFRESH, "").strip()
    if env:
        return max(0, int(env))
    return load_config().auto_refresh_seconds


def load_config_vault_root() -> Path | None:
    return load_config().vault_root
