"""Optional user config (~/.config/email-inbox/config.toml)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "email-inbox"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass(frozen=True)
class AppConfig:
    vault_root: Path | None = None
    open_obsidian: bool = True


def load_config() -> AppConfig:
    if not CONFIG_FILE.is_file():
        return AppConfig()
    data = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return AppConfig()
    vault = data.get("vault_root")
    open_obs = data.get("open_obsidian", True)
    return AppConfig(
        vault_root=Path(str(vault)).expanduser().resolve() if vault else None,
        open_obsidian=bool(open_obs),
    )


def load_config_vault_root() -> Path | None:
    return load_config().vault_root
