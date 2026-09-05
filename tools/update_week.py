#!/usr/bin/env python3
"""Incorpora un CSV semanal al motor compacto sin reconstruir el histórico."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from build_data import FILES_PER_FOLDER, load_crosses, load_directory_records, minified_json, norm, norm_variants, normalized_csv_lines, text
from data_integrity import write_integrity

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_HEADERS = {"Semana", "Tiendas", "Categoría Inventario", "Ingrediente", "Indicadores", "Uso Ideal* (#)"}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read_manifest(root: Path) -> dict[str, object]:
    source = (root / "data" / "manifest.js").read_text(encoding="utf-8")
    prefix = "window.MAXMIN_MANIFEST="
    if not source.startswith(prefix) or not source.rstrip().endswith(";"):
        fail("data/manifest.js no tiene una envoltura válida")
    return json.loads(source[len(prefix):].strip()[:-1])


def source_bytes(path: Path, week: int) -> tuple[bytes, str]:
    if not path.is_file():
        fail(f"no existe el archivo semanal: {path}")
    if path.suffix.lower() == ".csv":
        return path.read_bytes(), path.name
    if path.suffix.lower() != ".zip":
        fail("el archivo semanal debe ser CSV o ZIP")
    with zipfile.ZipFile(path) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith(".csv") and re.search(rf"_{week}\.csv$", name, re.IGNORECASE)]
        if len(candidates) != 1:
            fail(f"el ZIP debe contener exactamente un CSV terminado en _{week}.csv")
        return archive.read(candidates[0]), candidates[0]


def new_ingredient(source_name: str, micros: dict[str, tuple[str, str, str]], presentations: dict[str, dict[str, object]]) -> dict[str, object]:
    sap = next((micros[key] for key in norm_variants(source_name) if key in micros), ("", "", ""))
    presentation = presentations.get(norm(source_name), {})
    unit = text(presentation.get("unidad")) or "PZA:"
    pickpack = text(presentation.get("pickpack")) or unit
    factor = max(1, int(float(presentation.get("factor") or 1)))
    return {
        "name": source_name,
        "sap": sap[2] or source_name,
        "code": sap[1],
        "woe": sap[0],
        "unit": unit,
        "pickpack": pickpack,
        "factor": factor,
        "sapStatus": "ok" if sap[2] else "review",
        "formatStatus": "ok" if presentation else "review",
    }


def allocate_store_path(root: Path, store_entries: list[dict[str, object]], ceco: str) -> str:
    folder_counts: dict[int, int] = defaultdict(int)
    for store in store_entries:
        match = re.search(r"stores_(\d+)", str(store["file"]))
        if match:
            folder_counts[int(match.group(1))] += 1
    folder_number = max(folder_counts, default=1)
    if folder_counts[folder_number] >= FILES_PER_FOLDER:
        folder_number += 1
    folder = root / "data" / f"stores_{folder_number:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    return (folder / f"{ceco}.json").relative_to(root).as_posix()


def update(args: argparse.Namespace) -> dict[str, object]:
    root = args.root.resolve()
    manifest = read_manifest(root)
    week = args.week
    if not 1 <= week <= 53:
        fail("la semana debe estar entre 1 y 53")
    existing_weeks = [int(value) for value in manifest["weeks"]]
    replacing_existing_week = week in existing_weeks
    if replacing_existing_week and not args.replace:
        fail(f"la semana {week} ya existe; usa --replace sólo si deseas sustituirla")
    if week not in existing_weeks and existing_weeks and week != max(existing_weeks) + 1:
        fail(f"la siguiente semana esperada es {max(existing_weeks) + 1}, no {week}")

    directory_records = load_directory_records(args.directory)
    directory, micros, presentations = load_crosses(args.directory, args.prices, args.presentations)
    raw, source_name = source_bytes(args.input.resolve(), week)
    source_sha = hashlib.sha256(raw).hexdigest()
    reader = csv.DictReader(normalized_csv_lines(io.BytesIO(raw)))
    if not REQUIRED_HEADERS.issubset(set(reader.fieldnames or [])):
        fail(f"encabezados inválidos: {reader.fieldnames}")

    categories = manifest["categories"]
    ingredients = manifest["ingredients"]
    category_ids = {name: index for index, name in enumerate(categories)}
    ingredient_ids = {norm(item["name"]): index for index, item in enumerate(ingredients)}
    # Una clave CeCo/categoría/ingrediente sólo puede publicarse una vez. Guardar
    # primero en un mapa evita que un CSV defectuoso cree duplicados compactos.
    by_store: dict[str, dict[tuple[int, int], int]] = defaultdict(dict)
    source_keys: dict[tuple[str, str, str], int] = {}
    raw_rows = 0
    positive_rows = 0
    new_categories: list[str] = []
    new_ingredients: list[str] = []
    unknown_store_rows: Counter[str] = Counter()

    for row_number, row in enumerate(reader, start=2):
        raw_rows += 1
        try:
            row_week = int(float(text(row.get("Semana"))))
        except ValueError:
            fail(f"Semana inválida en fila {row_number}")
        if row_week != week:
            fail(f"fila {row_number}: se esperaba Semana {week} y se recibió {row_week}")
        if text(row.get("Indicadores")):
            fail(f"fila {row_number}: Indicadores debe permanecer vacío")
        ceco = text(row.get("Tiendas"))
        category = text(row.get("Categoría Inventario"))
        source_ingredient = text(row.get("Ingrediente"))
        try:
            usage = float(text(row.get("Uso Ideal* (#)")).replace(",", "") or 0)
        except ValueError:
            fail(f"fila {row_number}: Uso Ideal no es numérico")
        if usage <= 0 or not ceco or not category or not source_ingredient:
            continue
        if ceco not in directory:
            unknown_store_rows[ceco] += 1
            if args.unknown_store_policy == "fail":
                fail(f"fila {row_number}: CeCo {ceco} no existe en Directorio.xlsx")
            continue
        if category not in category_ids:
            category_ids[category] = len(categories)
            categories.append(category)
            new_categories.append(category)
        ingredient_key = norm(source_ingredient)
        ingredient_id = ingredient_ids.get(ingredient_key)
        if ingredient_id is None:
            ingredient_id = len(ingredients)
            ingredient_ids[ingredient_key] = ingredient_id
            ingredients.append(new_ingredient(source_ingredient, micros, presentations))
            new_ingredients.append(source_ingredient)
        source_key = (ceco, category, ingredient_key)
        if source_key in source_keys:
            fail(
                f"fila {row_number}: registro duplicado; ya apareció en fila "
                f"{source_keys[source_key]} ({ceco}, {category}, {source_ingredient})"
            )
        source_keys[source_key] = row_number
        cents = max(0, min(4_294_967_295, int(round(usage * 100))))
        by_store[ceco][(category_ids[category], ingredient_id)] = cents
        positive_rows += 1

    if raw_rows == 0:
        fail("el CSV semanal no contiene registros")

    store_entries = list(manifest["stores"])
    removed_directory_stores: list[str] = []
    if args.sync_directory:
        for store in list(store_entries):
            ceco = str(store["code"])
            if ceco in directory:
                continue
            path = root / str(store["file"])
            if path.is_file():
                path.unlink()
            store_entries.remove(store)
            removed_directory_stores.append(ceco)
    for store in store_entries:
        ceco = str(store["code"])
        if ceco not in directory_records:
            continue
        store["name"] = directory[ceco]
        store["label"] = f"{ceco} · {directory[ceco]}"
        store["status"] = directory_records[ceco]["status"]
    stores_by_code = {str(store["code"]): store for store in store_entries}
    added_stores: list[str] = []
    for ceco in sorted(by_store, key=lambda value: (int(value) if value.isdigit() else math.inf, value)):
        if ceco not in stores_by_code:
            relative = allocate_store_path(root, store_entries, ceco)
            store = {
                "code": ceco, "name": directory[ceco], "label": f"{ceco} · {directory[ceco]}",
                "file": relative, "status": directory_records[ceco]["status"],
            }
            store_entries.append(store)
            stores_by_code[ceco] = store
            added_stores.append(ceco)

    removed_stores: list[str] = []
    modified_files: list[str] = []
    for store in list(store_entries):
        ceco = str(store["code"])
        path = root / str(store["file"])
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if replacing_existing_week:
            payload.pop(str(week), None)
        if ceco in by_store:
            flat: list[int] = []
            for (category_id, ingredient_id), cents in sorted(by_store[ceco].items()):
                flat.extend((category_id, ingredient_id, cents))
            payload[str(week)] = flat
        if not payload:
            if path.is_file():
                path.unlink()
            store_entries.remove(store)
            removed_stores.append(ceco)
            continue
        ordered = {key: payload[key] for key in sorted(payload, key=int)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(minified_json(ordered), encoding="utf-8")
        if ceco in by_store or replacing_existing_week:
            modified_files.append(path.relative_to(root).as_posix())

    store_entries.sort(key=lambda store: (
        int(directory_records[str(store["code"])]["priority"]),
        int(store["code"]) if str(store["code"]).isdigit() else math.inf,
        str(store["code"]),
    ))
    manifest["stores"] = store_entries
    manifest["storesWithoutData"] = [
        {"code": code, "name": directory[code], "status": directory_records[code]["status"]}
        for code in sorted(directory, key=lambda value: (int(value) if value.isdigit() else math.inf, value))
        if code not in {str(store["code"]) for store in store_entries}
    ]
    manifest["weeks"] = sorted(set(existing_weeks + [week]))
    manifest["version"] = "4.2-directory-status"
    manifest["generated"] = date.today().isoformat()
    manifest["lastUpdate"] = {"week": week, "source": source_name, "sha256": source_sha}
    counts = manifest["counts"]
    old_rows = int(counts.get("rowsByWeek", {}).get(str(week), 0))
    old_positive = int(counts.get("positiveByWeek", {}).get(str(week), 0))
    counts["rows"] = int(counts["rows"]) - old_rows + raw_rows
    counts["positiveRows"] = int(counts["positiveRows"]) - old_positive + positive_rows
    counts.setdefault("rowsByWeek", {})[str(week)] = raw_rows
    counts.setdefault("positiveByWeek", {})[str(week)] = positive_rows
    counts["directoryStores"] = len(directory)
    counts["storesWithData"] = len(store_entries)
    counts["categories"] = len(categories)
    counts["ingredients"] = len(ingredients)
    counts["sapMatched"] = sum(item["sapStatus"] == "ok" for item in ingredients)
    counts["formatMatched"] = sum(item["formatStatus"] == "ok" for item in ingredients)
    counts["indicatorNonBlank"] = 0
    counts["openStores"] = sum(record["status"] == "Abierta" for record in directory_records.values())
    counts["temporaryClosedStores"] = sum(record["status"] == "Cierre Temporal" for record in directory_records.values())
    counts["excludedUnknownRows"] = sum(unknown_store_rows.values())
    published_by_week: Counter[str] = Counter()
    for store in store_entries:
        payload = json.loads((root / str(store["file"])).read_text(encoding="utf-8"))
        for published_week, flat in payload.items():
            published_by_week[str(published_week)] += len(flat) // 3
    counts["positiveByWeek"] = {str(value): published_by_week[str(value)] for value in manifest["weeks"]}
    counts["positiveRows"] = sum(published_by_week.values())
    (root / "data" / "manifest.js").write_text("window.MAXMIN_MANIFEST=" + minified_json(manifest) + ";\n", encoding="utf-8")
    write_integrity(root, manifest)

    review_path = root / "audit" / "ingredients_review.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["Ingrediente", "Descripción SAP", "Código DIA", "ID WOE", "Cruce SAP", "Cruce Formato"])
        writer.writeheader()
        for item in ingredients:
            if item["sapStatus"] != "ok" or item["formatStatus"] != "ok":
                writer.writerow({
                    "Ingrediente": item["name"], "Descripción SAP": item["sap"],
                    "Código DIA": item["code"], "ID WOE": item["woe"],
                    "Cruce SAP": item["sapStatus"], "Cruce Formato": item["formatStatus"],
                })

    folder_report = {
        folder.name: {"files": len(list(folder.glob("*.json"))), "bytes": sum(path.stat().st_size for path in folder.glob("*.json"))}
        for folder in sorted((root / "data").glob("stores_*"))
    }
    if any(info["files"] > 100 or info["bytes"] > 25 * 1024 * 1024 for info in folder_report.values()):
        fail("la actualización excede los límites de carpeta")
    report = {
        "status": "ok",
        "week": week,
        "mode": "replace" if replacing_existing_week else "insert",
        "replace": replacing_existing_week,
        "source": source_name,
        "sourceSha256": source_sha,
        "rows": raw_rows,
        "positiveRows": positive_rows,
        "storesUpdated": len(by_store),
        "filesModified": len(modified_files) + len(removed_directory_stores) + 3,
        "newStores": added_stores,
        "removedStores": removed_stores,
        "removedByDirectory": removed_directory_stores,
        "excludedUnknownStores": [
            {"ceco": code, "positiveRows": unknown_store_rows[code]}
            for code in sorted(unknown_store_rows)
        ],
        "excludedUnknownRows": sum(unknown_store_rows.values()),
        "newCategories": new_categories,
        "newIngredients": new_ingredients,
        "weeksAvailable": f"{min(manifest['weeks'])}-{max(manifest['weeks'])}",
        "folders": folder_report,
    }
    report_path = root / "audit" / f"week_{week}_update_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--sync-directory", action="store_true")
    parser.add_argument("--unknown-store-policy", choices=("fail", "skip"), default="skip")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--directory", type=Path, default=ROOT / "sources" / "Directorio.xlsx")
    parser.add_argument("--prices", type=Path, default=ROOT / "sources" / "Lista_Precios_Base.xlsx")
    parser.add_argument("--presentations", type=Path, default=ROOT / "tools" / "presentation_reference.json")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(update(parse_args()), ensure_ascii=False, indent=2))
