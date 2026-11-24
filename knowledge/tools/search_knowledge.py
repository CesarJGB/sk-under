#!/usr/bin/env python3
"""Busca en catálogos, campos, dependencias y fuentes del conocimiento.

Ejemplos:
    python3 knowledge/tools/search_knowledge.py knight
    python3 knowledge/tools/search_knowledge.py pistol --catalog weapons
    python3 knowledge/tools/search_knowledge.py --field fishChip --json
    python3 knowledge/tools/search_knowledge.py --path gameData.hero --type fields
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sk_knowledge import common  # noqa: E402
from sk_knowledge.common import (  # noqa: E402
    CATALOGS_DIR,
    DEPENDENCIES_DIR,
    FIELDS_DIR,
    SOURCES_DIR,
    normalize_lookup,
    read_json,
)


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)
    elif value is not None:
        yield str(value)


def catalog_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(CATALOGS_DIR.glob("*.json")):
        document = read_json(path)
        for item in document.get("items", []):
            names = item.get("name") or {}
            records.append(
                {
                    "type": "catalog",
                    "catalog": document.get("family"),
                    "id": item.get("id"),
                    "name": names.get("en") or names.get("es"),
                    "category": item.get("category"),
                    "subcategory": item.get("subcategory"),
                    "text": " ".join(iter_strings(item)),
                    "item": item,
                }
            )
    return records


def field_records() -> list[dict[str, Any]]:
    document = read_json(FIELDS_DIR / "fields.json")
    records: list[dict[str, Any]] = []
    for field in document.get("fields", []):
        records.append(
            {
                "type": "field",
                "catalog": "fields",
                "id": field.get("id"),
                "name": field.get("internal_name"),
                "category": field.get("category"),
                "subcategory": field.get("registry_tier"),
                "text": " ".join(iter_strings(field)),
                "field": field,
            }
        )
    return records


def dependency_records() -> list[dict[str, Any]]:
    document = read_json(DEPENDENCIES_DIR / "dependencies.json")
    records: list[dict[str, Any]] = []
    for dependency in document.get("dependencies", []):
        records.append(
            {
                "type": "dependency",
                "catalog": "dependencies",
                "id": dependency.get("id"),
                "name": dependency.get("relation"),
                "category": dependency.get("status"),
                "subcategory": dependency.get("evidence"),
                "text": " ".join(iter_strings(dependency)),
                "dependency": dependency,
            }
        )
    return records


def source_records() -> list[dict[str, Any]]:
    path = SOURCES_DIR / "sources.json"
    if not path.is_file():
        return []
    document = read_json(path)
    records: list[dict[str, Any]] = []
    for source in document.get("sources", []):
        records.append(
            {
                "type": "source",
                "catalog": "sources",
                "id": source.get("id"),
                "name": source.get("title"),
                "category": source.get("type"),
                "subcategory": source.get("evidence"),
                "text": " ".join(iter_strings(source)),
                "source": source,
            }
        )
    return records


def score(record: dict[str, Any], terms: list[str], exact_id: str | None, path: str | None) -> int:
    score_value = 0
    haystack = normalize_lookup(record.get("text") or "")
    identifier = str(record.get("id") or "")
    if exact_id:
        if exact_id == identifier:
            score_value += 100
        elif normalize_lookup(exact_id) in normalize_lookup(identifier):
            score_value += 40
        else:
            return 0
    if path:
        if normalize_lookup(path) not in normalize_lookup(identifier) and normalize_lookup(path) not in haystack:
            return 0
        score_value += 30
    for term in terms:
        normalized = normalize_lookup(term)
        if not normalized:
            continue
        if normalized == normalize_lookup(identifier) or normalized == normalize_lookup(str(record.get("name") or "")):
            score_value += 25
        elif normalized in normalize_lookup(str(record.get("name") or "")):
            score_value += 12
        if normalized in haystack:
            score_value += 4
        else:
            return 0
    return score_value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terms", nargs="*", help="Nombres, identificadores o palabras clave.")
    parser.add_argument("--catalog", help="Limita a una familia de catálogo.")
    parser.add_argument("--category", help="Filtra por categoría.")
    parser.add_argument("--id", dest="exact_id", help="Identificador exacto o parcial.")
    parser.add_argument("--path", help="Ruta interna del guardado.")
    parser.add_argument("--field", help="Atajo para buscar un campo por nombre.")
    parser.add_argument("--type", choices=["all", "catalogs", "fields", "dependencies", "sources"], default="all")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    terms = list(args.terms)
    if args.field:
        terms.append(args.field)
    if not terms and not args.exact_id and not args.path:
        parser.error("Indica al menos un término, --id, --path o --field.")

    records: list[dict[str, Any]] = []
    if args.type in ("all", "catalogs"):
        records.extend(catalog_records())
    if args.type in ("all", "fields"):
        records.extend(field_records())
    if args.type in ("all", "dependencies"):
        records.extend(dependency_records())
    if args.type in ("all", "sources"):
        records.extend(source_records())

    if args.catalog:
        wanted = normalize_lookup(args.catalog)
        records = [record for record in records if normalize_lookup(str(record.get("catalog"))) == wanted]
    if args.category:
        wanted = normalize_lookup(args.category)
        records = [record for record in records if wanted in normalize_lookup(str(record.get("category")))]

    matches = []
    for record in records:
        value = score(record, terms, args.exact_id, args.path)
        if value:
            matches.append((value, record))
    matches.sort(key=lambda pair: (-pair[0], str(pair[1].get("catalog")), str(pair[1].get("id"))))
    matches = matches[: max(0, args.limit)]

    if args.json:
        payload = [
            {
                "score": value,
                "type": record["type"],
                "catalog": record.get("catalog"),
                "id": record.get("id"),
                "name": record.get("name"),
                "category": record.get("category"),
                "subcategory": record.get("subcategory"),
                "data": record.get(
                    {"catalog": "item", "field": "field", "dependency": "dependency", "source": "source"}.get(
                        record["type"], ""
                    ),
                    record,
                ),
            }
            for value, record in matches
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not matches:
        print("Sin resultados.")
        return 1
    print(f"{len(matches)} resultado(s):\n")
    for value, record in matches:
        name = record.get("name") or "(sin nombre)"
        print(
            f"- [{record['type']}:{record.get('catalog')}] {record.get('id')} "
            f"| {name} | {record.get('category')} / {record.get('subcategory') or '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())