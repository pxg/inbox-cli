"""Textual inbox session — table stays on screen; browse and action modes."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import DataTable as DataTableWidget
from textual.widgets import Label, ListItem, ListView, Static

from email_inbox.browser import open_url
from email_inbox.formatting import InboxRow
from email_inbox.mark_read import mark_read_inbox_row
from email_inbox.paths import session_path
from email_inbox.pick import AmbiguousProjectError
from email_inbox.obsidian import open_in_obsidian
from email_inbox.pick_flow import pick_inbox_row_flow
from email_inbox.session import build_session, load_session, write_session
from email_inbox.routing import list_project_options, project_from_input
from email_inbox.send import AlreadySentError, is_reply_sent, push_draft, push_send
from email_inbox.terminal import _subject_text


class InboxDataTable(DataTableWidget):
    """Row cursor; Enter selects row (RowSelected), not app-level binding."""

    BINDINGS = [
        *DataTableWidget.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("r", "mark_read_focused", "Mark read", priority=True),
        Binding("o", "open_gmail_focused", "Gmail", priority=True),
    ]

    def action_open_gmail_focused(self) -> None:
        app = self.app
        if isinstance(app, InboxTuiApp):
            app.action_open_gmail()

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", **kwargs)

    def action_mark_read_focused(self) -> None:
        app = self.app
        if isinstance(app, InboxTuiApp):
            app.action_mark_read_row()


class ProjectPickerScreen(ModalScreen[str | None]):
    """Choose project when routing is ambiguous."""

    CSS = """
    ProjectPickerScreen {
        align: center middle;
    }
    #picker_dialog {
        width: 64;
        height: auto;
        max-height: 22;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    #project_list {
        height: auto;
        max-height: 14;
    }
    """

    def __init__(self, vault_root: Path, candidates: list[str]) -> None:
        super().__init__()
        self.vault_root = vault_root
        self.candidates = candidates

    def compose(self) -> ComposeResult:
        with Container(id="picker_dialog"):
            yield Label("Ambiguous project — enter to select, esc cancel")
            yield ListView(id="project_list")

    def on_mount(self) -> None:
        list_view = self.query_one("#project_list", ListView)
        shown: set[str] = set()
        for oid, label in list_project_options(self.vault_root):
            if oid == "0" or oid in self.candidates:
                list_view.append(ListItem(Label(f"{oid}  {label}", id=f"opt_{oid}")))
                shown.add(oid)
        for name in self.candidates:
            if name not in shown:
                list_view.append(ListItem(Label(f"--project {name}", id=f"opt_{name}")))
        if list_view.children:
            list_view.index = 0

    def _selected_token(self) -> str:
        list_view = self.query_one("#project_list", ListView)
        item = list_view.highlighted_child
        if item is None:
            return ""
        label = item.query_one(Label)
        text = str(label.renderable) if hasattr(label, "renderable") else str(label)
        return text.strip().split()[0].removeprefix("--project")

    def key_enter(self) -> None:
        token = self._selected_token()
        resolved = project_from_input(self.vault_root, token, candidates=self.candidates)
        self.dismiss(None if resolved == "invalid" else resolved)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        label = event.item.query_one(Label)
        text = str(label.renderable)
        token = text.strip().split()[0].removeprefix("--project")
        resolved = project_from_input(self.vault_root, token, candidates=self.candidates)
        self.dismiss(None if resolved == "invalid" else resolved)

    def key_escape(self) -> None:
        self.dismiss(None)


class InboxTuiApp(App[int]):
    """
    Browse: enter open Obsidian, o Gmail in browser, r mark read, f refresh, q quit.
    Action (after open): d draft, s send, o Gmail, esc browse, q quit.
    """

    SHOW_FOOTER = False

    CSS = """
    Screen {
        background: #000000;
    }
    InboxDataTable {
        height: 1fr;
        background: #000000;
        color: #ffffff;
    }
    InboxDataTable > .datatable--cursor {
        background: #444444;
        color: #ffffff;
    }
    InboxDataTable > .datatable--header {
        background: #000000;
        color: #ffffff;
        text-style: bold;
    }
    #hint_bar {
        height: 1;
        padding: 0 1;
        color: #9eb3ff;
        background: #1a1a1a;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quit", priority=True),
        Binding("f", "refresh_inbox", "Refresh"),
        Binding("r", "mark_read_row", "Mark read", priority=True),
        Binding("o", "open_gmail", "Gmail", priority=True),
        Binding("enter", "open_row", "Open", show=False),
        Binding("d", "push_draft", "Draft"),
        Binding("s", "push_send", "Send"),
        Binding("escape", "back_to_browse", "Back"),
    ]

    def __init__(
        self,
        vault_root: Path,
        rows: list[InboxRow],
        *,
        open_obsidian: bool,
        refresh_rows: Callable[[], list[InboxRow]] | None = None,
    ) -> None:
        super().__init__()
        self.vault_root = vault_root
        self.rows = list(rows)
        self.open_obsidian = open_obsidian
        self.refresh_rows = refresh_rows
        self.reply_path: Path | None = None
        self.open_row_index: int | None = None
        self._busy_message: str | None = None
        self.mode = "browse"

    def compose(self) -> ComposeResult:
        yield InboxDataTable(id="inbox_table", show_cursor=True)
        yield Static("", id="hint_bar")

    def on_mount(self) -> None:
        self.title = f"Inbox ({len(self.rows)} unread)"
        self._fill_table()
        self._update_ui()
        self.query_one("#inbox_table", InboxDataTable).focus()

    def _fill_table(self) -> None:
        table = self.query_one("#inbox_table", InboxDataTable)
        table.clear(columns=True)
        table.add_columns("#", "From", "Subject", "Account", "Date")
        for index, row in enumerate(self.rows, start=1):
            table.add_row(
                str(index),
                row.from_display,
                _subject_text(row),
                row.label,
                row.date,
            )
        if self.rows:
            table.move_cursor(row=min(table.cursor_row or 0, len(self.rows) - 1))

    def _sync_session_from_rows(self) -> None:
        path = session_path(self.vault_root)
        try:
            session = load_session(path)
            query = str(session.get("query") or "in:inbox is:unread")
        except FileNotFoundError:
            query = "in:inbox is:unread"
        write_session(path, build_session(self.rows, query=query))

    def _apply_table_ui(self, *, focus_table: bool = True) -> None:
        """Redraw table from self.rows (fast; safe to call before gog finishes)."""
        self.title = f"Inbox ({len(self.rows)} unread)"
        self.mode = "browse"
        self.reply_path = None
        self.open_row_index = None
        self._fill_table()
        self._update_ui()
        self.refresh()
        if focus_table and self.rows:
            self.query_one("#inbox_table", InboxDataTable).focus()

    def _cursor_row_index(self) -> int | None:
        if not self.rows:
            return None
        table = self.query_one("#inbox_table", InboxDataTable)
        row_index: int | None = None
        coord = table.cursor_coordinate
        if coord is not None:
            row_index = coord.row
        elif table.cursor_row is not None:
            row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= len(self.rows):
            return None
        return row_index

    def _current_row(self) -> InboxRow | None:
        row_number = self._cursor_row_number()
        if row_number is None:
            return None
        return self.rows[row_number - 1]

    def _cursor_row_number(self) -> int | None:
        row_index = self._cursor_row_index()
        if row_index is None:
            return None
        return row_index + 1

    def _update_ui(self) -> None:
        self._update_hint_bar()

    def _hint_text(self) -> str:
        if self._busy_message:
            return f"⏳ {self._busy_message}"
        if not self.rows:
            refresh = " · f refresh" if self.refresh_rows else ""
            return f"Inbox empty{refresh} · q quit"
        if self.mode == "action" and self.reply_path is not None:
            label = self.reply_path.name
            if is_reply_sent(self.reply_path):
                actions = "o gmail · esc back · q quit"
            else:
                actions = "d draft · s send · o gmail · esc back · q quit"
            return f"↩ {label} · {actions}"
        refresh = " · f refresh" if self.refresh_rows else ""
        return f"enter open · o gmail · r read{refresh} · q quit"

    def _update_hint_bar(self) -> None:
        self.query_one("#hint_bar", Static).update(f"  {self._hint_text()}")

    def _set_busy(self, message: str) -> None:
        self._busy_message = message
        self._update_ui()

    def _clear_busy(self) -> None:
        self._busy_message = None
        self._update_ui()

    def _focused_inbox_row(self) -> InboxRow | None:
        if self.mode == "action" and self.open_row_index is not None:
            idx = self.open_row_index
            if 0 <= idx < len(self.rows):
                return self.rows[idx]
        return self._current_row()

    def action_open_gmail(self) -> None:
        if self._busy_message:
            return
        row = self._focused_inbox_row()
        if row is None:
            self.notify("No row selected")
            return
        open_url(row.gmail_url)

    def on_data_table_row_selected(self, event: DataTableWidget.RowSelected) -> None:
        if event.control.id != "inbox_table":
            return
        self.action_open_row()

    async def _pick_at_row(self, row: InboxRow, *, project: str | None = None) -> Path | None:
        while True:
            try:
                return await asyncio.to_thread(
                    pick_inbox_row_flow,
                    self.vault_root,
                    row,
                    open_obsidian=False,
                    project=project,
                )
            except AmbiguousProjectError as exc:
                project = await self.push_screen_wait(
                    ProjectPickerScreen(self.vault_root, exc.candidates)
                )
                if project is None:
                    self.notify("Open cancelled")
                    return None

    def action_open_row(self) -> None:
        self.run_worker(self._do_open_row(), exclusive=True)

    async def _do_open_row(self) -> None:
        row_index = self._cursor_row_index()
        row = self._current_row()
        if row is None or row_index is None:
            self.notify("No row selected")
            return
        self._set_busy("Opening reply…")
        try:
            path = await self._pick_at_row(row)
        finally:
            self._clear_busy()
        if path is None:
            return
        self.open_row_index = row_index
        self.reply_path = path
        self.mode = "action"
        self._update_ui()
        if self.open_obsidian:

            async def launch_obsidian() -> None:
                await asyncio.to_thread(open_in_obsidian, path)

            self.run_worker(launch_obsidian, exclusive=False, group="obsidian")

    def action_mark_read_row(self) -> None:
        if self.mode != "browse":
            self.notify("Mark read is for browse mode (esc to go back)")
            return
        row_index = self._cursor_row_index()
        if row_index is None:
            self.notify("No row selected")
            return
        row = self.rows[row_index]
        del self.rows[row_index]
        try:
            self._sync_session_from_rows()
        except OSError as exc:
            self.notify(f"Session save failed: {exc}", severity="warning")
        self._apply_table_ui()
        if not self.rows:
            self.notify("Inbox empty")
        async def finish() -> None:
            await self._complete_mark_read(row, row_index)

        self.run_worker(finish, exclusive=False, group="mark_read")

    async def _complete_mark_read(self, row: InboxRow, row_index: int) -> None:
        """Gmail mark-read in background; row already removed from the table."""
        try:
            await asyncio.to_thread(mark_read_inbox_row, row)
        except (RuntimeError, ValueError, KeyError, FileNotFoundError) as exc:
            self.rows.insert(min(row_index, len(self.rows)), row)
            try:
                self._sync_session_from_rows()
            except OSError:
                pass
            self._apply_table_ui()
            self.notify(str(exc), severity="error", timeout=6)

    def action_refresh_inbox(self) -> None:
        if self.refresh_rows is None:
            return
        self.rows = self.refresh_rows()
        self._apply_table_ui()
        if not self.rows:
            self.notify("No unread threads")

    def action_back_to_browse(self) -> None:
        self.mode = "browse"
        self._update_ui()

    def action_quit_app(self) -> None:
        self.exit(0)

    def action_push_draft(self) -> None:
        if self._busy_message:
            return
        if self.mode != "action":
            self.notify("Open a row first (enter)")
            return
        self.run_worker(self._do_push_draft(), exclusive=True)

    async def _do_push_draft(self) -> None:
        if self.reply_path is None:
            return
        if is_reply_sent(self.reply_path):
            self.notify("Already sent")
            return
        self._set_busy("Creating Gmail draft…")
        try:
            await asyncio.to_thread(push_draft, self.reply_path)
        except (AlreadySentError, ValueError, RuntimeError) as exc:
            self.notify(str(exc), severity="error", timeout=6)
            return
        finally:
            self._clear_busy()
        self._remove_open_row_after_send()

    def action_push_send(self) -> None:
        if self._busy_message:
            return
        if self.mode != "action":
            self.notify("Open a row first (enter)")
            return
        self.run_worker(self._do_push_send(), exclusive=True)

    async def _do_push_send(self) -> None:
        if self.reply_path is None:
            return
        if is_reply_sent(self.reply_path):
            self.notify("Already sent")
            return
        self._set_busy("Sending via Gmail…")
        try:
            await asyncio.to_thread(push_send, self.reply_path)
        except (AlreadySentError, ValueError, RuntimeError) as exc:
            self.notify(str(exc), severity="error", timeout=6)
            return
        finally:
            self._clear_busy()
        self._remove_open_row_after_send()

    def _remove_open_row_after_send(self) -> None:
        """Drop thread from inbox after send/draft (Gmail marked read in push_*)."""
        if self.open_row_index is None:
            self.mode = "browse"
            self.reply_path = None
            self._update_ui()
            return
        row_index = self.open_row_index
        if 0 <= row_index < len(self.rows):
            del self.rows[row_index]
            try:
                self._sync_session_from_rows()
            except OSError as exc:
                self.notify(f"Session save failed: {exc}", severity="warning")
        self._apply_table_ui()
        if not self.rows:
            self.notify("Inbox empty")


def run_textual_inbox_session(
    vault_root: Path,
    rows: list[InboxRow],
    *,
    open_obsidian: bool,
    refresh_rows: Callable[[], list[InboxRow]] | None = None,
) -> int:
    """Run full Textual inbox session until user quits."""
    if not sys.stdin.isatty():
        return 0
    app = InboxTuiApp(
        vault_root,
        rows,
        open_obsidian=open_obsidian,
        refresh_rows=refresh_rows,
    )
    return app.run() or 0


InboxPickerApp = InboxTuiApp
