"""Shared terminal palette — minimal synthwave (purple / blue / magenta)."""

from __future__ import annotations

from rich.text import Text

# Deep violet base, cyan subjects, magenta focus, purple keys.
BG = "#0f0a1a"
TEXT = "#5c6b8a"
TEXT_BRIGHT = "#b8c5e8"
HEADER = "#e879f9"
CURSOR_BG = "#e879f9"
CURSOR_FG = "#0f0a1a"
SUBJECT = "#67e8f9"
SUBJECT_UNDERLINE = "#67e8f9"
HINT_KEY = "#c084fc"
HINT_LABEL = "#4c5d7a"
BORDER = "#2d1f4e"
MODAL_BORDER = "#e879f9"


def hint_commands_text(*pairs: tuple[str, str]) -> Text:
    """Purple [keys], dim blue labels, | between commands (safe for Textual)."""
    line = Text()
    for index, (key, label) in enumerate(pairs):
        if index:
            line.append(" | ", style=HINT_LABEL)
        line.append("[", style=HINT_KEY)
        line.append(key, style=HINT_KEY)
        line.append("] ", style=HINT_KEY)
        line.append(label, style=HINT_LABEL)
    return line


def title_bar(count: int) -> str:
    if count == 0:
        return "INBOX // ZERO"
    return f"INBOX // {count} UNREAD"
