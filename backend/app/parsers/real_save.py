import base64
import json
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


def read_payload(data: bytes, key: bytes, iv: bytes) -> dict[str, object] | None:
    try:
        plain = unpad(DES.new(key, DES.MODE_CBC, iv).decrypt(data), DES.block_size)
        if not plain.lstrip().startswith(b"{"):
            return None
        parsed = parse_json(plain)
        if isinstance(parsed, dict):
            return parsed
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


def records_or_empty_dict(**members: type) -> Callable[[object], bool]:
    """Acepta la lista observada o el objeto vacío que usa una colección sin entradas."""
    as_records = records(list, **members)

    def check(value: object) -> bool:
        if type(value) is dict:
            return not value
        return as_records(value)

    return check


def entries_or_empty_dict(entry: type) -> Callable[[object], bool]:
    as_list = entries(list, entry)
    as_dict = entries(dict, entry)

    def check(value: object) -> bool:
        if type(value) is dict:
            return as_dict(value)
        return as_list(value)

    return check


@dataclass(frozen=True)
class Schema:
    name: str
    category: str
    markers: dict[str, type | Callable[[object], bool]]
    fields: dict[str, str]
    version: tuple[str, int] | None = None
    optional: tuple[str, ...] = ()
    alt_versions: tuple[int, ...] = ()

    def accepts_version(self, value: object) -> bool:
        if self.version is None:
            return True
        return type(value) is int and (value == self.version[1] or value in self.alt_versions)

    def matches(self, payload: dict[str, object]) -> bool:
        for key, expected in self.markers.items():
            if key in self.optional and key not in payload:
                continue
            value = payload.get(key)
            if isinstance(expected, type):
                if type(value) is not expected:
                    return False
            elif not expected(value):
                return False
        return True


SCHEMAS = {
    "bp_data": Schema("Pase de batalla", "Pase de batalla", {
        "seasonData": records_or_empty_dict(Key=int, Value=dict),
        "bpShopOthersPurchaseCounts": entries_or_empty_dict(int),
        "bpShopOthersRefreshMonthKey": int,
    }, {"seasonData": "Entradas de temporada"}, optional=("bpShopOthersPurchaseCounts",)),
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
    }, version=("AppVersion", 80300), alt_versions=(0, 80800)),
    "misc_data": Schema("Datos de retorno y efectos", "Efectos", {
        "returningEventCurrentDay": int,
        "isReturnPlayerInit": bool,
        "unlockedKillEffectIds": entries(list, int),
        "equippedKillEffectIdByScene": records(list, Key=int, Value=int),
    }, {"unlockedKillEffectIds": "Efectos de eliminación registrados"}, optional=("equippedKillEffectIdByScene",)),
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
    }, {"pvpLobbyOpenCount": "Aperturas de la sala PvP"}, optional=("pvpSkinSelectionByHero",)),
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
        "achieve_record": records_or_empty_dict(Key=int, Value=dict),
        "passInfo": entries(dict, str),
    }, {
        "StatisticsData": "Grupos de estadísticas registrados",
        "handbookWeaponCollectionTrackedLevels": "Entradas de armas en el manual",
        "achieve_record": "Entradas de logros",
    }, optional=("passInfo",)),
    "task": Schema("Tareas", "Tareas", {
        "NewTaskData": records(list, ID=int, Status=str, CurrentProgress=int, TargetProgress=int),
        "tasks": entries(list, dict),
        "ActivityTaskData": dict,
        "changeCount": int,
    }, {"NewTaskData": "Entradas de tareas nuevas", "tasks": "Entradas de tareas"}, optional=("ActivityTaskData",)),
    "weapon_evolution_data": Schema("Evolución de armas", "Armas", {
        "weapons": records(dict, Name=str, Level=int, CurrentSkinIndex=int, UnlockedSkins=list),
        "blindBoxOpenCount0": int,
        "favorWeapons": list,
    }, {"weapons": "Entradas de evolución de armas", "favorWeapons": "Armas favoritas registradas"},
        optional=("favorWeapons",)),
    "setting": Schema("Ajustes locales", "Ajustes", {
        "shakeLevel": int,
        "sandboxFlyable": bool,
        "promotionIndex": int,
        "bgmName": str,
        "customKeyboardLayoutVersion": int,
    }, {
        "shakeLevel": "Intensidad de vibración registrada",
        "promotionIndex": "Índice de promoción",
        "customKeyboardLayoutVersion": "Versión del diseño de teclado",
    }, optional=("customKeyboardLayoutVersion",)),
    "mall_reload": Schema("Recargas de tienda", "Tienda", {
        "mallPurchaseCountHistoryIndexed": dict,
        "buyGemCount800": int,
        "hasGetWeeklyBundle": bool,
    }, {
        "buyGemCount800": "Compras del paquete de 800 gemas",
        "buyGemCount5000": "Compras del paquete de 5000 gemas",
        "buyGemCount12000": "Compras del paquete de 12000 gemas",
    }),
    "escape_season": Schema("Temporada Escape", "Escape", {
        "version": int,
        "maxRaidSessionId": int,
        "money": int,
        "playerBag": dict,
        "safeSlots": dict,
        "totalIronMoneyEarned": int,
    }, {
        "money": "Dinero de Escape",
        "maxRaidSessionId": "Identificador máximo de incursión",
        "totalIronMoneyEarned": "Hierro acumulado",
    }, version=("version", 1)),
}


# Capa de ofuscación observada en ``game.data`` 8.8.0. No es autenticación ni
# cifrado fuerte: es un XOR repetido que el cliente aplica al JSON local. La
# clave se verificó contra la muestra auténtica del entorno privado.
LOCAL_GAME_XOR_KEY = bytes(
    (115, 108, 99, 122, 125, 103, 117, 99, 127, 87, 109, 108, 107, 74, 95)
)
MAX_GAME_DATA_BYTES = 8 * 1024 * 1024

GAME_DATA_SCHEMA = Schema(
    "Datos de juego",
    "Juego",
    {
        "skinLock": dict,
        "heroUnlock": dict,
        "heroLevel": dict,
        "gems": int,
        "roomLevel": int,
        "gameVersion": int,
        "lastPlayTime": int,
        "rebornCard": bool,
    },
    {
        "gems": "Gemas actuales",
        "lastGems": "Gemas de la última partida",
        "varGems": "Gemas variables",
        "cumulativeGems": "Gemas acumuladas",
        "cumulativeConsumeGems": "Gemas consumidas acumuladas",
        "fishChip": "Fichas de pesca",
        "roomLevel": "Nivel de la sala",
        "gameVersion": "Marcador de versión del juego",
        "lastPlayTime": "Última partida",
        "lastPlayTimeWithNetworkTime": "Última partida con hora de red",
        "totalGameTime": "Tiempo total de juego",
    },
)


def xor_game_data(data: bytes) -> bytes:
    key = LOCAL_GAME_XOR_KEY
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))


def decode_game_data(data: bytes) -> dict[str, object] | None:
    if not 0 < len(data) <= MAX_GAME_DATA_BYTES:
        return None
    try:
        parsed = parse_json(xor_game_data(data))
    except (ValueError, RecursionError):
        return None
    if isinstance(parsed, dict) and GAME_DATA_SCHEMA.matches(parsed):
        return parsed
    return None


def encode_game_data(document: dict[str, object]) -> bytes:
    plain = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return xor_game_data(plain)
