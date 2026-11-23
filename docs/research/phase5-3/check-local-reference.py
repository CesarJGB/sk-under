"""Ensayo privado de reserialización de un subsistema de 8.6.0 en memoria."""

import argparse
import base64
import json
from hashlib import sha256
from pathlib import Path

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad

from app.cloud_import import LocalFileSource
from app.cloud_save import MAX_INPUT_BYTES
from app.formats.real_save import RealSaveAdapter
from app.parsers.json_document import parse_json
from app.settings import Settings


def check(path, cipher, inventory):
    original = LocalFileSource(path).read(MAX_INPUT_BYTES)
    digest = sha256(original).hexdigest()
    if not any(f"`{path.name}`" in row and f"`{digest}`" in row for row in inventory):
        raise ValueError("La referencia difiere del inventario privado.")
    general, statistics, iv = cipher
    match = RealSaveAdapter(general, statistics, iv).read_if_matching(original)
    if match is None:
        raise ValueError("Subsistema fuera del conjunto reconocido.")
    kind = match["kind"]
    key = statistics if kind == "statistic" else general
    raw = base64.b64decode(original, validate=True)
    plain = unpad(DES.new(key, DES.MODE_CBC, iv).decrypt(raw), DES.block_size)
    tree = parse_json(plain)

    def repack(document):
        encrypted = DES.new(key, DES.MODE_CBC, iv).encrypt(pad(document, DES.block_size))
        return base64.b64encode(encrypted)

    if repack(plain) != original:
        raise ValueError("La reconstrucción del texto original difiere.")
    compact = json.dumps(tree, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    pretty = json.dumps(tree, ensure_ascii=False, indent=2, allow_nan=False).encode()
    if repack(compact) == original:
        profile = "compact"
    elif repack(pretty) == original:
        profile = "indent2"
    else:
        profile = "unknown"
        # Comprobar si conservar SOLO la sangría por línea explica la diferencia.
        original_lines = plain.split(b"\n")
        pretty_lines = pretty.split(b"\n")
        if len(original_lines) == len(pretty_lines):
            lines = []
            for before, after in zip(original_lines, pretty_lines, strict=True):
                width = len(before) - len(before.lstrip(b" "))
                lines.append(b" " * width + after.lstrip(b" "))
            if repack(b"\n".join(lines)) == original:
                profile = "original_line_indent"
    return {"kind": kind, "bytes": len(original), "json_bytes": len(plain),
            "root_fields": len(tree), "inventory_match": True, "original_roundtrip": True,
            "serialization": profile}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cipher-env", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    cipher = Settings(_env_file=args.cipher_env).save_cipher
    if cipher is None:
        parser.error("Falta el códec local.")
    inventory = args.inventory.read_text().splitlines()
    for path in args.files:
        print(json.dumps(check(path, cipher, inventory)))
