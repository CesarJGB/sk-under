import json

from ..formats.adapter import Document, SerializedFile
from ..parsers.demo import DEMO_SIGNATURE


def serialize_demo(document: Document) -> SerializedFile:
    payload = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    return SerializedFile(DEMO_SIGNATURE + payload + b"\n", "copia-editada.skdemo")
