"""Open vault files in Obsidian (macOS)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


def open_in_obsidian(path: Path) -> bool:
    """Open a note in Obsidian. Returns True if a launcher command succeeded."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        print(f"file not found: {resolved}", file=sys.stderr)
        return False

    uri = f"obsidian://open?path={quote(str(resolved), safe='')}"
    if _launch(["open", uri]):
        return True
    if _launch(["open", "-a", "Obsidian", str(resolved)]):
        return True
    print("could not open Obsidian (tried URI and open -a)", file=sys.stderr)
    return False


def _launch(cmd: list[str]) -> bool:
    """Start macOS open without waiting for Obsidian to finish loading."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
