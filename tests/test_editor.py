from pathlib import Path
from unittest.mock import patch

import pytest

from email_inbox.editor import (
    ENV_EDITOR,
    EditorConfig,
    open_reply_file,
    parse_editor_string,
    parse_editor_toml,
    resolve_editor,
)


def test_parse_editor_string_shortcuts() -> None:
    assert parse_editor_string("obsidian").kind == "obsidian"
    assert parse_editor_string("none").kind == "none"
    assert parse_editor_string("cursor").command == ("cursor", "{path}")


def test_parse_editor_toml_command_list() -> None:
    editor = parse_editor_toml(["cursor", "{path}"])
    assert editor.kind == "command"
    assert editor.command == ("cursor", "{path}")


def test_resolve_editor_cli_no_open() -> None:
    assert resolve_editor(cli_no_open=True).kind == "none"


def test_resolve_editor_env_over_config(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "inbox-cli"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text('editor = "obsidian"\n')
    monkeypatch.setattr("email_inbox.config.CONFIG_FILE", config_file)
    monkeypatch.setenv(ENV_EDITOR, "none")
    assert resolve_editor().kind == "none"


def test_open_reply_file_command(tmp_path: Path) -> None:
    note = tmp_path / "reply.md"
    note.write_text("hi")
    editor = EditorConfig.command(("touch", "{path}.opened"))
    with patch("email_inbox.editor.subprocess.Popen") as popen:
        assert open_reply_file(note, editor) is True
    cmd = popen.call_args[0][0]
    assert str(note.resolve()) in cmd[1]


def test_open_reply_file_none() -> None:
    assert open_reply_file(Path("/tmp/x.md"), EditorConfig.none()) is False


def test_parse_editor_string_unknown() -> None:
    with pytest.raises(ValueError, match="unknown editor"):
        parse_editor_string("vim")
