#!/usr/bin/env python3
"""Construye el motor separado de insumos descontados por receta (Normalizados)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import shutil
import tempfile
import zipfile
from collections import Counter, OrderedDict, defaultdict
from datetime import date
from pathlib import Path

from build_data import FILES_PER_FOLDER, RECORD, load_crosses, load_directory_records, minified_json, norm_variants, text


class SpoolWriter:
    def __init__(self, root: Path, limit: int = 96) -> None:
        self.root = root
        self.limit = limit
        self.handles: OrderedDict[str, io.BufferedWriter] = OrderedDict()

    def write(self, ceco: str, payload: bytes) -> None:
        handle = self.handles.pop(ceco, None)
        if handle is None:
            if len(self.handles) >= self.limit:
                _, oldest = self.handles.popitem(last=False)
                oldest.close()
            handle = (self.root / f"{ceco}.bin").open("ab")
        handle.write(payload)
        self.handles[ceco] = handle

    def close(self) -> None:
        for handle in self.handles.values():
            handle.close()
        self.handles.clear()


def csv_reader(binary: io.BufferedReader) -> csv.DictReader:
    prefix = binary.read(2)
    binary.seek(0)
    encoding = "utf-16" if prefix in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    stream = io.TextIOWrapper(binary, encoding=encoding, newline="")
    for line in stream:
        candidate = line.lstrip("\ufeff\"")
        if candidate.startswith("Semana\"") or candidate.startswith("Semana,"):
            return csv.DictReader(itertools.chain([line.lstrip("\ufeff")], stream))
    raise ValueError("No se encontró el encabezado de Normalizados")


def build(args: argparse.Namespace) -> dict[str, object]:
    root = args.output.resolve()
    normalized_root = root / "data" / "normalized"
    if normalized_root.exists():
        shutil.rmtree(normalized_root)
    normalized_root.mkdir(parents=True, exist_ok=True)
    (root / "audit").mkdir(parents=True, exist_ok=True)

    directory_records = load_directory_records(args.directory)
    directory, micros, presentations = load_crosses(args.directory, args.prices, args.presentations)
    categories: list[str] = []
    category_ids: dict[str, int] = {}
    ingredients: list[dict[str, object]] = []
    ingredient_ids: dict[str, int] = {}
    ingredient_weeks: dict[int, set[int]] = defaultdict(set)
    stores_with_data: set[str] = set()
    weeks_seen: set[int] = set()
    rows_by_week: Counter[int] = Counter()
    positive_by_week: Counter[int] = Counter()
    unknown_store_rows: Counter[str] = Counter()
    indicator_nonblank = 0
    raw_rows = 0
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()

    with tempfile.TemporaryDirectory(prefix="maxmin-normalized-") as temp_name:
        spool_root = Path(temp_name)
        spool = SpoolWriter(spool_root)
        with zipfile.ZipFile(args.source) as archive:
            candidates = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(candidates) != 1:
                raise ValueError("Normalizados.zip debe contener exactamente un CSV")
            with archive.open(candidates[0]) as binary:
                reader = csv_reader(binary)
                required = {"Semana", "Tiendas", "Categoría Inventario", "Ingrediente", "Indicadores", "Uso Ideal* (#)"}
                if not required.issubset(set(reader.fieldnames or [])):
                    raise ValueError(f"Encabezados inválidos: {reader.fieldnames}")
                for row_number, row in enumerate(reader, start=2):
                    raw_rows += 1
                    try:
                        week = int(float(text(row.get("Semana"))))
                    except ValueError as error:
                        raise ValueError(f"Semana inválida en fila {row_number}") from error
                    if not 1 <= week <= 53:
                        raise ValueError(f"Semana fuera de rango en fila {row_number}: {week}")
                    weeks_seen.add(week)
                    rows_by_week[week] += 1
                    ceco = text(row.get("Tiendas"))
                    category = text(row.get("Categoría Inventario"))
                    source_name = text(row.get("Ingrediente"))
                    if text(row.get("Indicadores")):
                        indicator_nonblank += 1
                    try:
                        usage = float(text(row.get("Uso Ideal* (#)")).replace(",", "") or 0)
                    except ValueError as error:
                        raise ValueError(f"Uso Ideal inválido en fila {row_number}") from error
                    if usage <= 0 or not ceco or not category or not source_name:
                        continue
                    if ceco not in directory:
                        unknown_store_rows[ceco] += 1
                        if args.unknown_store_policy == "fail":
                            raise ValueError(f"CeCo {ceco} no existe en Directorio.xlsx")
                        continue
                    if category not in category_ids:
                        category_ids[category] = len(categories)
                        categories.append(category)
                    source_key = norm_variants(source_name)[0]
                    ingredient_id = ingredient_ids.get(source_key)
                    if ingredient_id is None:
                        ingredient_id = len(ingredients)
                        ingredient_ids[source_key] = ingredient_id
                        sap = next((micros[key] for key in norm_variants(source_name) if key in micros), ("", "", ""))
                        presentation = next((presentations[key] for key in norm_variants(source_name) if key in presentations), {})
                        unit = text(presentation.get("unidad")) or "Pieza"
                        pickpack = text(presentation.get("pickpack")) or unit
                        factor = max(1, int(float(presentation.get("factor") or 1)))
                        ingredients.append({
                            "name": source_name,
                            "sap": sap[2] or source_name,
                            "code": sap[1],
                            "woe": sap[0],
                            "unit": unit,
                            "pickpack": pickpack,
                            "factor": factor,
                            "sapStatus": "ok" if sap[2] else "review",
                            "formatStatus": "ok" if presentation else "review",
                            "source": "normalizado",
                        })
                    ingredient_weeks[ingredient_id].add(week)
                    cents = max(0, min(4_294_967_295, int(round(usage * 100))))
                    spool.write(ceco, RECORD.pack(week, category_ids[category], ingredient_id, cents))
                    stores_with_data.add(ceco)
                    positive_by_week[week] += 1
        spool.close()

        weeks = sorted(weeks_seen)
        if not weeks:
            raise ValueError("Normalizados.zip no contiene semanas válidas")
        last_source_week = weeks[-1]
        for ingredient_id, item in enumerate(ingredients):
            report_weeks = sorted(ingredient_weeks[ingredient_id])
            item["reportWeeks"] = report_weeks
            item["firstWeek"] = report_weeks[0]
            item["lastWeek"] = report_weeks[-1]
            item["stoppedWeek"] = report_weeks[-1] + 1 if report_weeks[-1] < last_source_week else None

        sorted_codes = sorted(
            stores_with_data,
            key=lambda code: (int(directory_records[code]["priority"]), int(code) if code.isdigit() else math.inf, code),
        )
        store_entries: list[dict[str, object]] = []
        for index, ceco in enumerate(sorted_codes):
            folder = normalized_root / f"stores_{index // FILES_PER_FOLDER + 1:02d}"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{ceco}.json"
            by_week: dict[str, list[int]] = defaultdict(list)
            raw = (spool_root / f"{ceco}.bin").read_bytes()
            if len(raw) % RECORD.size:
                raise ValueError(f"Spool dañado para {ceco}")
            for offset in range(0, len(raw), RECORD.size):
                week, category_id, ingredient_id, cents = RECORD.unpack_from(raw, offset)
                by_week[str(week)].extend((category_id, ingredient_id, cents))
            target.write_text(minified_json(dict(sorted(by_week.items(), key=lambda pair: int(pair[0])))), encoding="utf-8")
            store_entries.append({
                "code": ceco,
                "file": target.relative_to(root).as_posix(),
                "status": directory_records[ceco]["status"],
            })

    manifest = {
        "version": "1.0-normalizados",
        "generated": date.today().isoformat(),
        "sourceSha256": source_sha,
        "weeks": weeks,
        "categories": categories,
        "ingredients": ingredients,
        "stores": store_entries,
        "counts": {
            "directoryStores": len(directory),
            "storesWithData": len(stores_with_data),
            "categories": len(categories),
            "ingredients": len(ingredients),
            "rows": raw_rows,
            "positiveRows": sum(positive_by_week.values()),
            "rowsByWeek": {str(key): rows_by_week[key] for key in weeks},
            "positiveByWeek": {str(key): positive_by_week[key] for key in weeks},
            "sapMatched": sum(item["sapStatus"] == "ok" for item in ingredients),
            "formatMatched": sum(item["formatStatus"] == "ok" for item in ingredients),
            "indicatorNonBlank": indicator_nonblank,
            "currentIngredients": sum(item["lastWeek"] == weeks[-1] for item in ingredients),
            "stoppedIngredients": sum(item["lastWeek"] < weeks[-1] for item in ingredients),
            "excludedUnknownRows": sum(unknown_store_rows.values()),
        },
        "rule": "Cada ingrediente usa sólo sus semanas reportadas; la última semana determina cuándo dejó de descontarse por receta.",
    }
    (normalized_root / "manifest.js").write_text("window.MAXMIN_NORMALIZED=" + minified_json(manifest) + ";\n", encoding="utf-8")

    report = {
        "status": "ok",
        "generated": manifest["generated"],
        "sourceSha256": source_sha,
        "weeks": f"{weeks[0]}-{weeks[-1]}",
        "counts": manifest["counts"],
        "lastWeekDistribution": dict(sorted(Counter(item["lastWeek"] for item in ingredients).items())),
        "folders": {
            folder.name: {"files": len(list(folder.iterdir())), "bytes": sum(path.stat().st_size for path in folder.iterdir())}
            for folder in sorted(normalized_root.glob("stores_*"))
        },
        "excludedUnknownStores": [
            {"ceco": code, "positiveRows": unknown_store_rows[code]} for code in sorted(unknown_store_rows)
        ],
    }
    (root / "audit" / "normalized_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path = root / "audit" / "normalized_ingredients_review.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["Ingrediente", "Descripción SAP", "Código DIA", "#SAP", "Primera semana", "Última semana", "Aviso", "Cruce SAP", "Cruce Formato"])
        writer.writeheader()
        for item in ingredients:
            writer.writerow({
                "Ingrediente": item["name"],
                "Descripción SAP": item["sap"],
                "Código DIA": item["code"],
                "#SAP": item["woe"],
                "Primera semana": item["firstWeek"],
                "Última semana": item["lastWeek"],
                "Aviso": f"Dejó de descontarse desde Sem {item['stoppedWeek']}" if item["stoppedWeek"] else f"Reporta hasta Sem {item['lastWeek']}",
                "Cruce SAP": item["sapStatus"],
                "Cruce Formato": item["formatStatus"],
            })
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "sources" / "Normalizados.zip")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "sources" / "Directorio.xlsx")
    parser.add_argument("--prices", type=Path, default=Path(__file__).resolve().parents[1] / "sources" / "Lista_Precios_Base.xlsx")
    parser.add_argument("--presentations", type=Path, default=Path(__file__).with_name("presentation_reference.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--unknown-store-policy", choices=("fail", "skip"), default="skip")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), ensure_ascii=False, indent=2))
