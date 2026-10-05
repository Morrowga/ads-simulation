"""Versioned prompt templates: `.md` files with a `<!-- version: x.y -->` header and {{placeholders}}."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPT_DIR = Path(__file__).resolve().parent
_VERSION_RE = re.compile(r"<!--\s*version:\s*([\w.\-]+)\s*-->")


@lru_cache(maxsize=32)
def load(name: str) -> tuple[str, str]:
    """Return (template_text, version)."""
    path = PROMPT_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    m = _VERSION_RE.search(text)
    version = m.group(1) if m else "0"
    body = _VERSION_RE.sub("", text, count=1).lstrip("\n")
    return body, version


def render(template_name: str, /, **values: Any) -> tuple[str, str]:
    """Render {{key}} placeholders. Unknown placeholders are left empty. Returns (text, version)."""
    body, version = load(template_name)

    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        v = values.get(key, "")
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x) for x in v) if v else "none"
        if isinstance(v, dict):
            return ", ".join(f"{k} {vv}" for k, vv in v.items()) if v else "none"
        return str(v)

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", sub, body), version
