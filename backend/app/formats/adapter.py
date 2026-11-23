from dataclasses import dataclass
from typing import Protocol

from pydantic import JsonValue

from ..models import EditableValue, EditorField, FormatInfo

type Document = dict[str, JsonValue]


@dataclass(frozen=True)
class SerializedFile:
    data: bytes
    filename: str
    media_type: str = "application/octet-stream"


class FormatAdapter(Protocol):
    info: FormatInfo

    def read_if_matching(self, data: bytes) -> Document | None:
        """Reconoce el formato y devuelve el documento validado."""
        ...

    def fields(self, document: Document) -> list[EditorField]:
        """Describe los campos que pueden mostrarse y modificarse."""
        ...

    def validate_changes(self, document: Document, changes: dict[str, EditableValue]) -> Document:
        """Devuelve un documento válido con las ediciones aplicadas a una copia."""
        ...

    def serialize(self, document: Document) -> SerializedFile:
        """Codifica el documento para descargarlo con un nombre seguro."""
        ...
