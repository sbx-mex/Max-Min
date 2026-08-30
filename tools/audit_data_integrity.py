#!/usr/bin/env python3
"""Audita hashes, archivos huérfanos y reconciliación semanal de ambos motores."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from data_integrity import build_integrity, load_manifest, load_normalized_manifest

ROOT = Path(__file__).resolve().parents[1]


def audit_engine(
    root: Path,
    label: str,
    manifest: dict[str, object],
    manifest_raw: bytes,
    integrity_path: Path,
    store_pattern: str,
) -> dict[str, object]:
    issues: list[str] = []
    if not integrity_path.is_file():
        return {"status": "error", "files": 0, "positiveRows": 0, "weeks": 0, "issues": [f"{label}: falta {integrity_path.relative_to(root)}"]}
    expected = json.loads(integrity_path.read_text(encoding="utf-8"))
    if expected.get("manifestSha256") != hashlib.sha256(manifest_raw).hexdigest():
        issues.append(f"{label}: el sello no corresponde al manifiesto actual")

    referenced = {str(store["file"]) for store in manifest["stores"]}
    sealed = set(expected.get("files", {}))
    for relative in sorted(referenced - sealed):
        issues.append(f"{label}: archivo sin sello: {relative}")
    for relative in sorted(sealed - referenced):
        issues.append(f"{label}: sello obsoleto: {relative}")
    actual_files = {path.relative_to(root).as_posix() for path in root.glob(store_pattern)}
    for relative in sorted(actual_files - referenced):
        issues.append(f"{label}: archivo huérfano: {relative}")
    for relative in sorted(referenced - actual_files):
        issues.append(f"{label}: archivo faltante: {relative}")

    try:
        actual = build_integrity(root, manifest, manifest_raw)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues.append(f"{label}: {error}")
        actual = {"positiveRows": 0, "positiveByWeek": {}, "files": {}}

    for relative in sorted(referenced & sealed & set(actual.get("files", {}))):
        wanted = expected["files"][relative]
        found = actual["files"][relative]
        if wanted.get("sha256") != found.get("sha256"):
            issues.append(
                f"{label}: contenido alterado: {relative} "
                f"({found.get('records', 0)} vs {wanted.get('records', 0)} registros)"
            )

    counts = manifest["counts"]
    if actual.get("positiveRows") != counts.get("positiveRows"):
        issues.append(f"{label}: total distinto: {actual.get('positiveRows')} vs {counts.get('positiveRows')}")
    expected_by_week = {str(key): int(value) for key, value in counts["positiveByWeek"].items()}
    actual_by_week = {str(key): int(value) for key, value in actual.get("positiveByWeek", {}).items()}
    for week in sorted(set(expected_by_week) | set(actual_by_week), key=int):
        if actual_by_week.get(week, 0) != expected_by_week.get(week, 0):
            issues.append(f"{label}: semana {week}: {actual_by_week.get(week, 0)} vs {expected_by_week.get(week, 0)}")

    return {
        "status": "ok" if not issues else "error",
        "files": len(referenced),
        "positiveRows": actual.get("positiveRows", 0),
        "weeks": len(manifest["weeks"]),
        "issues": issues,
    }


def audit(root: Path) -> dict[str, object]:
    main_manifest, main_raw = load_manifest(root)
    normalized_manifest, normalized_raw = load_normalized_manifest(root)
    engines = {
        "maxMin": audit_engine(
            root, "Max Min", main_manifest, main_raw,
            root / "data" / "integrity.json", "data/stores_*/*.json",
        ),
        "normalizados": audit_engine(
            root, "Normalizados", normalized_manifest, normalized_raw,
            root / "data" / "normalized" / "integrity.json",
            "data/normalized/stores_*/*.json",
        ),
    }
    issues = [issue for engine in engines.values() for issue in engine["issues"]]
    return {
        "status": "ok" if not issues else "error",
        "files": sum(int(engine["files"]) for engine in engines.values()),
        "positiveRows": int(engines["maxMin"]["positiveRows"]),
        "weeks": int(engines["maxMin"]["weeks"]),
        "engines": engines,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.root.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] != "ok":
        preview = "; ".join(report["issues"][:12])
        remaining = len(report["issues"]) - 12
        suffix = f"; y {remaining} incidencia(s) más" if remaining > 0 else ""
        raise SystemExit(f"ERROR: integridad de datos: {preview}{suffix}")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
