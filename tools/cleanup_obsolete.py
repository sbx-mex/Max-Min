#!/usr/bin/env python3
"""Detecta o elimina únicamente artefactos conocidos de motores anteriores."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
patterns = ["js/data_part_*.js", "js/data_sem_*.js", "js/data_index.js", "icons/hero-maxmin.png", "icons/splash-1920x1080.png"]


def engine_orphans(manifest_path: Path, prefix: str, pattern: str) -> list[Path]:
    if not manifest_path.is_file():
        return []
    source = manifest_path.read_text(encoding="utf-8")
    if not source.startswith(prefix) or not source.rstrip().endswith(";"):
        return []
    manifest = json.loads(source[len(prefix):].strip()[:-1])
    referenced = {str(store["file"]) for store in manifest.get("stores", [])}
    return sorted(
        path for path in ROOT.glob(pattern)
        if path.relative_to(ROOT).as_posix() not in referenced
    )


legacy_targets = {path for pattern in patterns for path in ROOT.glob(pattern) if path.is_file()}
orphan_targets = set(engine_orphans(
    ROOT / "data" / "manifest.js", "window.MAXMIN_MANIFEST=", "data/stores_*/*.json",
)) | set(engine_orphans(
    ROOT / "data" / "normalized" / "manifest.js", "window.MAXMIN_NORMALIZED=",
    "data/normalized/stores_*/*.json",
))
targets = sorted(legacy_targets | orphan_targets)
parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
parser.add_argument("--report", type=Path)
args = parser.parse_args()

report = {
    "status": "clean" if not targets else ("cleaned" if args.apply else "blocked"),
    "apply": args.apply,
    "targets": [target.relative_to(ROOT).as_posix() for target in targets],
    "legacyTargets": [target.relative_to(ROOT).as_posix() for target in sorted(legacy_targets)],
    "orphanStoreFiles": [target.relative_to(ROOT).as_posix() for target in sorted(orphan_targets)],
}

if args.apply:
    for target in targets:
        target.unlink()
        print(f"eliminado: {target.relative_to(ROOT)}")
else:
    for target in targets:
        print(f"obsoleto: {target.relative_to(ROOT)}")
if args.report:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with Path(summary).open("a", encoding="utf-8") as stream:
        stream.write("## Limpieza de motores obsoletos\n\n")
        stream.write(
            f"Estado: **{report['status']}** · Obsoletos: **{len(legacy_targets)}** "
            f"· Tiendas huérfanas: **{len(orphan_targets)}**\n\n"
        )
        if targets:
            stream.write("Ejecuta el workflow **Limpiar motores obsoletos** antes de validar.\n")
if targets and not args.apply:
    raise SystemExit("ERROR: persisten archivos obsoletos; ejecuta el workflow Limpiar motores obsoletos")
print(f"status=ok targets={len(targets)}")
