from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

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
    compatibility: Literal["synthetic", "confirmed", "read_only"]
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


class CloudLabStatus(BaseModel):
    mode: Literal["live", "read_only", "disabled"]
    read_ready: bool
    write_enabled: bool
    write_ready: bool
    admin_configured: bool
    admin_required: bool
    backup_count: int
    min_gems: int
    max_gems: int
    min_fish_chip: int = 0
    max_fish_chip: int = 2_147_483_647
    fish_chip_write_policy: Literal["confirmed_by_owner"] = "confirmed_by_owner"
    character_write_policy: Literal["confirmed_by_owner"] = "confirmed_by_owner"
    skill_write_policy: Literal["confirmed_by_owner"] = "confirmed_by_owner"
    skin_write_policy: Literal["confirmed_by_owner"] = "confirmed_by_owner"
    message: str


class CloudRemoteInfo(BaseModel):
    source: str
    size: int
    sha256: str


class CloudLabSave(BaseModel):
    remote: CloudRemoteInfo
    gems: int
    fish_chip: int | None = None
    fish_chip_path: str | None = None
    material_fish: int | None = None
    material_fish_path: str | None = None
    cumulative_fish_count: int | None = None
    cumulative_fish_count_path: str | None = None
    fish_chip_write_policy: Literal["confirmed_by_owner"] | None = None
    character_write_policy: Literal["confirmed_by_owner"] | None = None
    skill_write_policy: Literal["confirmed_by_owner"] | None = None
    skin_write_policy: Literal["confirmed_by_owner"] | None = None
    size: int
    sha256: str
    serialzed_version: int
    report: dict[str, Any] | None = None


class CloudItemChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: StrictStr = Field(min_length=1, max_length=80)
    value: StrictInt = Field(ge=0, le=2_147_483_647)


class CloudBattlePassChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season_id: StrictInt = Field(ge=0, le=2_147_483_647)
    cur_level: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)
    cur_exp: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)
    has_buy: bool | None = None


class CloudLabAdvancedPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materials: list[CloudItemChange] = Field(default_factory=list, max_length=343)
    seeds: list[CloudItemChange] = Field(default_factory=list, max_length=47)
    season_coin: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)
    reborn_card: StrictBool | None = None
    battle_pass: CloudBattlePassChange | None = None


class CloudBackupSummary(BaseModel):
    id: str
    created_at: str
    field: Literal[
        "gems", "fish_chip", "fish_progress", "characters", "skills", "skins", "advanced"
    ] = "gems"
    changed: bool
    original_size: int
    original_sha256: str
    original_gems: int
    original_value: int | None = None
    candidate_size: int
    candidate_sha256: str
    candidate_gems: int
    candidate_value: int | None = None
    remote_source: str
    remote_size: int
    remote_sha256: str
    character_codes: list[str] = Field(default_factory=list)
    skill_selections: list[dict[str, Any]] = Field(default_factory=list)
    skin_selections: list[dict[str, Any]] = Field(default_factory=list)
    advanced_plan: dict[str, Any] = Field(default_factory=dict)


class CloudByteDiff(BaseModel):
    original_size: int
    modified_size: int
    first_difference: int | None
    common_prefix: int
    common_suffix: int
    changed_original_bytes: int
    changed_modified_bytes: int
    original_sha256: str
    modified_sha256: str


class CloudLabValidation(BaseModel):
    valid: Literal[True] = True
    structure_valid: Literal[True] = True
    only_gems_changed: bool
    message: str


class CloudLabPrepared(BaseModel):
    remote: CloudRemoteInfo
    backup: CloudBackupSummary
    original_gems: int
    new_gems: int
    original_value: int | None = None
    new_value: int | None = None
    field: str | None = None
    changed: bool
    candidate_size: int
    candidate_sha256: str
    byte_diff: CloudByteDiff
    changed_fields: list[str]
    validation: CloudLabValidation


class CloudLabFishChipPrepared(BaseModel):
    remote: CloudRemoteInfo
    backup: CloudBackupSummary
    original_fish_chip: int
    new_fish_chip: int
    original_material_fish: int | None = None
    new_material_fish: int | None = None
    material_fish_path: str | None = None
    original_value: int | None = None
    new_value: int | None = None
    field: str
    experimental: Literal[True] = True
    changed: bool
    candidate_size: int
    candidate_sha256: str
    byte_diff: CloudByteDiff
    changed_fields: list[str]
    validation: dict[str, Any]


