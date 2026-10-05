"""Write backend/openapi.json for the frontend type generator.

python -m scripts.export_openapi [output_path]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "openapi.json"
    spec = app.openapi()
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    paths = len(spec.get("paths", {}))
    schemas = len(spec.get("components", {}).get("schemas", {}))
    print(f"wrote {out} ({paths} paths, {schemas} schemas)")


if __name__ == "__main__":
    main()
