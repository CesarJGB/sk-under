"""Orquestación local: transporte → verificación → decodificación.

No hay reintentos ni acceso a red. El importador solo acepta un sobre que el
transporte ya obtuvo; un conector futuro deberá demostrar autorización antes
de implementar `CloudTransport`.
"""

from dataclasses import dataclass

from ..cloud_import import CopyMetadata, ImportedCopy
from ..cloud_save import JsonValue, MAX_INPUT_BYTES
from .decoder import DetectedFormat
from .transport import CloudTransport, RevisionMetadata, TransportEnvelope
from .validator import validate_payload


@dataclass(frozen=True)
class ImportedRevision:
    metadata: RevisionMetadata
    format: DetectedFormat
    copy: ImportedCopy

    def section(self, name: str) -> JsonValue:
        return self.copy.section(name)

    def summary(self) -> dict[str, object]:
        return self.copy.aggregate.summary()


class CloudImporter:
    def __init__(self, transport: CloudTransport, *, limit: int = MAX_INPUT_BYTES) -> None:
        self.transport = transport
        self.limit = limit

    def fetch(self) -> ImportedRevision:
        envelope: TransportEnvelope = self.transport.fetch_latest(self.limit)
        expected = CopyMetadata(envelope.metadata.size, envelope.metadata.sha256)
        validated = validate_payload(
            envelope.payload,
            expected=expected,
            limit=self.limit,
        )
        return ImportedRevision(
            metadata=envelope.metadata,
            format=validated.format,
            copy=ImportedCopy(validated.original, validated.aggregate),
        )


def import_from_transport(
    transport: CloudTransport, *, limit: int = MAX_INPUT_BYTES
) -> ImportedRevision:
    return CloudImporter(transport, limit=limit).fetch()
