# HotNote

A lightweight personal task tracker for Ubuntu with a system tray indicator and a GTK window — all driven by a single JSON file and a CLI.

## Features

- **System tray indicator** — see pending hotnotes at a glance from the top bar
- **GTK window** — full view with add/done/reopen/delete, importance & urgency badges
- **CLI** — scriptable `hotnote` command for adding, listing, and managing notes
- **Recurring notes** — set a repeat interval (days/weeks/months); completed notes resurrect automatically when due
- **Links & references** — attach URLs (opened in browser) or text references (copied to clipboard) to any hotnote
- **Hot theming** — warm fire-inspired colour scheme throughout

## Dependencies

HotNote needs Python 3.10+ and GTK 3 with AppIndicator support.

```bash
sudo apt install python3 python3-dateutil gir1.2-appindicator3-0.1 gir1.2-gtk-3.0 libnotify-bin
```

## Install

```bash
make install
```

This installs to `~/.local` by default. Override with `make install PREFIX=/usr/local` if you prefer a system-wide install (you'll need `sudo`).

After installing, either log out/in for the autostart entry to take effect, or start the indicator manually:

```bash
hotnote-indicator &
```

## Uninstall

```bash
make uninstall
```

## CLI Usage

```
hotnote add "Buy milk" --importance low --urgency whenever
hotnote add "Fix auth bug" --importance critical --urgency immediate
hotnote add "Monthly report" --recur 1m --importance high
hotnote list
hotnote list --all --links
hotnote done <id>
hotnote reopen <id>
hotnote set <id> --importance high --urgency soon
hotnote set <id> --recur none
hotnote link <id> https://github.com/issue/123 "Auth issue"
hotnote link <id> "check the deploy logs on staging"
hotnote show <id>
hotnote delete <id>
hotnote open
```

### Link types

- **URL** — any value starting with `http://` or `https://` becomes a clickable web link (opened with `xdg-open`)
- **Text reference** — anything else becomes a reference that copies to clipboard when clicked

### Recurrence

Add `--recur` to make a hotnote repeat. When completed, it stays done until the next due date, then automatically reappears as pending.

| Spec | Meaning |
|---|---|
| `18d` | every 18 days |
| `2w` | every 2 weeks |
| `1m` | every 1 month |
| `none` | remove recurrence |

### Field values

| Field | Values (highest to lowest) |
|---|---|
| importance | `critical`, `high`, `medium`, `low` |
| urgency | `immediate`, `soon`, `whenever` |

Defaults: `--importance medium --urgency soon`

## Data

- Notes are stored in `~/.local/share/hotnote/hotnotes.json`
- Settings are stored in `~/.config/hotnote/config.json`

Back up these files to preserve your hotnotes and preferences.

