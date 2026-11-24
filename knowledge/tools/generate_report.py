#!/usr/bin/env python3
"""Genera informes de cobertura, familia, campo o versión.

Ejemplos:
    python3 knowledge/tools/generate_report.py
    python3 knowledge/tools/generate_report.py --family materials
    python3 knowledge/tools/generate_report.py --field gameData.heroUnlock
    python3 knowledge/tools/generate_report.py --version 8.8.0
    python3 knowledge/tools/generate_report.py --output knowledge/reports/coverage.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sk_knowledge import common  # noqa: E402
from sk_knowledge.common import (  # noqa: E402
    CATALOGS_DIR,
    DEPENDENCIES_DIR,
    FIELDS_DIR,
    REPORTS_DIR,
    SOURCES_DIR,
    VERSION_DIFFS_DIR,
    read_json,
)


def load_all() -> dict[str, Any]:
    catalogs = {
        path.stem: read_json(path) for path in sorted(CATALOGS_DIR.glob("*.json"))
    }
    fields = read_json(FIELDS_DIR / "fields.json")
    dependencies = read_json(DEPENDENCIES_DIR / "dependencies.json")
    sources = read_json(SOURCES_DIR / "sources.json")
    snapshots = read_json(VERSION_DIFFS_DIR / "snapshots.json")
    return {
        "catalogs": catalogs,
        "fields": fields,
        "dependencies": dependencies,
        "sources": sources,
        "snapshots": snapshots,
    }


def named_count(document: dict[str, Any]) -> tuple[int, int]:
    items = document.get("items", [])
    named = sum(1 for item in items if (item.get("name") or {}).get("en"))
    return named, len(items)


def coverage(data: dict[str, Any]) -> dict[str, Any]:
    fields = data["fields"].get("fields", [])
    levels = Counter(field.get("validation_level") for field in fields)
    categories: dict[str, Counter[str]] = defaultdict(Counter)
    for field in fields:
        categories[field.get("category") or "sin categoría"][field.get("validation_level")] += 1
    catalogs = []
    for family, document in sorted(data["catalogs"].items()):
        named, total = named_count(document)
        catalogs.append(
            {
                "family": family,
                "title": document.get("title"),
                "count": total,
                "named_en": named,
                "name_coverage": round(named / total, 3) if total else None,
            }
        )
    statuses = Counter(
        dependency.get("status") for dependency in data["dependencies"].get("dependencies", [])
    )
    semantics = Counter(
        field.get("evidence", {}).get("semantics") for field in fields
    )
    return {
        "generated_by": "knowledge/tools/generate_report.py",
        "game_version": data["fields"].get("game_version"),
        "fields": {
            "total": len(fields),
            "by_level": dict(sorted(levels.items())),
            "by_category": {
                category: dict(sorted(counts.items()))
                for category, counts in sorted(categories.items())
            },
            "semantics": dict(sorted(semantics.items())),
            "open_questions": sum(len(field.get("open_questions", [])) for field in fields),
        },
        "catalogs": catalogs,
        "catalog_items": sum(catalog["count"] for catalog in catalogs),
        "translations": read_json(common.TRANSLATIONS_DIR / "name-index.json").get("count"),
        "dependencies": {
            "total": len(data["dependencies"].get("dependencies", [])),
            "by_status": dict(sorted(statuses.items())),
        },
        "sources": len(data["sources"].get("sources", [])),
        "versions_analyzed": sorted(data["snapshots"].get("versions", {})),
    }


def render_coverage(report: dict[str, Any]) -> str:
    lines = [
        "# Cobertura del Save Knowledge Engine",
        "",
        f"Versión del juego: **{report['game_version']}**.",
        "",
        "## Campos",
        "",
        f"- Total: **{report['fields']['total']}**",
        f"- Preguntas abiertas: **{report['fields']['open_questions']}**",
        "",
        "| Nivel | Campos |",
        "| --- | ---: |",
    ]
    for level, count in report["fields"]["by_level"].items():
        lines.append(f"| {level} | {count} |")
    lines += [
        "",
        "### Semántica",
        "",
        "| Nivel | Campos |",
        "| --- | ---: |",
    ]
    for level, count in report["fields"]["semantics"].items():
        lines.append(f"| {level} | {count} |")
    lines += [
        "",
        "### Categorías",
        "",
        "| Categoría | H | E1 | E2 | E3 | E4 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for category, counts in report["fields"]["by_category"].items():
        lines.append(
            f"| {category} | {counts.get('H', 0)} | {counts.get('E1', 0)} | "
            f"{counts.get('E2', 0)} | {counts.get('E3', 0)} | {counts.get('E4', 0)} |"
        )
    lines += [
        "",
        "## Catálogos",
        "",
        f"- Catálogos: **{len(report['catalogs'])}**",
        f"- Elementos: **{report['catalog_items']}**",
        f"- Traducciones indexadas: **{report['translations']}**",
        "",
        "| Catálogo | Elementos | Con nombre EN | Cobertura |",
        "| --- | ---: | ---: | ---: |",
    ]
    for catalog in report["catalogs"]:
        coverage_text = (
            f"{catalog['name_coverage'] * 100:.1f}%" if catalog["name_coverage"] is not None else "-"
        )
        lines.append(
            f"| {catalog['family']} | {catalog['count']} | {catalog['named_en']} | {coverage_text} |"
        )
    lines += [
        "",
        "## Dependencias y fuentes",
        "",
        f"- Dependencias: **{report['dependencies']['total']}**",
        f"- Fuentes: **{report['sources']}**",
        f"- Versiones analizadas: **{', '.join(report['versions_analyzed'])}**",
    ]
    for status, count in report["dependencies"]["by_status"].items():
        lines.append(f"- {status}: {count}")
    lines += [
        "",
        "> Los catálogos no prueban posesión. La cobertura de nombres no equivale a cobertura funcional.",
        "",
    ]
    return "\n".join(lines)


def render_family(family: str, document: dict[str, Any]) -> str:
    lines = [
        f"# Catálogo: {document.get('title')} (`{family}`)",
        "",
        f"- Elementos: **{document.get('count')}**",
        f"- Versión: {document.get('game_version')}",
        f"- Fuentes: {', '.join(ref.get('path', str(ref)) for ref in document.get('source_refs', []))}",
        "",
        "| id | nombre EN | categoría | subcategoría |",
        "| --- | --- | --- | --- |",
    ]
    for item in document.get("items", [])[:200]:
        name = (item.get("name") or {}).get("en") or ""
        lines.append(
            f"| `{item.get('id')}` | {name} | {item.get('category')} | {item.get('subcategory') or ''} |"
        )
    if document.get("count", 0) > 200:
        lines.append(f"\n_Mostrando 200 de {document.get('count')} elementos._")
    lines.append("")
    return "\n".join(lines)


def render_field(field: dict[str, Any]) -> str:
    lines = [
        f"# Campo: `{field.get('id')}`",
        "",
        f"- Nombre interno: `{field.get('internal_name')}`",
        f"- Categoría: {field.get('category')}",
        f"- Nivel global: **{field.get('validation_level')}**",
        f"- Política: {field.get('edit_policy')}",
        f"- Descripción: {field.get('description') or 'No documentada.'}",
        f"- Catálogo asociado: {field.get('associated_catalog') or '-'}",
        "",
        "## Evidencia",
        "",
        "| Aspecto | Nivel |",
        "| --- | --- |",
    ]
    for aspect, level in (field.get("evidence") or {}).items():
        lines.append(f"| {aspect} | {level} |")
    lines += [
        "",
        "## Ubicaciones",
        "",
        "```json",
        json.dumps(field.get("locations"), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Observaciones y límites",
        "",
        f"- Valores observados: `{json.dumps(field.get('observed_values'), ensure_ascii=False)}`",
        f"- Valores iniciales: `{json.dumps(field.get('initial_values'), ensure_ascii=False)}`",
        f"- Límites: `{json.dumps(field.get('limits'), ensure_ascii=False)}`",
        f"- Semántica conocida: {', '.join(field.get('known_value_semantics', [])) or 'Ninguna.'}",
        f"- Dependencias conocidas: {', '.join(map(str, field.get('known_dependencies', []))) or 'Ninguna.'}",
        f"- Dependencias pendientes: {', '.join(map(str, field.get('pending_dependencies', []))) or 'Ninguna.'}",
        "",
        "## Preguntas abiertas",
        "",
    ]
    questions = field.get("open_questions", [])
    lines += [f"- {question}" for question in questions] or ["- Ninguna registrada."]
    lines += ["", "## Experimentos necesarios", ""]
    experiments = field.get("experiments_required", [])
    lines += [f"- {experiment}" for experiment in experiments] or ["- Ninguno registrado."]
    lines += ["", "## Fuentes", ""]
    lines += [f"- `{source}`" for source in field.get("sources", [])]
    lines.append("")
    return "\n".join(lines)


def render_version(version: str, data: dict[str, Any]) -> str:
    snapshots = data["snapshots"].get("versions", {})
    if version not in snapshots:
        raise SystemExit(f"Versión desconocida: {version}")
    snapshot = snapshots[version]
    lines = [
        f"# Versión {version}",
        "",
        f"- Commit SKDFE: `{snapshot.get('commit')}`",
        "",
        "| Familia | Identificadores |",
        "| --- | ---: |",
    ]
    for family, count in sorted(snapshot.get("counts", {}).items()):
        lines.append(f"| {family} | {count} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family")
    parser.add_argument("--field")
    parser.add_argument("--version")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = load_all()

    if args.family:
        if args.family not in data["catalogs"]:
            raise SystemExit(f"Catálogo desconocido: {args.family}")
        payload = data["catalogs"][args.family]
        text = render_family(args.family, payload)
    elif args.field:
        fields = {field["id"]: field for field in data["fields"].get("fields", [])}
        if args.field not in fields:
            matches = [field for field in fields if args.field in field]
            if len(matches) != 1:
                raise SystemExit(
                    f"Campo desconocido o ambiguo: {args.field}. Coincidencias: {matches[:10]}"
                )
            args.field = matches[0]
        payload = fields[args.field]
        text = render_field(payload)
    elif args.version:
        payload = data["snapshots"].get("versions", {}).get(args.version)
        text = render_version(args.version, data)
    else:
        payload = coverage(data)
        text = render_coverage(payload)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
        relative = args.output.resolve().relative_to(common.REPO_ROOT)
        print(f"Informe escrito: {relative}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())