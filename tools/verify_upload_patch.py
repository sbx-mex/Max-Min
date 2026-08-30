#!/usr/bin/env python3
"""Verifica que cada archivo del parche conserve tamaño y huella SHA-256."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "UPLOAD_MANIFEST.json"


def main() -> None:
    if not MANIFEST.is_file():
        raise SystemExit("ERROR: falta UPLOAD_MANIFEST.json")
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    checked: list[dict[str, object]] = []
    for expected in payload.get("files", []):
        relative = str(expected["path"])
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"falta {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        size = path.stat().st_size
        if digest != expected["sha256"]:
            failures.append(f"huella distinta: {relative}")
        if size != int(expected["bytes"]):
            failures.append(f"tamaño distinto: {relative}")
        checked.append({"path": relative, "bytes": size, "sha256": digest})
    if failures:
        raise SystemExit("ERROR: " + "; ".join(failures))
    print(json.dumps({"status": "ok", "baseCommit": payload.get("baseCommit"), "files": len(checked)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