class CloudLabFishProgressPrepared(BaseModel):
    remote: CloudRemoteInfo
    backup: CloudBackupSummary
    original_cumulative_fish_count: int
    new_cumulative_fish_count: int
    original_value: int | None = None
    new_value: int | None = None
    field: str
    experimental: Literal[True] = True
    changed: bool
    candidate_size: int
    candidate_sha256: str
    byte_diff: CloudByteDiff
    changed_fields: list[str]
    validation: dict[str, Any]


class CloudLabCharacterPrepared(BaseModel):
    remote: CloudRemoteInfo
    backup: CloudBackupSummary
    original_unlocked_count: int
    new_unlocked_count: int
    total_characters: int
    selected_codes: list[str]
    newly_unlocked_codes: list[str]
    original_value: int | None = None
    new_value: int | None = None
    field: str
    experimental: bool = False
    changed: bool
    candidate_size: int
    candidate_sha256: str
    byte_diff: CloudByteDiff
    changed_fields: list[str]
    validation: dict[str, Any]


class CloudSkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: StrictStr = Field(min_length=1, max_length=80)
    index: StrictInt = Field(ge=0, le=104)


class CloudLabSkillPrepared(BaseModel):
    remote: CloudRemoteInfo
    backup: CloudBackupSummary
    original_unlocked_count: int
    new_unlocked_count: int
    total_skills: int
    selected_skills: list[CloudSkillSelection]
    newly_unlocked_skills: list[CloudSkillSelection]
    affected_codes: list[str]
    original_value: int | None = None
    new_value: int | None = None
    field: str
    experimental: Literal[True] = True
    changed: bool
    candidate_size: int
    candidate_sha256: str
    byte_diff: CloudByteDiff
    changed_fields: list[str]
    validation: dict[str, Any]


class CloudSkinSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: StrictStr = Field(min_length=1, max_length=80)
    index: StrictInt = Field(ge=0, le=801)


class CloudLabSkinPrepared(BaseModel):
    remote: CloudRemoteInfo
    backup: CloudBackupSummary
    original_unlocked_count: int
    new_unlocked_count: int
    total_skins: int
    selected_skins: list[CloudSkinSelection]
    newly_unlocked_skins: list[CloudSkinSelection]
    affected_codes: list[str]
    locked_character_codes: list[str]
    original_value: int | None = None
    new_value: int | None = None
    field: str
    experimental: bool = False
    changed: bool
    candidate_size: int
    candidate_sha256: str
    byte_diff: CloudByteDiff
    changed_fields: list[str]
    validation: dict[str, Any]


class CloudLabPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_gems: StrictInt


class CloudLabFishChipPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_fish_chip: StrictInt


class CloudLabFishProgressPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_cumulative_fish_count: StrictInt


class CloudLabCharacterPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codes: list[StrictStr] = Field(min_length=1, max_length=42)


class CloudLabSkillPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[CloudSkillSelection] = Field(min_length=1, max_length=105)


class CloudLabSkinPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skins: list[CloudSkinSelection] = Field(min_length=1, max_length=802)


class CloudLabConfirmInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backup_id: StrictStr = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")
    expected_sha256: StrictStr = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    confirmation: Literal["SUBIR"]


class CloudLabRestoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backup_id: StrictStr = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")
    confirmation: Literal["RESTAURAR"]


class CloudLabVerifyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backup_id: StrictStr = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")


class CloudLabWriteResult(BaseModel):
    action: Literal["confirm", "restore"]
    backup_id: str
    field: str = "gameData.gems"
    uploaded: bool
    accepted: bool
    persisted: bool
    already_original: bool
    expected_sha256: str
    remote_sha256: str | None
    remote_size: int | None
    remote_gems: int | None
    remote_value: int | None = None
    remote_material_fish: int | None = None
    remote_characters: int | None = None
    remote_skills: int | None = None
    remote_skins: int | None = None
    status: int | None
    message: str


class CloudLabVerification(BaseModel):
    backup_id: str
    field: str = "gameData.gems"
    matches_candidate: bool
    matches_original: bool
    remote_sha256: str
    remote_size: int
    remote_gems: int | None
    remote_value: int | None = None
    remote_material_fish: int | None = None
    remote_characters: int | None = None
    remote_skills: int | None = None
    remote_skins: int | None = None
    expected_candidate_sha256: str
    expected_original_sha256: str
    message: str


class CloudLabBackups(BaseModel):
    backups: list[CloudBackupSummary]
