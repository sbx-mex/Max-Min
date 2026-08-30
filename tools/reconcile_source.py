#!/usr/bin/env python3
"""Reconcilia un CeCo contra los CSV originales antes de entregar/publicar."""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path

from build_data import norm, normalized_csv_lines, parse_week, text

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--ceco", default="38107")
    parser.add_argument("--weeks", default="18-25")
    args = parser.parse_args()
    start, end = (int(value) for value in args.weeks.split("-", 1))
    weeks = set(range(start, end + 1))

    source: dict[tuple[int, str], int] = {}
    with zipfile.ZipFile(args.zip) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".csv") or parse_week(name) not in weeks:
                continue
            week = parse_week(name)
            for row in csv.DictReader(normalized_csv_lines(archive.open(name))):
                if text(row.get("Tiendas")) != args.ceco:
                    continue
                cents = int(round(float(text(row.get("Uso Ideal* (#)")) or 0) * 100))
                if cents > 0:
                    source[(week, norm(row.get("Ingrediente")))] = cents

    manifest_source = (ROOT / "data" / "manifest.js").read_text(encoding="utf-8")
    manifest = json.loads(manifest_source.removeprefix("window.MAXMIN_MANIFEST=").strip()[:-1])
    store = next(item for item in manifest["stores"] if item["code"] == args.ceco)
    payload = json.loads((ROOT / store["file"]).read_text(encoding="utf-8"))
    compact: dict[tuple[int, str], int] = {}
    for week in weeks:
        flat = payload.get(str(week), [])
        for index in range(0, len(flat), 3):
            ingredient_id = flat[index + 1]
            compact[(week, norm(manifest["ingredients"][ingredient_id]["name"]))] = flat[index + 2]

    missing = sorted(set(source) - set(compact))
    extra = sorted(set(compact) - set(source))
    differences = sorted(key for key in source.keys() & compact.keys() if source[key] != compact[key])
    report = {
        "status": "ok" if not missing and not extra and not differences else "error",
        "ceco": args.ceco,
        "weeks": args.weeks,
        "sourceRecords": len(source),
        "compactRecords": len(compact),
        "missing": len(missing),
        "extra": len(extra),
        "valueDifferences": len(differences),
    }
    (ROOT / "audit" / "source_reconciliation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
