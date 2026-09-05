#!/usr/bin/env python3
"""Auditoría integral de estructura, datos, cruces, límites y exportación."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from build_data import load_directory_records

ROOT = Path(__file__).resolve().parents[1]
LIMIT_BYTES = 25 * 1024 * 1024
LIMIT_FILES = 100


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


required = [
    "index.html", "css/styles.css", "js/app.js", "sw.js", "manifest.webmanifest",
    "vendor/jspdf.umd.min.js", "data/manifest.js", "tools/build_data.py", "tools/update_week.py",
    "data/integrity.json", "data/normalized/integrity.json", "tools/data_integrity.py", "tools/audit_data_integrity.py",
    "data/normalized/manifest.js", "tools/build_normalized.py", "tools/audit_business_rules.cjs", "sources/Normalizados.zip",
    "sources/Directorio.xlsx", "sources/Lista_Precios_Base.xlsx",
    "updates/incoming/README.md", ".github/workflows/update-week.yml",
    ".github/workflows/rebuild-normalized.yml",
    "assets/ui/Damos_Seguimiento.webp", "assets/ui/Un_placer_haber_Ayudado.webp",
    "assets/reference/BOH_5S_Referencia.webp", "docs/guias/Guia_5S_BOH.pdf",
    "docs/guias/Alineacion_acomodo_items.pdf", "tools/audit_week_source.py",
    "tools/verify_week_publish.py",
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
directory = load_directory_records(ROOT / "sources" / "Directorio.xlsx")
if not weeks or weeks[0] != 1 or weeks != list(range(1, weeks[-1] + 1)):
    fail(f"las semanas no son continuas desde 1: {weeks}")
if counts["directoryStores"] != len(directory) or counts["storesWithData"] != len(manifest["stores"]):
    fail("conteo inconsistente de tiendas")
if counts.get("openStores") != sum(item["status"] == "Abierta" for item in directory.values()):
    fail("conteo inconsistente de tiendas abiertas")
if counts.get("temporaryClosedStores") != sum(item["status"] == "Cierre Temporal" for item in directory.values()):
    fail("conteo inconsistente de cierres temporales")
store_priorities = []
for store in manifest["stores"]:
    code = str(store["code"])
    if code not in directory:
        fail(f"tienda fuera del directorio vigente: {code}")
    if store.get("status") != directory[code]["status"]:
        fail(f"estatus desactualizado para {code}")
    store_priorities.append(int(directory[code]["priority"]))
if store_priorities != sorted(store_priorities):
    fail("las tiendas abiertas deben aparecer antes de los cierres temporales")
if counts["ingredients"] != len(manifest["ingredients"]) or counts["categories"] != len(manifest["categories"]):
    fail("conteo inconsistente de ingredientes o categorías")
if counts["indicatorNonBlank"] != 0:
    fail("Indicadores debe permanecer vacío")
if set(counts["rowsByWeek"]) != {str(week) for week in weeks} or set(counts["positiveByWeek"]) != {str(week) for week in weeks}:
    fail("faltan conteos semanales en el manifiesto")
if any(int(counts["positiveByWeek"][str(week)]) > int(counts["rowsByWeek"][str(week)]) for week in weeks):
    fail("un conteo positivo supera las filas de su semana")

referenced_store_files = [str(store["file"]) for store in manifest["stores"]]
if len(referenced_store_files) != len(set(referenced_store_files)):
    fail("el manifiesto contiene archivos de tienda duplicados")
actual_store_files = {
    path.relative_to(ROOT).as_posix()
    for path in (ROOT / "data").glob("stores_*/*.json")
}
orphan_store_files = sorted(actual_store_files - set(referenced_store_files))
if orphan_store_files:
    preview = ", ".join(orphan_store_files[:8])
    suffix = f" y {len(orphan_store_files) - 8} más" if len(orphan_store_files) > 8 else ""
    fail(f"persisten archivos de tienda huérfanos: {preview}{suffix}")

total_records = 0
records_by_week: Counter[str] = Counter()
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
        records = len(flat) // 3
        total_records += records
        records_by_week[str(int(week))] += records
if total_records != counts["positiveRows"]:
    differences = [
        f"Sem {week}: {records_by_week[str(week)]} vs {counts['positiveByWeek'][str(week)]}"
        for week in weeks
        if records_by_week[str(week)] != int(counts["positiveByWeek"][str(week)])
    ]
    fail(
        f"reconciliación fallida: {total_records} vs {counts['positiveRows']}; "
        + "; ".join(differences[:8])
    )
for week in weeks:
    if records_by_week[str(week)] != int(counts["positiveByWeek"][str(week)]):
        fail(
            f"reconciliación semanal fallida en {week}: "
            f"{records_by_week[str(week)]} vs {counts['positiveByWeek'][str(week)]}"
        )

normalized_source = (ROOT / "data" / "normalized" / "manifest.js").read_text(encoding="utf-8")
normalized_prefix = "window.MAXMIN_NORMALIZED="
if not normalized_source.startswith(normalized_prefix) or not normalized_source.rstrip().endswith(";"):
    fail("manifest.js de Normalizados no tiene envoltura válida")
normalized = json.loads(normalized_source[len(normalized_prefix):].strip()[:-1])
normalized_counts = normalized["counts"]
normalized_weeks = [int(value) for value in normalized["weeks"]]
if not normalized_weeks or normalized_weeks != sorted(set(normalized_weeks)):
    fail("las semanas de Normalizados no son válidas")
if normalized_counts["ingredients"] != len(normalized["ingredients"]) or normalized_counts["categories"] != len(normalized["categories"]):
    fail("conteo inconsistente en Normalizados")
if normalized_counts["storesWithData"] != len(normalized["stores"]):
    fail("conteo de tiendas inconsistente en Normalizados")
if normalized_counts["indicatorNonBlank"] != 0:
    fail("Indicadores debe permanecer vacío en Normalizados")
if normalized_counts["sapMatched"] != normalized_counts["ingredients"] or normalized_counts["formatMatched"] != normalized_counts["ingredients"]:
    fail("todos los insumos Normalizados deben tener cruce SAP y presentación")
last_source_week = normalized_weeks[-1]
for item in normalized["ingredients"]:
    report_weeks = [int(value) for value in item.get("reportWeeks", [])]
    if not report_weeks or report_weeks != sorted(set(report_weeks)):
        fail(f"semanas reportadas inválidas para {item.get('name')}")
    if item.get("source") != "normalizado" or item.get("firstWeek") != report_weeks[0] or item.get("lastWeek") != report_weeks[-1]:
        fail(f"vigencia inconsistente para {item.get('name')}")
    expected_stop = report_weeks[-1] + 1 if report_weeks[-1] < last_source_week else None
    if item.get("stoppedWeek") != expected_stop:
        fail(f"aviso de término inconsistente para {item.get('name')}")
normalized_records = 0
pedregal_normalized = False
for store in normalized["stores"]:
    code = str(store["code"])
    if code not in directory:
        fail(f"Normalizados contiene tienda fuera del directorio: {code}")
    path = ROOT / store["file"]
    if not path.is_file():
        fail(f"falta data Normalizados de {code}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if code == "38107":
        if sorted(int(value) for value in payload) != normalized_weeks:
            fail("la carga Normalizados de 38107 · Pedregal es inconsistente")
        pedregal_normalized = True
    for week, flat in payload.items():
        if int(week) not in normalized_weeks or len(flat) % 3:
            fail(f"registro Normalizados inválido en {path}")
        normalized_records += len(flat) // 3
if normalized_records != normalized_counts["positiveRows"]:
    fail(f"reconciliación Normalizados fallida: {normalized_records} vs {normalized_counts['positiveRows']}")
if not pedregal_normalized:
    fail("falta el cruce Normalizados para 38107 · Pedregal")
service_items = [item for item in normalized["ingredients"] if re.search(r"vaso|tapa", str(item.get("name", "")), re.IGNORECASE)]
if not service_items or not any(item["lastWeek"] == last_source_week for item in service_items) or not any(item["lastWeek"] < last_source_week for item in service_items):
    fail("Normalizados debe incluir vasos/tapas tanto vigentes como históricos")

salsa = [item for item in manifest["ingredients"] if item.get("name") == "Salsa de calabaza"]
if len(salsa) != 1 or salsa[0].get("unit") != "Bote 1.86 L" or salsa[0].get("pickpack") != "Caja 4 botes de 1.86 L" or salsa[0].get("factor") != 4:
    fail("la presentación de Salsa de calabaza debe interpretarse por bote de 1.86 L")

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
    "openExportConfirmation", "confirmExportDialog", "confirmExportSummary",
    "createSingleStoreFilter", "store.status", "photoCameraInput",
    "normalizedManifest", "NORMALIZED_INGREDIENT_BASE", "averageDivisor", "recipeNotice",
]
for marker in markers:
    if marker not in app:
        fail(f"falta marcador crítico: {marker}")

index_markers = [
    "assets/ui/Damos_Seguimiento.webp", "assets/ui/Un_placer_haber_Ayudado.webp",
    "Sistema de Evidencias OPS", "Jorge Alcantar Aguiar", "Enrique César Flores",
    "assets/reference/BOH_5S_Referencia.webp", "docs/guias/Guia_5S_BOH.pdf",
]
for marker in index_markers:
    if marker not in index:
        fail(f"falta elemento visual: {marker}")
for obsolete_copy in ["Control operativo confiable", "Valida, ajusta y corta etiquetas listas.", "Promedio dinámico:"]:
    if obsolete_copy in index:
        fail(f"persiste texto que debe estar oculto: {obsolete_copy}")
for obsolete_copy in ["Sem 25 o anteriores", "histórico de uso de vasos y tapas", "historyNote"]:
    if obsolete_copy in index or obsolete_copy in app:
        fail(f"persiste aviso histórico fijo: {obsolete_copy}")

report = {
    "status": "ok",
    "weeks": f"1-{weeks[-1]}",
    "stores": counts["storesWithData"],
    "ingredients": counts["ingredients"],
    "positiveRows": counts["positiveRows"],
    "sapMatched": counts["sapMatched"],
    "formatMatched": counts["formatMatched"],
    "normalized": {
        "weeks": f"{normalized_weeks[0]}-{normalized_weeks[-1]}",
        "stores": normalized_counts["storesWithData"],
        "ingredients": normalized_counts["ingredients"],
        "positiveRows": normalized_counts["positiveRows"],
        "sapMatched": normalized_counts["sapMatched"],
        "formatMatched": normalized_counts["formatMatched"],
        "currentIngredients": normalized_counts["currentIngredients"],
        "stoppedIngredients": normalized_counts["stoppedIngredients"],
        "notice": "por última semana reportada de cada ingrediente",
    },
    "pdf": {
        "format": "letter", "orientation": "landscape", "labelsPerPage": 12,
        "grid": "4x3", "multiPage": True, "compactHeaderMm": 8,
        "cardFields": ["Descripción SAP", "Nombre Inventario", "#DIA", "#SAP", "MIN", "MAX", "Formato", "Unidad de medida", "# Pedidos"],
    },
    "limits": {"maxFilesPerFolder": LIMIT_FILES, "maxImmediateBytesPerFolder": LIMIT_BYTES},
}
(ROOT / "audit" / "project_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
