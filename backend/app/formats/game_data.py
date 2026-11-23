"""Adaptador de solo lectura para ``game.data`` (AboGameData) local 8.8.0."""

from dataclasses import dataclass, field
from typing import cast

from ..errors import EditorError
from ..models import EditableValue, EditorField, FormatInfo, IntegerField, TextField
from ..parsers.real_save import GAME_DATA_SCHEMA, decode_game_data
from .adapter import Document, SerializedFile

JS_SAFE_INTEGER = (1 << 53) - 1


@dataclass(frozen=True)
class GameDataAdapter:
    info = FormatInfo(
        id="sk-local-game-xor",
        name="Datos de juego locales",
        version="8.8.0 (local)",
        extensions=[".data"],
        compatibility="read_only",
        description="AboGameData de game.data con la capa XOR observada en 8.8.0. Inspección y copia intacta.",
    )

    def read_if_matching(self, data: bytes) -> Document | None:
        payload = decode_game_data(data)
        if payload is None:
            return None
        values: dict[str, int] = {}
        for name in GAME_DATA_SCHEMA.fields:
            value = payload.get(name)
            if type(value) is int:
                values[name] = value
        return {"kind": "game_data", "values": values}

    def fields(self, document: Document) -> list[EditorField]:
        values = cast(dict[str, int], document["values"])
        fields: list[EditorField] = [
            TextField(id="save_type", label="Tipo de archivo", category="Formato", editable=False,
                      value=GAME_DATA_SCHEMA.name, min_length=0, max_length=len(GAME_DATA_SCHEMA.name)),
        ]
        fields.extend(
            self.number(name, label, GAME_DATA_SCHEMA.category, values[name])
            for name, label in GAME_DATA_SCHEMA.fields.items()
            if name in values
        )
        return fields

    @staticmethod
    def number(name: str, label: str, category: str, value: int) -> EditorField:
        if -JS_SAFE_INTEGER <= value <= JS_SAFE_INTEGER:
            return IntegerField(id=name, label=label, category=category, editable=False,
                                value=value, minimum=-JS_SAFE_INTEGER, maximum=JS_SAFE_INTEGER)
        text = str(value)
        return TextField(id=name, label=label, category=category, editable=False,
                         value=text, min_length=0, max_length=len(text))

    def validate_changes(self, document: Document, changes: dict[str, EditableValue]) -> Document:
        if changes:
            raise EditorError(422, "invalid_changes", "El formato admite únicamente copias intactas.")
        return document

    def serialize(self, document: Document, original: bytes) -> SerializedFile:
        return SerializedFile(data=original, filename="copia-game.data")
