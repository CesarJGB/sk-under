from ..formats.adapter import SerializedFile

def serialize_real_copy(kind: str, original: bytes) -> SerializedFile:
    return SerializedFile(data=original, filename=f"copia-{kind}.data")
