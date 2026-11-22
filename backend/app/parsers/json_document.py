import json


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Clave JSON duplicada.")
        result[key] = value
    return result


def reject_non_finite(_: str) -> None:
    raise ValueError("Constante JSON no admitida.")


def parse_json(data: bytes) -> object:
    return json.loads(
        data.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_non_finite,
    )
