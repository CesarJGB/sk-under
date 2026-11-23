from collections.abc import Sequence

from ..errors import EditorError
from .adapter import Document, FormatAdapter
from .demo import DemoAdapter

ADAPTERS: tuple[FormatAdapter, ...] = (DemoAdapter(),)


def identify(data: bytes, adapters: Sequence[FormatAdapter]) -> tuple[FormatAdapter, Document]:
    matches = [
        (adapter, document)
        for adapter in adapters
        if (document := adapter.read_if_matching(data)) is not None
    ]
    if len(matches) != 1:
        raise EditorError(
            415,
            "unsupported_format",
            "La firma o versión del archivo no corresponde a un formato admitido.",
        )
    return matches[0]
