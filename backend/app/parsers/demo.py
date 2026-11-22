from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..errors import EditorError
from ..models import Issue
from .json_document import parse_json

DEMO_SIGNATURE = b"SK-EDITOR-DEMO/1\n"
MIN_SAMPLE = 0
MAX_SAMPLE = 100
MIN_LABEL = 1
MAX_LABEL = 48

FIELD_MESSAGES = {
    "fixture_id": "El identificador de la muestra es inválido.",
    "label": f"La etiqueta debe tener entre {MIN_LABEL} y {MAX_LABEL} caracteres de texto.",
    "sample_count": f"La cantidad debe ser un entero entre {MIN_SAMPLE} y {MAX_SAMPLE}.",
    "sample_limit": f"El límite debe ser un entero entre {MIN_SAMPLE} y {MAX_SAMPLE}.",
}


class DemoDocument(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    fixture_id: str = Field(pattern=r"^[a-z0-9-]{1,40}$")
    label: str = Field(min_length=MIN_LABEL, max_length=MAX_LABEL, pattern=r"^[^\x00-\x1f\x7f]+$")
    sample_count: int = Field(ge=MIN_SAMPLE, le=MAX_SAMPLE)
    sample_limit: int = Field(ge=MIN_SAMPLE, le=MAX_SAMPLE)


def validate_demo(payload: object, *, applying_changes: bool = False) -> DemoDocument:
    code = "invalid_changes" if applying_changes else "malformed_file"
    message = "Revisa los campos de la muestra." if applying_changes else "El archivo de demostración está malformado."
    try:
        document = DemoDocument.model_validate(payload)
    except ValidationError as exc:
        issues = []
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            field = error["loc"][0] if error["loc"] else None
            if isinstance(field, str) and field in FIELD_MESSAGES and error["type"] != "extra_forbidden":
                issues.append(Issue(code="invalid_field", field_id=field, message=FIELD_MESSAGES[field]))
            else:
                issues.append(Issue(code="invalid_document", message="La estructura contiene campos o valores inesperados."))
                break
        raise EditorError(422, code, message, issues) from None
    if document.sample_count > document.sample_limit:
        raise EditorError(
            422, code, message,
            [Issue(code="dependency_failed", field_id="sample_count", message="La cantidad no puede superar el límite.")],
        )
    return document


def read_demo(data: bytes) -> DemoDocument:
    if not data.startswith(DEMO_SIGNATURE):
        raise EditorError(422, "malformed_file", "La firma del archivo de demostración es inválida.")
    try:
        payload = parse_json(data[len(DEMO_SIGNATURE):])
    except (ValueError, RecursionError):
        raise EditorError(422, "malformed_file", "El archivo de demostración contiene JSON inválido.") from None
    return validate_demo(payload)
