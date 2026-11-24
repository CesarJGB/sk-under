"""Validación ejecutable dentro de la imagen real del backend.

No se recoge con pytest (el nombre no empieza por ``test_``). Se monta en el
contenedor junto con ``tests/fixtures`` y se ejecuta con el usuario de la
imagen para comprobar que el catálogo empaquetado es legible y que los flujos
de personajes, gemas y fichas de pesca siguen funcionando.

Uso:
    docker run --rm -e PYTHONPATH=/app -v "$PWD/tests:/check:ro" \
        --entrypoint python <imagen> /check/verify_image_catalog.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from app.catalogs import CATALOG_PATH, load_character_catalog
from app.cloud.character_editor import (
    CharacterCatalogMissing,
    InvalidCharacterSelection,
    UnknownCharacter,
    character_catalog_codes,
    prepare_character_unlock_edit,
    read_characters,
)
from app.cloud.fish_chip_editor import prepare_fish_chip_edit
from app.cloud.gems_editor import prepare_gems_edit
from app.cloud.skill_editor import (
    SkillCatalogMissing,
    IncompleteSkillStructure,
    UnknownSkillCharacter,
    UnknownSkillIndex,
    prepare_skill_unlock_edit,
    read_skills,
    skill_catalog,
)
from app.cloud.skin_editor import (
    IncompleteSkinStructure,
    SkinCatalogMissing,
    UnknownSkinCharacter,
    UnknownSkinIndex,
    prepare_skin_unlock_edit,
    read_skins,
    skin_catalog,
)
from app.save_report import _load_character_catalog, read_save_report

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def document(unlocked=("Knight",)) -> dict:
    data = json.loads(FIXTURE.read_bytes())
    codes = load_character_catalog()["codes"]
    data["gameData"]["gems"] = 1000
    data["gameData"]["heroUnlock"] = {code: code in unlocked for code in codes}
    data["gameData"]["heroLevel"] = {code: 0 for code in codes}
    data["gameData"]["heroLevel"]["Knight"] = 2
    data["gameData"]["heroSkill"] = {code: 0 for code in codes}
    catalog = load_character_catalog()
    data["gameData"]["heroSkillUnlock"] = {
        code: [
            {"Key": skill["index"], "Value": skill["index"] == 0}
            for skill in catalog["characters"][code]["skills"]
        ]
        for code in codes
    }
    data["gameData"]["skinLock"] = {
        code: [
            {"Key": skin["index"], "Value": 1 if skin["index"] == 0 else 0}
            for skin in catalog["characters"][code]["skins"]
        ]
        for code in codes
    }
    data["gameData"]["currentSkinDatas"] = {"Knight": 1}
    data["gameData"]["fishChip"] = 3
    data["itemData"]["materials"] = {"material_fish": 3, "material_ticket": 5}
    return data


def payload() -> bytes:
    return canonical(document())


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    try:
        check(os.geteuid() != 0, "la validación debe ejecutarse con el usuario no privilegiado")
        check(CATALOG_PATH.is_file(), "el catálogo no existe en la imagen")
        check(os.access(CATALOG_PATH, os.R_OK), "el catálogo no es legible")
        print(f"catálogo legible por uid={os.geteuid()}: {CATALOG_PATH}")

        catalog = _load_character_catalog()
        check(catalog.get("available") is True, "el catálogo empaquetado no está disponible")
        check(len(catalog["codes"]) == 42, "el catálogo no contiene 42 personajes")
        codes = character_catalog_codes()
        check(len(codes) == 42, "character_catalog_codes no devuelve 42 códigos")
        check(len(set(codes)) == 42, "los códigos del catálogo no son únicos")
        print("catálogo: 42 personajes y 42 códigos únicos")

        source = payload()
        snapshot = read_characters(source)
        check(snapshot.total == 42, "la lectura no declara 42 personajes")
        check(snapshot.unlocked == ("Knight",), "la lectura no conserva el desbloqueo original")

        single = prepare_character_unlock_edit(source, ["Ranger"])
        check(single.newly_unlocked == ("Ranger",), "la preparación individual no cambió Ranger")
        multiple = prepare_character_unlock_edit(source, ["Ranger", "Mage"])
        check(multiple.newly_unlocked == ("Ranger", "Mage"), "la preparación múltiple es incorrecta")
        remaining = [code for code in codes if code != "Knight"]
        massive = prepare_character_unlock_edit(source, remaining)
        check(massive.new_unlocked == codes, "la preparación masiva no desbloquea los 42")
        check(len(massive.changed_fields) == 41, "la preparación masiva cambió un número inesperado")
        print("preparación individual, múltiple y masiva de personajes: correcta")

        skill_catalog_data = skill_catalog()
        check(skill_catalog_data.total == 105, "el catálogo no declara 105 habilidades")
        skills = read_skills(source)
        check(skills.total == 105, "la lectura no declara 105 habilidades")
        check(len(skills.unlocked) == 42, "la lectura no conserva 42 habilidades disponibles")
        check(skills.characters_with_data == 42, "la lectura no cubre 42 personajes")
        skill_single = prepare_skill_unlock_edit(source, [{"code": "Knight", "index": 1}])
        check(
            [(ref.code, ref.index) for ref in skill_single.newly_unlocked] == [("Knight", 1)],
            "la preparación individual de habilidades es incorrecta",
        )
        skill_multiple = prepare_skill_unlock_edit(
            source,
            [
                {"code": "Knight", "index": 1},
                {"code": "Transcendent", "index": 1},
            ],
        )
        check(
            [(ref.code, ref.index) for ref in skill_multiple.newly_unlocked]
            == [("Knight", 1), ("Transcendent", 1)],
            "la preparación múltiple de habilidades es incorrecta",
        )
        all_locked = [
            {"code": code, "index": skill["index"]}
            for code in codes
            for skill in catalog["characters"][code]["skills"]
            if skill["index"] != 0
        ]
        skill_massive = prepare_skill_unlock_edit(source, all_locked)
        check(len(all_locked) == 63, "el catálogo no tiene 63 habilidades bloqueadas observadas")
        check(len(skill_massive.new_unlocked) == 105, "la preparación masiva no llega a 105")
        check(len(skill_massive.changed_fields) == 63, "la preparación masiva cambió un número inesperado")
        skill_candidate = json.loads(skill_massive.candidate)
        check(
            skill_candidate["gameData"]["heroSkill"]
            == json.loads(source)["gameData"]["heroSkill"],
            "la preparación de habilidades alteró heroSkill",
        )
        check(
            skill_candidate["gameData"]["heroUnlock"]
            == json.loads(source)["gameData"]["heroUnlock"],
            "la preparación de habilidades alteró heroUnlock",
        )
        print("lectura y preparación individual, múltiple y masiva de habilidades: correcta")

        skin_catalog_data = skin_catalog()
        check(skin_catalog_data.total == 802, "el catálogo no declara 802 skins")
        skins = read_skins(source)
        check(skins.total == 802, "la lectura no declara 802 skins")
        check(len(skins.unlocked) == 42, "la lectura no conserva 42 skins iniciales")
        check(skins.characters_with_data == 42, "la lectura no cubre 42 personajes")
        skin_single = prepare_skin_unlock_edit(source, [{"code": "Knight", "index": 1}])
        check(
            [(ref.code, ref.index) for ref in skin_single.newly_unlocked] == [("Knight", 1)],
            "la preparación individual de skins es incorrecta",
        )
        skin_multiple = prepare_skin_unlock_edit(
            source,
            [
                {"code": "Knight", "index": 1},
                {"code": "Ranger", "index": 1},
            ],
        )
        check(
            [(ref.code, ref.index) for ref in skin_multiple.newly_unlocked]
            == [("Knight", 1), ("Ranger", 1)],
            "la preparación múltiple de skins es incorrecta",
        )
        all_pending_skins = [
            {"code": code, "index": skin["index"]}
            for code in codes
            for skin in catalog["characters"][code]["skins"]
            if skin["index"] != 0
        ]
        skin_massive = prepare_skin_unlock_edit(source, all_pending_skins)
        check(len(all_pending_skins) == 760, "el catálogo no tiene 760 skins pendientes en la fixture")
        check(len(skin_massive.new_unlocked) == 802, "la preparación masiva no llega a 802")
        check(len(skin_massive.changed_fields) == 760, "la preparación masiva cambió un número inesperado")
        skin_candidate = json.loads(skin_massive.candidate)
        check(
            skin_candidate["gameData"]["currentSkinDatas"]
            == json.loads(source)["gameData"]["currentSkinDatas"],
            "la preparación de skins alteró currentSkinDatas",
        )
        check(
            skin_candidate["gameData"]["heroUnlock"]
            == json.loads(source)["gameData"]["heroUnlock"],
            "la preparación de skins alteró heroUnlock",
        )
        print("lectura y preparación individual, múltiple y masiva de skins: correcta")

        try:
            prepare_skin_unlock_edit(source, [{"code": "Knight", "index": 500}])
        except UnknownSkinIndex:
            pass
        else:
            raise AssertionError("un índice de skin inexistente no fue rechazado")
        try:
            prepare_skin_unlock_edit(source, [{"code": "NoExiste", "index": 0}])
        except UnknownSkinCharacter:
            pass
        else:
            raise AssertionError("un personaje desconocido de skin no fue rechazado")
        incomplete_skins = json.loads(source)
        incomplete_skins["gameData"]["skinLock"]["Ranger"] = []
        try:
            prepare_skin_unlock_edit(
                canonical(incomplete_skins), [{"code": "Ranger", "index": 1}]
            )
        except IncompleteSkinStructure:
            pass
        else:
            raise AssertionError("una estructura incompleta de skins no fue rechazada")

        try:
            prepare_skill_unlock_edit(source, [{"code": "Envoy", "index": 1}])
        except UnknownSkillIndex:
            pass
        else:
            raise AssertionError("un índice de habilidad inexistente no fue rechazado")
        try:
            prepare_skill_unlock_edit(source, [{"code": "NoExiste", "index": 0}])
        except UnknownSkillCharacter:
            pass
        else:
            raise AssertionError("un personaje desconocido no fue rechazado")
        incomplete = json.loads(source)
        incomplete["gameData"]["heroSkillUnlock"]["Envoy"] = []
        try:
            prepare_skill_unlock_edit(
                canonical(incomplete), [{"code": "Envoy", "index": 0}]
            )
        except IncompleteSkillStructure:
            pass
        else:
            raise AssertionError("una estructura incompleta de habilidades no fue rechazada")

        for selection, error in (
            (["NoExiste"], UnknownCharacter),
            ([], InvalidCharacterSelection),
            (["Ranger", "Ranger"], InvalidCharacterSelection),
        ):
            try:
                prepare_character_unlock_edit(source, selection)
            except error:
                pass
            else:
                raise AssertionError(f"la selección {selection!r} no fue rechazada")

        with tempfile.TemporaryDirectory() as directory:
            missing = load_character_catalog(Path(directory) / "missing.json")
            check(missing["available"] is False, "la ausencia del catálogo no se detectó")
            check(missing["error"] == "catalog_missing", "el error de ausencia no es catalog_missing")
            corrupt_path = Path(directory) / "corrupt.json"
            corrupt_path.write_text("{", encoding="utf-8")
            corrupt = load_character_catalog(corrupt_path)
            check(corrupt["available"] is False, "la corrupción del catálogo no se detectó")
            check(
                corrupt["error"] == "catalog_invalid_json",
                "el error de corrupción no es catalog_invalid_json",
            )

        import app.cloud.character_editor as editor

        original_loader = editor.load_character_catalog
        editor.load_character_catalog = lambda: {
            "available": False,
            "error": "catalog_missing",
            "codes": [],
        }
        try:
            try:
                character_catalog_codes()
            except CharacterCatalogMissing:
                pass
            else:
                raise AssertionError("la preparación no se bloqueó sin catálogo")
        finally:
            editor.load_character_catalog = original_loader
        import app.cloud.skill_editor as skill_module

        original_skill_loader = skill_module.load_character_catalog
        skill_module.load_character_catalog = lambda: {
            "available": False,
            "error": "catalog_missing",
            "codes": [],
        }
        try:
            try:
                prepare_skill_unlock_edit(source, [{"code": "Knight", "index": 1}])
            except SkillCatalogMissing:
                pass
            else:
                raise AssertionError("la preparación de habilidades no se bloqueó sin catálogo")
        finally:
            skill_module.load_character_catalog = original_skill_loader
        import app.cloud.skin_editor as skin_module

        original_skin_loader = skin_module.load_character_catalog
        skin_module.load_character_catalog = lambda: {
            "available": False,
            "error": "catalog_missing",
            "codes": [],
        }
        try:
            try:
                prepare_skin_unlock_edit(source, [{"code": "Knight", "index": 1}])
            except SkinCatalogMissing:
                pass
            else:
                raise AssertionError("la preparación de skins no se bloqueó sin catálogo")
        finally:
            skin_module.load_character_catalog = original_skin_loader
        print("ausencia, corrupción y bloqueo de personajes, habilidades y skins: controlados")

        gems = prepare_gems_edit(source, 1002)
        check(json.loads(gems.candidate)["gameData"]["gems"] == 1002, "la edición de gemas falló")
        check(json.loads(source)["gameData"]["gems"] == 1000, "la edición de gemas alteró el original")
        fish = prepare_fish_chip_edit(source, 7)
        candidate = json.loads(fish.candidate)
        check(candidate["gameData"]["fishChip"] == 7, "la edición de fichas no cambió fishChip")
        check(
            candidate["itemData"]["materials"]["material_fish"] == 7,
            "la edición de fichas no cambió material_fish",
        )
        check(candidate["gameData"]["gems"] == 1000, "la edición de fichas alteró las gemas")
        print("gemas y fichas de pesca: sin regresiones")

        report = read_save_report(source)
        check(report["characters"]["catalog"]["available"] is True, "el informe no ve el catálogo")
        check(report["characters"]["catalog"]["characters"] == 42, "el informe no ve 42 personajes")
        check(report["characters"]["skins"]["total"] == 802, "el informe no ve 802 skins")
        check(report["characters"]["skins"]["unlocked"] == 42, "el informe no ve 42 skins iniciales")
        check(report["fish_chips"]["balance"] == 3, "el informe no conserva las fichas")
        print("informe saneado: catálogo y fichas disponibles")
    except Exception as exc:  # noqa: BLE001 - el script debe fallar de forma legible
        print(f"FALLO: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("VALIDACIÓN DE IMAGEN COMPLETA: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())