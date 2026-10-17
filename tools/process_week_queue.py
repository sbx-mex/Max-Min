#!/usr/bin/env python3
"""Procesa todas las cargas semanales en una copia; publica sólo un lote verificado."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from audit_week_source import audit
from build_data import normalized_csv_lines
from update_week import read_manifest, update
from verify_week_publish import verify
from weekly_source import REQUIRED_HEADERS, incoming_files, parse_week, read_source

ROOT = Path(__file__).resolve().parents[1]


def source_info(root: Path, path: Path) -> dict:
    folder = root / "updates" / "incoming"
    if path.is_symlink() or path.resolve().parent != folder.resolve():
        raise ValueError("la fuente debe ser un archivo directo de updates/incoming")
    raw, member = read_source(path)
    reader = csv.DictReader(normalized_csv_lines(io.BytesIO(raw)))
    headers = reader.fieldnames or []
    if not REQUIRED_HEADERS.issubset(headers) or len(headers) != len(set(headers)):
        raise ValueError(f"{path.name}: encabezados inválidos o repetidos")
    week = None
    count = 0
    for number, row in enumerate(reader, 2):
        if None in row or any(row.get(key) is None for key in REQUIRED_HEADERS):
            raise ValueError(f"{path.name}, fila {number}: columnas incompletas o sobrantes")
        found = parse_week(row["Semana"])
        if found < 35:
            raise ValueError(f"{path.name}: la entrada semanal comienza en 35")
        if week is not None and week != found:
            raise ValueError(f"{path.name}: mezcla semanas {week} y {found}")
        week = found
        count += 1
    if week is None:
        raise ValueError(f"{path.name}: CSV sin registros")
    match = re.search(r"_(\d{1,2})\.(?:csv|zip)$", path.name, re.I)
    return {"path": path.relative_to(root).as_posix(), "week": week,
            "namedWeek": int(match[1]) if match else None, "member": member,
            "rows": count, "sha256": hashlib.sha256(raw).hexdigest(),
            "uploadSha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def plan_queue(root: Path, source: str = "", requested_week: str = "") -> dict:
    if requested_week and not source:
        raise ValueError("indica source_path si eliges una semana manualmente")
    paths = [root / source] if source else incoming_files(root)
    entries = [source_info(root, path) for path in paths]
    if requested_week and any(item["week"] != parse_week(requested_week) for item in entries):
        raise ValueError("la semana solicitada no coincide con la columna Semana del CSV")
    groups = defaultdict(list)
    for item in entries:
        groups[item["week"]].append(item)
    unique, duplicates = [], []
    for week, candidates in sorted(groups.items()):
        if len({item["sha256"] for item in candidates}) != 1:
            raise ValueError(f"Semana {week}: hay fuentes distintas en incoming; conserva la corrección que deseas cargar")
        candidates.sort(key=lambda item: (item["namedWeek"] != week, not item["path"].lower().endswith(".csv"), item["path"]))
        unique.append(candidates[0])
        duplicates.extend({"path": item["path"], "duplicateOf": candidates[0]["path"], "week": week} for item in candidates[1:])
    return {"entries": entries, "sources": unique, "duplicates": duplicates,
            "misnamed": [item for item in entries if item["namedWeek"] not in (None, item["week"])]}


def source_args(stage: Path, item: dict) -> argparse.Namespace:
    return argparse.Namespace(root=stage, input=stage / item["path"], week=item["week"],
        directory=stage / "sources/Directorio.xlsx", prices=stage / "sources/Lista_Precios_Base.xlsx",
        presentations=stage / "tools/presentation_reference.json", unknown_store_policy="skip",
        report=stage / "audit" / f"week_{item['week']}_source_report.json", replace=True,
        sync_directory=True, allow_gaps=True)


def run_checks(root: Path) -> None:
    commands = [["node", "--check", "js/app.js"], ["node", "--check", "sw.js"],
        ["node", "tools/audit_business_rules.cjs"],
        [sys.executable, "-B", "tools/cleanup_obsolete.py"],
        [sys.executable, "-B", "tools/audit_data_integrity.py", "--report", "audit/data_integrity_report.json"],
        [sys.executable, "-B", "tools/audit_project.py"]]
    for command in commands:
        subprocess.run(command, cwd=root, check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def promote(stage: Path, root: Path, entries: list[dict]) -> None:
    """Reemplazos en el mismo sistema de archivos con recuperación ante cualquier fallo."""
    for item in entries:
        path = root / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["uploadSha256"]:
            raise ValueError(f"la carga cambió durante la validación: {item['path']}")
    with tempfile.TemporaryDirectory(prefix="maxmin-rollback-", dir=root.parent) as temporary:
        backup = Path(temporary)
        moved = []
        try:
            for name in ("data", "audit"):
                target = root / name
                if target.exists():
                    os.replace(target, backup / name)
                moved.append((target, backup / name))
                os.replace(stage / name, target)
            for item in entries:
                target = root / item["path"]
                saved = backup / item["path"]
                saved.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, saved)
                moved.append((target, saved))
        except BaseException:
            for target, saved in reversed(moved):
                if target.is_dir():
                    shutil.rmtree(target)
                if saved.exists():
                    os.replace(saved, target)
            raise


def process_queue(root: Path, source: str = "", week: str = "", before_promote=None) -> dict:
    root = root.resolve()
    plan = plan_queue(root, source, week)
    if not plan["sources"]:
        return {"status": "noop", "processedWeeks": [], "retiredSources": [],
                "pendingWeeks": read_manifest(root).get("pendingWeeks", [])}
    with tempfile.TemporaryDirectory(prefix="maxmin-validated-", dir=root.parent) as temporary:
        stage = Path(temporary) / "project"
        shutil.copytree(root, stage, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        (stage / "audit").mkdir(exist_ok=True)
        # Rechazar cualquier fuente defectuosa antes de modificar siquiera la copia.
        for item in plan["sources"]:
            audit(source_args(stage, item))
        published = []
        for item in plan["sources"]:
            args = source_args(stage, item)
            old = read_manifest(stage).get("weekSources", {}).get(str(item["week"]), {})
            if old.get("sha256") != item["sha256"]:
                update(args)
            args.report = stage / "audit" / f"week_{item['week']}_publish_report.json"
            published.append(verify(args))
        # Retirar sólo las fuentes que ya fueron contrastadas contra el motor.
        for item in plan["entries"]:
            (stage / item["path"]).unlink()
        run_checks(stage)
        for item in plan["sources"]:
            args = source_args(stage, item)
            # Verificación final de cada semana después de incorporar todo el lote.
            args.input = root / item["path"]
            args.report = stage / "audit" / f"week_{item['week']}_publish_report.json"
            verify(args)
        result = {"status": "ok", "processedWeeks": [item["week"] for item in plan["sources"]],
            "retiredSources": [item["path"] for item in plan["entries"]],
            "pendingWeeks": read_manifest(stage).get("pendingWeeks", []),
            "duplicates": plan["duplicates"], "misnamed": plan["misnamed"], "publications": published}
        (stage / "audit/week_queue_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if before_promote:
            before_promote()
        promote(stage, root, plan["entries"])
        return result


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


class NewUploads(RuntimeError):
    pass


def publish(args) -> dict:
    root = args.root.resolve()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main" or Path(os.environ.get("GITHUB_WORKSPACE", "")).resolve() != root:
        raise ValueError("--push sólo se admite en el checkout aislado de Actions para main")
    for attempt in range(3):
        baseline = git(root, "rev-parse", "HEAD")
        def ensure_current():
            git(root, "fetch", "origin", "main")
            if git(root, "rev-parse", "origin/main") != baseline:
                raise NewUploads("llegaron cargas nuevas")
        try:
            result = process_queue(root, args.input, args.week, ensure_current)
            if result["status"] == "noop":
                return result
            git(root, "add", "--", "data", "audit", *result["retiredSources"])
            if not git(root, "diff", "--cached", "--name-only"):
                return result
            git(root, "-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "commit", "-m", "data: publicar semanas verificadas " + ",".join(map(str, result["processedWeeks"])))
            try:
                git(root, "push", "origin", "HEAD:main")
                return result
            except subprocess.CalledProcessError:
                git(root, "fetch", "origin", "main")
                if git(root, "rev-parse", "origin/main") == baseline:
                    raise
                raise NewUploads("main cambió antes de publicar")
        except NewUploads:
            # Nunca rebasear JSON calculados sobre una carga distinta; recalcular todo.
            git(root, "reset", "--hard", "origin/main")
    raise RuntimeError("main sigue recibiendo cambios; las fuentes permanecen en GitHub para la siguiente ejecución")


def write_summary(path: str, result: dict) -> None:
    if not path:
        return
    lines = ["## Carga semanal Max-Min", "", "Estado: **" + result["status"] + "**",
        "", "Semanas verificadas: " + (", ".join(map(str, result.get("processedWeeks", []))) or "sin fuentes pendientes"),
        "", "Semanas pendientes (no se inventan datos): " + (", ".join(map(str, result.get("pendingWeeks", []))) or "ninguna")]
    if result.get("duplicates"):
        lines += ["", f"Fuentes idénticas procesadas una sola vez: {len(result['duplicates'])}."]
    for item in result.get("misnamed", []):
        lines += ["", f"Aviso: `{item['path']}` contiene Semana **{item['week']}**; se respetó el contenido."]
    if result.get("error"):
        lines += ["", result["error"], "", "El lote no fue publicado."]
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--input", default="")
    parser.add_argument("--week", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    try:
        report = publish(args) if args.push else process_queue(args.root, args.input, args.week)
    except (Exception, SystemExit) as error:
        report = {"status": "error", "error": str(error)}
        write_summary(args.summary, report)
        target = args.root / "audit/week_queue_failure.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
    write_summary(args.summary, report)
    print(json.dumps(report, ensure_ascii=False))
