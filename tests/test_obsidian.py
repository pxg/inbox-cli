from pathlib import Path
from unittest.mock import patch

from email_inbox.obsidian import open_in_obsidian


def test_open_uri_success(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("hi")
    with patch("email_inbox.obsidian._launch", side_effect=[True, False]) as launch:
        assert open_in_obsidian(note) is True
    assert launch.call_args_list[0][0][0][1].startswith("obsidian://open?path=")
