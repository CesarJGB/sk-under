from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from .settings import AccessMode

type EditableValue = StrictInt | StrictStr


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    access_mode: AccessMode
    max_file_bytes: int


class FormatInfo(BaseModel):
    id: str
    name: str
    version: str
    extensions: list[str]
    compatibility: Literal["synthetic", "confirmed"]
    description: str


class Formats(BaseModel):
    formats: list[FormatInfo]


class FieldInfo(BaseModel):
    id: str
    label: str
    category: str
    editable: bool


class TextField(FieldInfo):
    type: Literal["string"] = "string"
    value: str
    min_length: int
    max_length: int


class IntegerField(FieldInfo):
    type: Literal["integer"] = "integer"
    value: int
    minimum: int
    maximum: int


type EditorField = Annotated[TextField | IntegerField, Field(discriminator="type")]


class InspectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_base64: StrictStr = Field(
        description="Archivo original completo, en Base64 estándar."
    )


class EditInput(InspectInput):
    changes: dict[str, EditableValue] = Field(
        max_length=32,
        description="Nuevos valores por ID de campo editable. Usa {} para conservar los valores.",
    )


class Inspection(BaseModel):
    format: FormatInfo
    byte_size: int
    sha256: str
    fields: list[EditorField]


class AppliedChange(BaseModel):
    field_id: str
    original: EditableValue
    modified: EditableValue


class Validation(BaseModel):
    valid: Literal[True] = True
    changes: list[AppliedChange]
    output_byte_size: int
    output_sha256: str


class Issue(BaseModel):
    code: str
    message: str
    field_id: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    issues: list[Issue] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail
