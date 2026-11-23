import base64
from collections.abc import Callable
from dataclasses import dataclass

from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad

from .json_document import parse_json


def ciphertext(data: bytes) -> bytes | None:
    try:
        decoded = base64.b64decode(data, validate=True)
    except ValueError:
        return None
    if not decoded or len(decoded) % DES.block_size or base64.b64encode(decoded) != data:
        return None
    return decoded


def read_payload(data: bytes, key: bytes, iv: bytes) -> tuple[str, dict] | None:
    try:
        plain = unpad(DES.new(key, DES.MODE_CBC, iv).decrypt(data), DES.block_size)
        if not plain.lstrip().startswith(b"{"):
            return None
        parsed = parse_json(plain)
        if isinstance(parsed, dict):
            return plain.decode("utf-8"), parsed
    except (ValueError, RecursionError):
        pass
    return None


def entries(container: type, entry: type) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        if type(value) is not container:
            return False
        values = value.values() if isinstance(value, dict) else value
        return all(type(item) is entry for item in values)

    return check


def records(container: type, **members: type) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        if type(value) is not container:
            return False
        values = value.values() if isinstance(value, dict) else value
        return all(
            type(item) is dict and all(type(item.get(key)) is expected for key, expected in members.items())
            for item in values
        )

    return check


@dataclass(frozen=True)
class Schema:
    name: str
    category: str
    markers: dict[str, type | Callable[[object], bool]]
    fields: dict[str, str]
    version: tuple[str, int] | None = None

    def matches(self, payload: dict) -> bool:
        for key, expected in self.markers.items():
            value = payload.get(key)
            if isinstance(expected, type):
                if type(value) is not expected:
                    return False
            elif not expected(value):
                return False
        return True


SCHEMAS = {
    "bp_data": Schema("Pase de batalla", "Pase de batalla", {
        "seasonData": records(list, Key=int, Value=dict),
        "bpShopOthersPurchaseCounts": list,
        "bpShopOthersRefreshMonthKey": int,
    }, {"seasonData": "Entradas de temporada"}),
    "item_data": Schema("Inventario", "Inventario", {
        "materials": entries(dict, int),
        "seeds": entries(dict, int),
        "blueprints": entries(dict, str),
        "itemUnlock": entries(list, str),
        "cumulativeFishCount": int,
    }, {
        "materials": "Tipos de materiales registrados",
        "seeds": "Tipos de semillas registrados",
        "blueprints": "Planos registrados",
        "itemUnlock": "Desbloqueos de objetos registrados",
        "cumulativeFishCount": "Peces acumulados",
    }, version=("AppVersion", 80300)),
    "misc_data": Schema("Datos de retorno y efectos", "Efectos", {
        "returningEventCurrentDay": int,
        "isReturnPlayerInit": bool,
        "unlockedKillEffectIds": entries(list, int),
        "equippedKillEffectIdByScene": records(list, Key=int, Value=int),
    }, {"unlockedKillEffectIds": "Efectos de eliminación registrados"}),
    "monsrise_data": Schema("Monster Rise", "Progreso", {
        "maxClearLevel": int,
        "pveGameTimes": int,
        "monsterTeams": list,
        "CollectedMonsters": dict,
    }, {
        "maxClearLevel": "Nivel máximo completado",
        "pveGameTimes": "Partidas PvE registradas",
        "CollectedMonsters": "Entradas de monstruos coleccionados",
    }, version=("version", 1)),
    "pvp_data": Schema("PvP", "PvP", {
        "isPvpFirstMatch": bool,
        "pvpLobbyOpenCount": int,
        "pvpTaskData": dict,
        "pvpSkinSelectionByHero": dict,
    }, {"pvpLobbyOpenCount": "Aperturas de la sala PvP"}),
    "season_data": Schema("Temporada", "Temporada", {
        "coin": int,
        "gainedCoinToday": int,
        "cumulativeCoinCount": int,
        "gainedCoinInSeason": entries(dict, int),
        "chips": records(list, chipName=str, level=int, refineLevel=int),
    }, {
        "coin": "Monedas de temporada",
        "gainedCoinToday": "Monedas de temporada obtenidas hoy",
        "cumulativeCoinCount": "Monedas de temporada acumuladas",
        "chips": "Chips registrados",
    }),
    "statistic": Schema("Estadísticas", "Estadísticas", {
        "StatisticsData": entries(dict, dict),
        "handbookWeaponCollectionTrackedLevels": entries(dict, int),
        "achieve_record": records(list, Key=int, Value=dict),
        "passInfo": entries(dict, str),
    }, {
        "StatisticsData": "Grupos de estadísticas registrados",
        "handbookWeaponCollectionTrackedLevels": "Entradas de armas en el manual",
        "achieve_record": "Entradas de logros",
    }),
    "task": Schema("Tareas", "Tareas", {
        "NewTaskData": records(list, ID=int, Status=str, CurrentProgress=int, TargetProgress=int),
        "tasks": entries(list, dict),
        "ActivityTaskData": dict,
        "changeCount": int,
    }, {"NewTaskData": "Entradas de tareas nuevas", "tasks": "Entradas de tareas"}),
    "weapon_evolution_data": Schema("Evolución de armas", "Armas", {
        "weapons": records(dict, Name=str, Level=int, CurrentSkinIndex=int, UnlockedSkins=list),
        "blindBoxOpenCount0": int,
        "favorWeapons": list,
    }, {"weapons": "Entradas de evolución de armas", "favorWeapons": "Armas favoritas registradas"}),
}
