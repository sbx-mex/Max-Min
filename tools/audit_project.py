#!/usr/bin/env python3
"""Auditoría integral de estructura, datos, cruces, límites y exportación."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT_BYTES = 25 * 1024 * 1024
LIMIT_FILES = 100


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


required = [
    "index.html", "css/styles.css", "js/app.js", "sw.js", "manifest.webmanifest",
    "vendor/jspdf.umd.min.js", "data/manifest.js", "tools/build_data.py", "tools/update_week.py",
    "sources/Directorio.xlsx", "sources/Lista_Precios_Base.xlsx",
    "updates/incoming/README.md", ".github/workflows/update-week.yml",
]
for relative in required:
    if not (ROOT / relative).is_file():
        fail(f"falta {relative}")

legacy = list((ROOT / "js").glob("data_part_*.js")) + list((ROOT / "js").glob("data_sem_*.js"))
if legacy or (ROOT / "js" / "data_index.js").exists():
    fail("persisten motores de datos obsoletos")

for folder in [path for path in ROOT.rglob("*") if path.is_dir() and ".git" not in path.parts]:
    immediate_files = [path for path in folder.iterdir() if path.is_file()]
    if len(immediate_files) > LIMIT_FILES:
        fail(f"{folder.relative_to(ROOT)} contiene {len(immediate_files)} archivos")
    size = sum(path.stat().st_size for path in immediate_files)
    if size > LIMIT_BYTES:
        fail(f"{folder.relative_to(ROOT)} pesa {size} bytes en archivos directos")
for path in ROOT.rglob("*"):
    if path.is_file() and ".git" not in path.parts and path.stat().st_size > LIMIT_BYTES:
        fail(f"{path.relative_to(ROOT)} supera 25 MB")

manifest_source = (ROOT / "data" / "manifest.js").read_text(encoding="utf-8")
prefix = "window.MAXMIN_MANIFEST="
if not manifest_source.startswith(prefix) or not manifest_source.rstrip().endswith(";"):
    fail("manifest.js no tiene envoltura válida")
manifest = json.loads(manifest_source[len(prefix):].strip()[:-1])
counts = manifest["counts"]
weeks = [int(value) for value in manifest["weeks"]]
if not weeks or weeks[0] != 1 or weeks != list(range(1, weeks[-1] + 1)):
    fail(f"las semanas no son continuas desde 1: {weeks}")
if counts["directoryStores"] < counts["storesWithData"] or counts["storesWithData"] != len(manifest["stores"]):
    fail("conteo inconsistente de tiendas")
if counts["ingredients"] != len(manifest["ingredients"]) or counts["categories"] != len(manifest["categories"]):
    fail("conteo inconsistente de ingredientes o categorías")
if counts["indicatorNonBlank"] != 0:
    fail("Indicadores debe permanecer vacío")
if set(counts["rowsByWeek"]) != {str(week) for week in weeks} or set(counts["positiveByWeek"]) != {str(week) for week in weeks}:
    fail("faltan conteos semanales en el manifiesto")
if any(int(counts["positiveByWeek"][str(week)]) > int(counts["rowsByWeek"][str(week)]) for week in weeks):
    fail("un conteo positivo supera las filas de su semana")

total_records = 0
for store in manifest["stores"]:
    path = ROOT / store["file"]
    if not path.is_file():
        fail(f"falta data de {store['code']}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for week, flat in payload.items():
        if int(week) not in weeks:
            fail(f"semana inválida en {path}")
        if len(flat) % 3:
            fail(f"registro compacto incompleto en {path}")
        total_records += len(flat) // 3
if total_records != counts["positiveRows"]:
    fail(f"reconciliación fallida: {total_records} vs {counts['positiveRows']}")

index = (ROOT / "index.html").read_text(encoding="utf-8")
app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
styles = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
if len(re.findall(r'class="tab(?: active)?" data-tab=', index)) != 3:
    fail("deben existir exactamente tres pestañas")
if "sidebar" in styles.lower() or "margin-left:var(--sidebar)" in styles:
    fail("se detectó menú lateral")
markers = [
    'format: "letter"', 'orientation: "landscape"', "pdf.addPage", "PAGE_SIZE = 12",
    "Math.floor(index / 3)", "index % 3", "drawPdfHeader", "drawPdfLabel",
    "pdf.internal.getNumberOfPages()", "fetchStoreData(store.file", "compactWeeks",
    'const headerH = 8', 'item.woe || "—"', "#DIA", "#SAP", "PEDIDOS",
    "latestWeeks", "data-week-preset", "activeFilterSummary",
]
for marker in markers:
    if marker not in app:
        fail(f"falta marcador crítico: {marker}")

report = {
    "status": "ok",
    "weeks": f"1-{weeks[-1]}",
    "stores": counts["storesWithData"],
    "ingredients": counts["ingredients"],
    "positiveRows": counts["positiveRows"],
    "sapMatched": counts["sapMatched"],
    "formatMatched": counts["formatMatched"],
    "pdf": {
        "format": "letter", "orientation": "landscape", "labelsPerPage": 12,
        "grid": "4x3", "multiPage": True, "compactHeaderMm": 8,
        "cardFields": ["Descripción SAP", "Nombre Inventario", "#DIA", "#SAP", "MIN", "MAX", "Formato", "Unidad de medida", "# Pedidos"],
    },
    "limits": {"maxFilesPerFolder": LIMIT_FILES, "maxImmediateBytesPerFolder": LIMIT_BYTES},
}
(ROOT / "audit" / "project_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
