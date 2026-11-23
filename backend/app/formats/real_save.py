from dataclasses import dataclass, field
from typing import cast

from ..errors import EditorError
from ..models import EditableValue, EditorField, FormatInfo, IntegerField, TextField
from ..parsers.real_save import SCHEMAS, ciphertext, read_payload
from ..serializers.real_save import encode_payload
from .adapter import Document, SerializedFile

JS_SAFE_INTEGER = (1 << 53) - 1


@dataclass(frozen=True)
class RealSaveAdapter:
    general_key: bytes = field(repr=False)
    statistics_key: bytes = field(repr=False)
    iv: bytes = field(repr=False)

    info = FormatInfo(
        id="sk-local-des-cbc",
        name="Guardado local de Soul Knight",
        version="8.6.0 (muestras)",
        extensions=[".data"],
        compatibility="read_only",
        description="Nueve estructuras observadas en 8.6.0. Inspección y descarga de una copia intacta.",
    )

    def read_if_matching(self, data: bytes) -> Document | None:
        encrypted = ciphertext(data)
        if encrypted is None:
            return None

        matches = []
        for key, statistics in ((self.general_key, False), (self.statistics_key, True)):
            result = read_payload(encrypted, key, self.iv)
            if result is None:
                continue
            plaintext, payload = result
            matches.extend(
                (kind, payload, plaintext) for kind, schema in SCHEMAS.items()
                if (kind == "statistic") == statistics and schema.matches(payload)
            )

        if len(matches) != 1:
            return None

        kind, payload, plaintext = matches[0]
        schema = SCHEMAS[kind]
        values: dict[str, int] = {}
        for name in schema.fields:
            value = payload[name]
            values[name] = len(value) if isinstance(value, (list, dict)) else value
        if schema.version is not None:
            name, version = schema.version
            value = payload.get(name)
            if type(value) is not int or value != version:
                raise EditorError(415, "unsupported_version", "El marcador de versión del archivo está fuera de la cobertura verificada.")
            values[name] = value

        return {"kind": kind, "values": values, "plaintext": plaintext}

    def fields(self, document: Document) -> list[EditorField]:
        kind = str(document["kind"])
        schema = SCHEMAS[kind]
        values = cast(dict[str, int], document["values"])
        fields: list[EditorField] = [
            TextField(id="save_type", label="Tipo de archivo", category="Formato", editable=False,
                      value=schema.name, min_length=0, max_length=len(schema.name)),
        ]
        if schema.version is not None:
            name, _ = schema.version
            fields.append(self.number(name, f"Marcador interno ({name})", "Formato", values[name]))
        fields.extend(
            self.number(name, label, schema.category, values[name])
            for name, label in schema.fields.items()
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

    def serialize(self, document: Document) -> SerializedFile:
        kind = str(document["kind"])
        key = self.statistics_key if kind == "statistic" else self.general_key
        data = encode_payload(str(document["plaintext"]), key, self.iv)
        return SerializedFile(data=data, filename=f"copia-{kind}.data")
