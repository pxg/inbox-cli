"""Rich terminal table (TTY)."""

from __future__ import annotations

import sys
from io import StringIO

from rich.box import SQUARE
from rich.console import Console
from rich.table import Table
from rich.text import Text

from email_inbox.formatting import InboxRow

from email_inbox.theme import HEADER, SUBJECT, SUBJECT_UNDERLINE, TEXT_BRIGHT

_SUBJECT_COLOR = SUBJECT_UNDERLINE
_CELL_STYLE = TEXT_BRIGHT
_HEADER_STYLE = f"bold {HEADER}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _dashed_underline_ansi(color: str) -> tuple[str, str]:
    """Kitty-style dashed underline + matching underline colour (SGR 4:5, 58)."""
    r, g, b = _hex_to_rgb(color)
    start = f"\x1b[38;2;{r};{g};{b}m\x1b[4:5m\x1b[58;2::{r}:{g}:{b}m"
    end = "\x1b[24m\x1b[59m\x1b[39m"
    return start, end


def _subject_text(row: InboxRow) -> Text:
    """Clickable subject with dashed lavender underline; preserves emoji."""
    title = row.subject_for_table
    start, end = _dashed_underline_ansi(_SUBJECT_COLOR)
    text = Text.from_ansi(f"{start}{title}{end}")
    text.stylize(f"link {row.gmail_url}", 0, len(text.plain))
    return text


def build_inbox_table(rows: list[InboxRow]) -> Table:
    """Inbox grid table."""
    table = Table(
        show_header=True,
        header_style=_HEADER_STYLE,
        box=SQUARE,
        show_lines=True,
        expand=True,
        pad_edge=True,
    )
    table.add_column("#", style=_CELL_STYLE, width=4, justify="center")
    table.add_column("From", style=_CELL_STYLE, min_width=14, overflow="fold", no_wrap=False)
    table.add_column(
        "Subject",
        style=_CELL_STYLE,
        min_width=28,
        ratio=1,
        overflow="fold",
    )
    table.add_column("Account", style=_CELL_STYLE, min_width=18, no_wrap=True)
    table.add_column("Date", style=_CELL_STYLE, width=17, no_wrap=True)

    for index, row in enumerate(rows):
        table.add_row(
            str(index + 1),
            row.from_for_table,
            _subject_text(row),
            row.label,
            row.date,
            style=_CELL_STYLE,
        )
    return table


def render_rich_inbox(rows: list[InboxRow], *, file=None, width: int | None = None) -> None:
    """Print bordered table with clickable subject links."""
    console = Console(file=file or sys.stdout, force_terminal=True, width=width)

    if not rows:
        console.print("Inbox clear.")
        return

    console.print(f"Inbox ({len(rows)} unread)")
    console.print()
    console.print(build_inbox_table(rows))


def render_rich_inbox_as_text(rows: list[InboxRow], *, width: int = 120) -> str:
    """Capture Rich output as plain text (for tests)."""
    buffer = StringIO()
    render_rich_inbox(rows, file=buffer, width=width)
    return buffer.getvalue()
