from ..models import EditableValue, EditorField, FormatInfo, IntegerField, TextField
from ..parsers.demo import (
    DEMO_SIGNATURE, MAX_LABEL, MAX_SAMPLE, MIN_LABEL, MIN_SAMPLE,
    DemoDocument, read_demo, validate_demo,
)
from ..serializers.demo import serialize_demo
from .adapter import Document, SerializedFile


class DemoAdapter:
    info = FormatInfo(
        id="sk-editor-demo-v1",
        name="Muestra de demostración",
        version="1",
        extensions=[".skdemo"],
        compatibility="synthetic",
        description="Datos de prueba para recorrer la edición y exportación de una copia sintética.",
    )

    def read_if_matching(self, data: bytes) -> Document | None:
        if data.startswith(DEMO_SIGNATURE):
            return read_demo(data).model_dump(mode="json")
        return None

    def fields(self, document: Document) -> list[EditorField]:
        # El motor solo entrega documentos validados por este adaptador.
        data = DemoDocument.model_construct(**document)
        return [
            TextField(
                id="label", label="Etiqueta", category="Identificación", value=data.label,
                editable=True, min_length=MIN_LABEL, max_length=MAX_LABEL,
            ),
            TextField(
                id="fixture_id", label="ID de muestra", category="Identificación",
                value=data.fixture_id, editable=False, min_length=1, max_length=40,
            ),
            IntegerField(
                id="sample_count", label="Cantidad de prueba", category="Límites",
                value=data.sample_count, editable=True, minimum=MIN_SAMPLE, maximum=MAX_SAMPLE,
            ),
            IntegerField(
                id="sample_limit", label="Límite de prueba", category="Límites",
                value=data.sample_limit, editable=True, minimum=MIN_SAMPLE, maximum=MAX_SAMPLE,
            ),
        ]

    def validate_changes(self, document: Document, changes: dict[str, EditableValue]) -> Document:
        return validate_demo(document | changes, applying_changes=True).model_dump(mode="json")

    def serialize(self, document: Document) -> SerializedFile:
        return serialize_demo(document)
