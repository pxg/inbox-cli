"""Open URLs in the default browser (macOS)."""

from __future__ import annotations

import subprocess
import sys


def open_url(url: str) -> bool:
    if not url.strip():
        return False
    try:
        subprocess.Popen(
            ["open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        print(f"could not open browser for {url}", file=sys.stderr)
        return False
    return True
