"""Extrae un inventario estructural de global-metadata.dat de Soul Knight 8.8.0.

Requiere haber extraído:
  lib/arm64-v8a/libil2cpp.so
  assets/bin/Data/Managed/Metadata/global-metadata.dat

Dependencias: pyelftools y pycryptodome.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from bisect import bisect_left
from pathlib import Path

from Crypto.Cipher import AES
from elftools.elf.elffile import ELFFile

# Esquema ACE validado contra este APK. La clave/IV proviene del esquema ACE
# documentado para clientes Unity; la validación es la estructura resultante.
ACE_XOR = 0x66
ACE_AES_KEY = b"d96603c0d96603c0"
ACE_IV = bytes.fromhex("02030405060708090a0b0c0d0e0f1011")


def decrypt_metadata(raw: bytes) -> bytes:
    data = bytearray(raw)
    for index in range(8, min(0x1000, len(data))):
        data[index] ^= ACE_XOR
    for offset in range(0x1000, min(0x5000, len(data)), 0x800):
        block = bytes(data[offset : offset + 0x800])
        plain = AES.new(ACE_AES_KEY, AES.MODE_CBC, ACE_IV).decrypt(block)
        data[offset : offset + len(plain)] = plain
    for base in range(0x11000, len(data), 0x10000):
        for index in range(base, min(base + 0x4000, len(data))):
            data[index] ^= ACE_XOR
    struct.pack_into("<II", data, 0, 0xFAB11BAF, 31)
    return bytes(data)


class Binary:
    def __init__(self, path: Path) -> None:
        self._stream = path.open("rb")
        self._elf = ELFFile(self._stream)
        self.data = path.read_bytes()
        self._segments = [
            (segment["p_vaddr"], segment["p_vaddr"] + segment["p_filesz"], segment["p_offset"])
            for segment in self._elf.iter_segments()
            if segment["p_type"] == "PT_LOAD"
        ]
        relocation = self._elf.get_section_by_name(".rela.dyn")
        self._relocations: list[tuple[int, int]] = []
        for offset in range(relocation["sh_offset"], relocation["sh_offset"] + relocation["sh_size"], 24):
            target, info, addend = struct.unpack_from("<QQQ", self.data, offset)
            if info & 0xFFFFFFFF == 0x403:
                self._relocations.append((target, addend))
        self._relocations.sort()
        self._relocation_targets = [item[0] for item in self._relocations]

    def offset(self, virtual: int) -> int:
        for start, end, file_offset in self._segments:
            if start <= virtual < end:
                return file_offset + virtual - start
        raise ValueError(f"dirección fuera de los segmentos: {virtual:#x}")

    def u64(self, virtual: int) -> int:
        return struct.unpack_from("<Q", self.data, self.offset(virtual))[0]

    def relocated(self, virtual: int) -> int:
        raw = self.u64(virtual)
        if raw:
            return raw
        index = bisect_left(self._relocation_targets, virtual)
        if index < len(self._relocations) and self._relocations[index][0] == virtual:
            return self._relocations[index][1]
        return 0

    def pointers_in(self, virtual: int, count: int) -> list[int]:
        start = virtual
        end = virtual + count * 8
        first = bisect_left(self._relocation_targets, start)
        last = bisect_left(self._relocation_targets, end)
        return [addend for _, addend in self._relocations[first:last]]


class Metadata:
    PRIMITIVES = {
        1: "void",
        2: "bool",
        3: "char",
        4: "sbyte",
        5: "byte",
        6: "short",
        7: "ushort",
        8: "int",
        9: "uint",
        10: "long",
        11: "ulong",
        12: "float",
        13: "double",
        14: "string",
        15: "ptr",
        16: "byref",
        19: "var",
        20: "array",
        21: "generic",
        22: "typedbyref",
        24: "intptr",
        25: "uintptr",
        27: "fnptr",
        28: "object",
        29: "szarray",
        30: "mvar",
    }

    def __init__(self, metadata: bytes, binary: Binary) -> None:
        self.data = metadata
        self.binary = binary
        self._header = tuple(
            struct.unpack_from("<II", metadata, 8 + index * 8) for index in range(31)
        )
        self.strings = self._header[2][0]
        self.string_literals = self._header[0]
        self.methods = self._header[5]
        self.fields = self._header[11]
        self.properties = self._header[4]
        self.types = self._header[19]
        self.images = self._header[20]
        self.assemblies = self._header[21]
        registration = 0xF839CD8
        self.type_count = binary.relocated(registration + 0x30)
        self.type_pointers = binary.relocated(registration + 0x38)
        self._type_indices = {
            pointer: index
            for index, pointer in enumerate(
                binary.pointers_in(self.type_pointers, self.type_count)
            )
        }
        self._type_by_pointer = {
            pointer: binary.offset(pointer) for pointer in self._type_indices
        }

    def string(self, offset: int) -> str:
        end = self.data.find(b"\0", offset)
        return self.data[offset:end].decode("utf-8", "replace")

    def type_definition(self, index: int):
        return struct.unpack_from("<7I I 8I 8H I I", self.data, self.types[0] + index * 88)

    def field(self, index: int):
        return struct.unpack_from("<IiI", self.data, self.fields[0] + index * 12)

    def method(self, index: int):
        return struct.unpack_from("<7I 4H", self.data, self.methods[0] + index * 36)

    def type_name(self, type_index: int, depth: int = 0) -> str:
        if not 0 <= type_index < self.type_count:
            return f"?{type_index}"
        pointer = self.binary.relocated(self.type_pointers + type_index * 8)
        if not pointer:
            return f"?{type_index}"
        return self.type_name_at(pointer, depth)

    def type_name_at(self, pointer: int, depth: int = 0) -> str:
        if depth > 6:
            return "..."
        raw = self.binary.offset(pointer)
        # Il2CppType vive en libil2cpp.so, no en el archivo de metadatos.
        datapoint, bits = struct.unpack_from("<QI", self.binary.data, raw)
        kind = (bits >> 16) & 0xFF
        if kind in self.PRIMITIVES:
            return self.PRIMITIVES[kind]
        if kind in (17, 18):
            try:
                definition = self.type_definition(datapoint)
                return (self.string(self.strings + definition[1]) + "." + self.string(self.strings + definition[0])).lstrip(".")
            except Exception:
                return f"type{datapoint}"
        if kind == 29:
            return self.type_name_at(datapoint, depth + 1) + "[]"
        if kind == 20:
            element = struct.unpack_from("<Q", self.binary.data, self.binary.offset(datapoint))[0]
            return self.type_name_at(element, depth + 1) + "[,]"
        if kind == 21:
            raw = self.binary.offset(datapoint)
            definition_index, class_inst = struct.unpack_from("<IQ", self.binary.data, raw)
            arguments: list[str] = []
            if class_inst:
                instance = self.binary.offset(class_inst)
                count, argv = struct.unpack_from("<IQ", self.binary.data, instance)
                for position in range(min(count, 8)):
                    argument = struct.unpack_from("<Q", self.binary.data, self.binary.offset(argv + position * 8))[0]
                    arguments.append(self.type_name_at(argument, depth + 1))
            try:
                definition = self.type_definition(definition_index)
                base = (self.string(self.strings + definition[1]) + "." + self.string(self.strings + definition[0])).lstrip(".")
            except Exception:
                base = f"type{definition_index}"
            return f"{base}<{', '.join(arguments)}>"
        return f"{self.PRIMITIVES.get(kind, kind)}({datapoint})"

    def describe(self, index: int) -> dict[str, object]:
        definition = self.type_definition(index)
        full_name = (self.string(self.strings + definition[1]) + "." + self.string(self.strings + definition[0])).lstrip(".")
        fields = []
        for position in range(definition[8], definition[8] + definition[18]):
            name, type_index, token = self.field(position)
            fields.append(
                {
                    "name": self.string(self.strings + name),
                    "type": self.type_name(type_index),
                    "token": f"0x{token:08x}",
                }
            )
        methods = []
        for position in range(definition[9], definition[9] + definition[16]):
            name, _, return_type, _, parameter_start, _, token, flags, _, slot, parameter_count = self.method(position)
            methods.append(
                {
                    "name": self.string(self.strings + name),
                    "return": self.type_name(return_type),
                    "parameters": parameter_count,
                    "parameter_start": parameter_start,
                    "slot": slot,
                    "flags": f"0x{flags:04x}",
                    "token": f"0x{token:08x}",
                }
            )
        return {
            "index": index,
            "name": full_name,
            "fields": fields,
            "methods": methods,
            "token": f"0x{definition[25]:08x}",
        }

    def find_types(self, needle: str) -> list[int]:
        matches = []
        for index in range(self.types[1] // 88):
            definition = self.type_definition(index)
            name = self.string(self.strings + definition[0])
            namespace = self.string(self.strings + definition[1])
            if needle.lower() in (namespace + "." + name).lower():
                matches.append(index)
        return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("libil2cpp", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--types", default="CloudSaveGameData,ItemData,StatisticData,TaskData,SeasonData,WeaponEvolutionData,MiscData,PvpData,BattlePassSaveData,EscapeSeasonData,MallReloadData,MonsterRiseData,SettingData,GameData")
    parser.add_argument("--fields-only", action="store_true", help="Omite las firmas de métodos.")
    args = parser.parse_args()

    decrypted = decrypt_metadata(args.metadata.read_bytes())
    binary = Binary(args.libil2cpp)
    metadata = Metadata(decrypted, binary)
    wanted = [item.strip() for item in args.types.split(",") if item.strip()]
    selected = {}
    for needle in wanted:
        for index in metadata.find_types(needle):
            if index not in selected:
                description = metadata.describe(index)
                if args.fields_only:
                    description.pop("methods", None)
                selected[index] = description
    output = {
        "metadata_magic": "0xFAB11BAF",
        "metadata_version": 31,
        "type_count": metadata.type_count,
        "types": [selected[index] for index in sorted(selected)],
    }
    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
