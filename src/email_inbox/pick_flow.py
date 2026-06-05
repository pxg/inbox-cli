"""Shared pick-by-row flow for CLI prompts."""

from __future__ import annotations

import sys
from pathlib import Path

from email_inbox.editor import EditorConfig, open_reply_file
from email_inbox.formatting import InboxRow
from email_inbox.pick import AmbiguousProjectError, format_success, pick_and_write, pick_inbox_row
from email_inbox.routing import format_project_menu, project_from_input


def pick_inbox_row_flow(
    vault_root: Path,
    row: InboxRow,
    *,
    editor: EditorConfig,
    project: str | None = None,
) -> Path | None:
    """Pick by inbox row identity (for TUI after rows removed from table)."""
    try:
        path = pick_inbox_row(vault_root, row, project=project)
    except (FileNotFoundError, KeyError, RuntimeError) as exc:
        notify(str(exc))
        return None
    except AmbiguousProjectError:
        raise

    notify(format_success(vault_root, path))
    if open_reply_file(path, editor):
        notify(editor.success_message())
    return path


def pick_row(
    vault_root: Path,
    row_number: int,
    *,
    editor: EditorConfig,
    project: str | None = None,
) -> Path | None:
    """
    Create or reopen reply file for session row N (single attempt, fixed project).

    For ambiguous routing without a project, raises AmbiguousProjectError.
    """
    try:
        path = pick_and_write(vault_root, row_number, project=project)
    except (FileNotFoundError, KeyError, RuntimeError) as exc:
        notify(str(exc))
        return None
    except AmbiguousProjectError:
        raise

    notify(format_success(vault_root, path))
    if open_reply_file(path, editor):
        notify(editor.success_message())
    return path


def pick_row_prompt(
    vault_root: Path,
    row_number: int,
    *,
    editor: EditorConfig,
) -> Path | None:
    """Pick with stdin retry loop for ambiguous project."""
    project: str | None = None
    while True:
        try:
            path = pick_and_write(vault_root, row_number, project=project)
        except FileNotFoundError as exc:
            notify(str(exc))
            return None
        except KeyError as exc:
            notify(str(exc))
            return None
        except AmbiguousProjectError as exc:
            notify(format_project_menu(vault_root, exc.candidates))
            try:
                choice = input("Project (number or name): ").strip()
            except (EOFError, KeyboardInterrupt):
                raise SystemExit(0) from None
            resolved = project_from_input(vault_root, choice, candidates=exc.candidates)
            if resolved == "invalid":
                notify("Invalid project. Try again.")
                continue
            project = resolved
            continue
        except RuntimeError as exc:
            notify(str(exc))
            return None
        else:
            break

    notify(format_success(vault_root, path))
    if open_reply_file(path, editor):
        notify(editor.success_message())
    return path


def notify(message: str) -> None:
    print(message, file=sys.stderr)
