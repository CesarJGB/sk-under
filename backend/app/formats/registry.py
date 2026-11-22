from collections.abc import Sequence

from ..errors import EditorError
from .adapter import FormatAdapter
from .demo import DemoAdapter

ADAPTERS: tuple[FormatAdapter, ...] = (DemoAdapter(),)


def identify(data: bytes, adapters: Sequence[FormatAdapter]) -> FormatAdapter:
    matches = [adapter for adapter in adapters if adapter.matches(data)]
    if len(matches) != 1:
        raise EditorError(
            415,
            "unsupported_format",
            "La firma o versión del archivo no corresponde a un formato admitido.",
        )
    return matches[0]
