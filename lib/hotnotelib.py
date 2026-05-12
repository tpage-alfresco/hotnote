"""HotNote shared library — data, config, recurrence, and URL title helpers."""

import json
import os
import random
import re
from datetime import datetime, timedelta, timezone

# ── Paths ─────────────────────────────────────────────────────────────────────

HOTNOTES_PATH = os.path.expanduser("~/.local/share/hotnote/hotnotes.json")
CONFIG_PATH = os.path.expanduser("~/.config/hotnote/config.json")

# ── Constants ─────────────────────────────────────────────────────────────────

IMPORTANCE_VALUES = ["critical", "high", "medium", "low"]
URGENCY_VALUES = ["immediate", "soon", "whenever"]

IMPORTANCE_WEIGHT = {"critical": 0, "high": 1, "medium": 2, "low": 3}
URGENCY_WEIGHT = {"immediate": 0, "soon": 1, "whenever": 2}

DEFAULT_USELESS_PATTERNS = [r".*log in.*", r".*sign in.*"]

# ── Config ────────────────────────────────────────────────────────────────────


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {"useless_title_patterns": list(DEFAULT_USELESS_PATTERNS)}
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        cfg.setdefault("useless_title_patterns", list(DEFAULT_USELESS_PATTERNS))
        return cfg
    except (json.JSONDecodeError, OSError):
        return {"useless_title_patterns": list(DEFAULT_USELESS_PATTERNS)}


def save_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


# ── Data I/O ──────────────────────────────────────────────────────────────────


def load_data() -> dict:
    """Load the full hotnotes data dict ({"hotnotes": [...]})."""
    if not os.path.exists(HOTNOTES_PATH):
        return {"hotnotes": []}
    with open(HOTNOTES_PATH) as f:
        return json.load(f)


def save_data(data: dict) -> None:
    os.makedirs(os.path.dirname(HOTNOTES_PATH), exist_ok=True)
    with open(HOTNOTES_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_notes() -> list:
    """Load just the notes list."""
    return load_data().get("hotnotes", [])


def save_notes(notes: list) -> None:
    save_data({"hotnotes": notes})


# ── Note helpers ──────────────────────────────────────────────────────────────


def new_id(notes: list) -> str:
    existing = {t["id"] for t in notes}
    while True:
        uid = f"{random.randint(0, 0xFFFFFF):06x}"
        if uid not in existing:
            return uid


def find_note(notes: list, note_id: str) -> dict | None:
    for t in notes:
        if t["id"] == note_id:
            return t
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sort_key(note: dict) -> tuple:
    imp = IMPORTANCE_WEIGHT.get(note.get("importance", "medium"), 99)
    urg = URGENCY_WEIGHT.get(note.get("urgency", "soon"), 99)
    return (imp + urg, urg)


def pending(notes: list) -> list:
    return sorted([t for t in notes if t.get("status") != "done"], key=sort_key)


def completed(notes: list) -> list:
    done = [t for t in notes if t.get("status") == "done"]
    return sorted(done, key=lambda t: t.get("completed", ""), reverse=True)


# ── URL title fetching ────────────────────────────────────────────────────────


def is_useless_title(title: str) -> bool:
    cfg = load_config()
    lower = title.lower()
    for pattern in cfg.get("useless_title_patterns", []):
        try:
            if re.fullmatch(pattern.lower(), lower):
                return True
        except re.error:
            continue
    return False


def domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or url
    return host.removeprefix("www.")


def fetch_page_title(url: str) -> str:
    """Fetch the <title> of a URL. Falls back to the domain name."""
    from urllib.request import Request, urlopen
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (HotNote)"})
        with urlopen(req, timeout=5) as resp:
            chunk = resp.read(65536).decode("utf-8", errors="ignore")
        match = re.search(r"<title[^>]*>(.*?)</title>", chunk, re.IGNORECASE | re.DOTALL)
        if match:
            import html
            title = html.unescape(match.group(1)).strip()
            if not is_useless_title(title):
                return title
    except Exception:
        pass
    return domain_from_url(url)


# ── Recurrence ────────────────────────────────────────────────────────────────

_RECUR_RE = re.compile(r"^(\d+)\s*([dwm])$", re.IGNORECASE)
_UNIT_MAP = {"d": "days", "w": "weeks", "m": "months"}


def parse_recur(spec: str) -> dict | None:
    """Parse '18d', '2w', '1m' into {"every": 18, "unit": "days"}.

    Returns None on 'none' or invalid input.
    """
    if spec.lower() == "none":
        return None
    m = _RECUR_RE.match(spec.strip())
    if not m:
        return None
    return {"every": int(m.group(1)), "unit": _UNIT_MAP[m.group(2).lower()]}


def advance_next_due(prev_due: str, recur: dict) -> str:
    """Advance a next_due ISO string by one recurrence interval."""
    from dateutil.relativedelta import relativedelta
    dt = datetime.fromisoformat(prev_due.replace("Z", "+00:00"))
    unit = recur["unit"]
    every = recur["every"]
    if unit == "days":
        dt += timedelta(days=every)
    elif unit == "weeks":
        dt += timedelta(weeks=every)
    elif unit == "months":
        dt += relativedelta(months=every)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def recur_resurrect(notes: list) -> bool:
    """Flip done recurring notes back to pending if next_due has passed."""
    now = datetime.now(timezone.utc)
    changed = False
    for note in notes:
        if note.get("status") != "done":
            continue
        if not note.get("recur") or not note.get("next_due"):
            continue
        due = datetime.fromisoformat(note["next_due"].replace("Z", "+00:00"))
        if due <= now:
            note["status"] = "pending"
            note["completed"] = None
            changed = True
    return changed


def fmt_recur_short(note: dict) -> str:
    """Short recurrence label, e.g. '↻18d'."""
    recur = note.get("recur")
    if not recur:
        return ""
    every = recur["every"]
    unit = recur["unit"]
    short = {"days": "d", "weeks": "w", "months": "mo"}[unit]
    return f"↻{every}{short}"
