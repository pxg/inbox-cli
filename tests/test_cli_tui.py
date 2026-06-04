from pathlib import Path
from unittest.mock import patch

from email_inbox.cli import _use_tui


def test_use_tui_default_on_tty() -> None:
    args = type("Args", (), {"no_tui": False})()
    with (
        patch.object(__import__("sys").stdin, "isatty", return_value=True),
        patch.object(__import__("sys").stdout, "isatty", return_value=True),
    ):
        assert _use_tui(args) is True


def test_use_tui_off_with_no_tui_flag() -> None:
    args = type("Args", (), {"no_tui": True})()
    with (
        patch.object(__import__("sys").stdin, "isatty", return_value=True),
        patch.object(__import__("sys").stdout, "isatty", return_value=True),
    ):
        assert _use_tui(args) is False


def test_use_tui_off_when_not_tty() -> None:
    args = type("Args", (), {"no_tui": False})()
    with (
        patch.object(__import__("sys").stdin, "isatty", return_value=False),
        patch.object(__import__("sys").stdout, "isatty", return_value=True),
    ):
        assert _use_tui(args) is False
