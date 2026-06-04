# email-inbox

List unread Gmail inbox threads across multiple accounts using [gog](https://github.com/steipete/gog), draft replies in your Obsidian vault.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`brew install uv`)
- `gog` on `PATH` with Gmail OAuth per mailbox in `accounts.md`
- macOS + Obsidian (optional, for `--open` / default open after pick)

## Setup

Clone or open the repo, sync dependencies, then install the CLI globally (editable):

```bash
cd ~/Projects/email-inbox
uv sync
uv tool install -e .
```

`-e` installs in editable mode: Python changes in `src/` are picked up on the next run without reinstalling.

Ensure `~/.local/bin` is on your `PATH` (uv’s default tool directory). Then run from **any directory**:

```bash
email-inbox list
email-inbox pick 2
```

Reinstall only when packaging changes, for example new dependencies or `[project.scripts]`:

```bash
uv tool install --force -e ~/Projects/email-inbox
```

### Vault path

Resolution order: `--vault-root` → `EMAIL_INBOX_VAULT_ROOT` → `~/.config/email-inbox/config.toml` → `~/Documents/Obsidian Vault`

Vault paths are absolute; cwd does not matter.

```bash
mkdir -p ~/.config/email-inbox
cp config.toml.example ~/.config/email-inbox/config.toml
```

### Without a global install

```bash
uv run --directory ~/Projects/email-inbox email-inbox list
```

Or: `alias email-inbox='uv run --directory ~/Projects/email-inbox email-inbox'`

## Terminal workflow

```bash
email-inbox          # same as email-inbox list
email-inbox list
```

On a TTY, shows a **Rich grid**, then prompts for a **row number**. Writes `.inbox-session.json`.

```
Pick row [1-N] (q to quit):
```

**Experiment (branch `experiment/textual-picker`):** `email-inbox list --tui` keeps the table on screen. One hint bar under the table (no duplicate footer). **Browse:** ↑↓, **enter** open in Obsidian, **o** open thread in Gmail, **r** mark read, **f** refresh, **q** quit. **After open:** **d** draft, **s** send, **o** Gmail, **esc** back to browse.

After pick, typed prompts: `d` draft, `s` send, `b` browse again, `r` refresh (re-fetch and re-print table), `q` quit. You can also type another row number from the post-pick menu.

- **`--no-interactive`:** list only (prints table, no picker)
- **`--no-open`:** do not launch Obsidian after pick
- Cannot send twice from the same reply file (`status: sent` blocks it)

Picking the same thread again opens the existing `email-reply` note (matched by `mailbox` + `thread_id` in frontmatter) instead of creating `Reply to … (2).md`.

One-shot pick without re-listing:

```bash
email-inbox pick 2
```

Push a reply file without the interactive loop:

```bash
email-inbox send path/to/reply.md          # Gmail draft
email-inbox send path/to/reply.md --send   # send immediately
email-inbox send path/to/reply.md --send --force   # re-send if already sent
```

## Output formats

| Flag | Use |
|------|-----|
| default | Rich table in terminal |
| `--format markdown` | Pipe table (scripts) |
| `--json` | Session JSON only |

## Project routing

Automatic: `routing.yaml`, learned `email-reply` files, subject keywords, else `emails/`.

Copy vault `Projects/Cursor Gmail/routing.yaml.example` → `routing.yaml` for explicit sender maps.

## Development

Work in `~/Projects/email-inbox`. With editable install, test changes via `email-inbox` from any cwd.

```bash
uv run pytest
uv run pytest --cov=email_inbox --cov-report=term-missing
```

After changing `pyproject.toml` dependencies: `uv sync` then `uv tool install --force -e .`
