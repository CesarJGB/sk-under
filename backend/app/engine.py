from collections.abc import Sequence
from dataclasses import dataclass, replace
from hashlib import sha256

from .errors import EditorError
from .file_validation import require_size
from .formats.adapter import FormatAdapter, SerializedFile
from .formats.registry import ADAPTERS, identify
from .models import AppliedChange, EditableValue, FormatInfo, Inspection, Issue, Validation


@dataclass(frozen=True)
class PreparedExport:
    file: SerializedFile
    validation: Validation


class Editor:
    def __init__(self, adapters: Sequence[FormatAdapter] = ADAPTERS) -> None:
        self.adapters = tuple(adapters)

    def formats(self) -> list[FormatInfo]:
        return [adapter.info for adapter in self.adapters]

    def inspect(self, original: bytes) -> Inspection:
        adapter, document = identify(original, self.adapters)
        return Inspection(
            format=adapter.info,
            byte_size=len(original),
            sha256=sha256(original).hexdigest(),
            fields=adapter.fields(document),
        )

    def prepare_export(
        self, original: bytes, changes: dict[str, EditableValue], size_limit: int
    ) -> PreparedExport:
        adapter, document = identify(original, self.adapters)
        editable = {field.id: field.value for field in adapter.fields(document) if field.editable}
        if changes.keys() - editable.keys():
            raise EditorError(
                422, "invalid_changes", "La solicitud incluye campos que no se pueden editar.",
                [Issue(code="field_not_editable", message="Envía solo campos editables de la inspección.")],
            )

        candidate = adapter.validate_changes(document, changes)
        modified = {field.id: field.value for field in adapter.fields(candidate) if field.editable}
        applied = [
            AppliedChange(field_id=field_id, original=value, modified=modified[field_id])
            for field_id, value in editable.items()
            if value != modified[field_id]
        ]
        output = adapter.serialize(candidate, original)
        if candidate == document and adapter.info.compatibility != "read_only":
            output = replace(output, data=original)
        require_size(output.data, size_limit)
        try:
            if adapter.info.compatibility == "read_only" and output.data != original:
                raise ValueError("La copia de solo lectura difiere del original.")
            roundtrip, reopened = identify(output.data, self.adapters)
            if roundtrip is not adapter or reopened != candidate:
                raise ValueError("El documento no coincide después de serializarlo.")
        except (EditorError, ValueError):
            raise EditorError(
                500, "export_verification_failed", "La copia generada no pasó la verificación de lectura."
            ) from None

        return PreparedExport(
            output,
            Validation(
                changes=applied,
                output_byte_size=len(output.data),
                output_sha256=sha256(output.data).hexdigest(),
            ),
        )
