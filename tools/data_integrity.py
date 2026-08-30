#!/usr/bin/env python3
"""Funciones deterministas para sellar y reconciliar el motor de tiendas."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

MANIFEST_PREFIX = "window.MAXMIN_MANIFEST="
NORMALIZED_PREFIX = "window.MAXMIN_NORMALIZED="


def load_wrapped_manifest(path: Path, prefix: str) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    if not source.startswith(prefix) or not source.rstrip().endswith(";"):
        raise ValueError(f"{path} no tiene una envoltura válida")
    return json.loads(source[len(prefix):].strip()[:-1]), raw


def load_manifest(root: Path) -> tuple[dict[str, object], bytes]:
    return load_wrapped_manifest(root / "data" / "manifest.js", MANIFEST_PREFIX)


def load_normalized_manifest(root: Path) -> tuple[dict[str, object], bytes]:
    return load_wrapped_manifest(root / "data" / "normalized" / "manifest.js", NORMALIZED_PREFIX)


def inspect_store(path: Path, valid_weeks: set[int]) -> tuple[int, dict[str, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_week: Counter[str] = Counter()
    for week, flat in payload.items():
        parsed_week = int(week)
        if parsed_week not in valid_weeks:
            raise ValueError(f"semana {week} fuera del manifiesto en {path}")
        if not isinstance(flat, list) or len(flat) % 3:
            raise ValueError(f"registro compacto incompleto en {path}, semana {week}")
        by_week[str(parsed_week)] += len(flat) // 3
    ordered = {key: by_week[key] for key in sorted(by_week, key=int)}
    return sum(ordered.values()), ordered


def build_integrity(root: Path, manifest: dict[str, object], manifest_raw: bytes | None = None) -> dict[str, object]:
    if manifest_raw is None:
        manifest_raw = (root / "data" / "manifest.js").read_bytes()
    valid_weeks = {int(value) for value in manifest["weeks"]}
    files: dict[str, dict[str, object]] = {}
    totals: Counter[str] = Counter()
    for store in manifest["stores"]:
        relative = str(store["file"])
        path = root / relative
        records, by_week = inspect_store(path, valid_weeks)
        totals.update(by_week)
        files[relative] = {
            "ceco": str(store["code"]),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
            "records": records,
            "byWeek": by_week,
        }
    return {
        "schema": 1,
        "manifestSha256": hashlib.sha256(manifest_raw).hexdigest(),
        "positiveRows": sum(totals.values()),
        "positiveByWeek": {str(week): totals[str(week)] for week in sorted(valid_weeks)},
        "files": files,
    }


def write_integrity(root: Path, manifest: dict[str, object] | None = None) -> dict[str, object]:
    if manifest is None:
        manifest, manifest_raw = load_manifest(root)
    else:
        manifest_raw = (root / "data" / "manifest.js").read_bytes()
    report = build_integrity(root, manifest, manifest_raw)
    target = root / "data" / "integrity.json"
    target.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return report


def write_normalized_integrity(root: Path, manifest: dict[str, object] | None = None) -> dict[str, object]:
    if manifest is None:
        manifest, manifest_raw = load_normalized_manifest(root)
    else:
        manifest_raw = (root / "data" / "normalized" / "manifest.js").read_bytes()
    report = build_integrity(root, manifest, manifest_raw)
    target = root / "data" / "normalized" / "integrity.json"
    target.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    resolved_root = arguments.root.resolve()
    result = write_integrity(resolved_root)
    normalized_result = write_normalized_integrity(resolved_root)
    print(json.dumps({
        "status": "ok",
        "files": len(result["files"]),
        "positiveRows": result["positiveRows"],
        "normalizedFiles": len(normalized_result["files"]),
        "normalizedPositiveRows": normalized_result["positiveRows"],
    }, ensure_ascii=False))
