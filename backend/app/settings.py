import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

type AccessMode = Literal["local", "token", "disabled"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SK_",
        env_file=("../.env", ".env"),
        extra="ignore",
        hide_input_in_errors=True,
    )

    env: Literal["development", "production"] = "production"
    access_token: SecretStr | None = None
    allowed_origins: list[str] = Field(default_factory=list)
    max_file_bytes: int = Field(default=1_048_576, ge=1, le=8_388_608)

    save_general_key_hex: SecretStr | None = None
    save_statistics_key_hex: SecretStr | None = None
    save_iv_hex: SecretStr | None = None

    # Laboratorio de nube. Todo permanece deshabilitado por defecto.
    cloud_session_token: SecretStr | None = None
    cloud_unique_id: SecretStr | None = None
    cloud_distro_id: SecretStr | None = None
    cloud_admin_token: SecretStr | None = None
    cloud_write_enabled: bool = False
    cloud_accounts_key: SecretStr | None = None
    cloud_accounts_origin: str = ""
    cloud_accounts_dir: Path | None = None
    cloud_backup_dir: Path = Field(
        default_factory=lambda: Path.home() / ".local" / "share" / "sk-under" / "backups"
    )

    # Autenticación nativa (Fase 6.8). Deshabilitada por defecto.
    native_auth_enabled: bool = False
    native_write_enabled: bool = False
    native_store_key: SecretStr | None = None
    native_store_dir: Path | None = None
    native_backup_dir: Path | None = None
    native_origin: str = ""
    native_distro_id: SecretStr | None = None
    native_unique_id: SecretStr | None = None
    native_profile_label: str = "Instalación Android Global"
    native_profile_allow_write: bool = False
    native_idle_seconds: int = Field(default=1800, ge=60, le=86400)
    native_absolute_seconds: int = Field(default=7 * 86400, ge=3600, le=30 * 86400)
    native_login_attempts: int = Field(default=5, ge=1, le=50)
    native_login_window_seconds: int = Field(default=900, ge=60, le=86400)

    @field_validator("save_general_key_hex", "save_statistics_key_hex", "save_iv_hex", mode="before")
    @classmethod
    def validate_save_hex(cls, value: object) -> SecretStr | None:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if secret is None or secret == "":
            return None
        if not isinstance(secret, str) or not re.fullmatch(r"[0-9a-fA-F]{16}", secret):
            raise ValueError("Las claves y el IV de guardados requieren 16 dígitos hexadecimales cada uno.")
        return SecretStr(secret)

    @model_validator(mode="after")
    def validate_save_config(self) -> "Settings":
        values = (self.save_general_key_hex, self.save_statistics_key_hex, self.save_iv_hex)
        if any(values) and not all(values):
            raise ValueError("Configura las dos claves y el IV de guardados juntos.")
        return self

    @property
    def save_cipher(self) -> tuple[bytes, bytes, bytes] | None:
        general = self.save_general_key_hex
        statistics = self.save_statistics_key_hex
        iv = self.save_iv_hex
        if general and statistics and iv:
            return (
                bytes.fromhex(general.get_secret_value()),
                bytes.fromhex(statistics.get_secret_value()),
                bytes.fromhex(iv.get_secret_value()),
            )
        return None

    @field_validator("cloud_session_token", "cloud_unique_id", "cloud_distro_id", mode="before")
    @classmethod
    def validate_cloud_credential(cls, value: object) -> SecretStr | None:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if secret is None or secret == "":
            return None
        if not isinstance(secret, str) or not all(33 <= ord(char) <= 126 for char in secret):
            raise ValueError("Las credenciales de nube deben ser texto ASCII visible sin espacios.")
        return SecretStr(secret)

    @field_validator("cloud_admin_token", mode="before")
    @classmethod
    def validate_cloud_admin_token(cls, value: object) -> SecretStr | None:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if secret is None or secret == "":
            return None
        if (
            not isinstance(secret, str)
            or len(secret) < 32
            or not all(char.isascii() and 33 <= ord(char) <= 126 for char in secret)
        ):
            raise ValueError("SK_CLOUD_ADMIN_TOKEN debe tener al menos 32 caracteres ASCII visibles.")
        return SecretStr(secret)

    @field_validator("access_token", mode="before")
    @classmethod
    def validate_token(cls, value: str | SecretStr | None) -> str | None:
        token = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not token:
            return None
        if len(token) < 32 or not all(char.isascii() and 33 <= ord(char) <= 126 for char in token):
            raise ValueError("SK_ACCESS_TOKEN debe tener al menos 32 caracteres ASCII visibles.")
        return token

    @field_validator("cloud_backup_dir", mode="before")
    @classmethod
    def validate_cloud_backup_dir(cls, value: object) -> Path:
        if value is None or value == "":
            return Path.home() / ".local" / "share" / "sk-under" / "backups"
        if not isinstance(value, (str, Path)):
            raise ValueError("SK_CLOUD_BACKUP_DIR debe ser una ruta.")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("SK_CLOUD_BACKUP_DIR debe ser una ruta absoluta.")
        return path

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        for origin in values:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
                or origin != f"{parsed.scheme}://{parsed.netloc}"
            ):
                raise ValueError("Usa orígenes CORS exactos con esquema y sin ruta ni comodines.")
            _ = parsed.port
        return values

    @field_validator("native_store_key", mode="before")
    @classmethod
    def validate_native_store_key(cls, value: object) -> SecretStr | None:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if secret is None or secret == "":
            return None
        if not isinstance(secret, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", secret):
            raise ValueError("SK_NATIVE_STORE_KEY requiere 32 bytes aleatorios en 64 dígitos hexadecimales.")
        return SecretStr(secret)

    @field_validator("native_distro_id", "native_unique_id", mode="before")
    @classmethod
    def validate_native_identifier(cls, value: object) -> SecretStr | None:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if secret is None or secret == "":
            return None
        if (
            not isinstance(secret, str)
            or len(secret) > 512
            or not all(33 <= ord(char) <= 126 for char in secret)
        ):
            raise ValueError("Los identificadores nativos deben ser texto ASCII visible sin espacios.")
        return SecretStr(secret)

    @field_validator("native_distro_id", mode="before")
    @classmethod
    def validate_native_distro(cls, value: object) -> SecretStr | None:
        secret = value.get_secret_value() if isinstance(value, SecretStr) else value
        if secret is None or secret == "":
            return None
        if not isinstance(secret, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", secret):
            raise ValueError("SK_NATIVE_DISTRO_ID no tiene el formato observado para una distribución.")
        return SecretStr(secret)

    @field_validator("native_store_dir", "native_backup_dir", mode="before")
    @classmethod
    def validate_native_dir(cls, value: object) -> Path | None:
        if value is None or value == "":
            return None
        if not isinstance(value, (str, Path)):
            raise ValueError("La ruta del almacén nativo debe ser un directorio.")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("La ruta del almacén nativo debe ser absoluta.")
        return path

    @field_validator("native_origin")
    @classmethod
    def validate_native_origin(cls, value: str) -> str:
        if value == "":
            return value
        return cls.validate_origins([value])[0]

    @field_validator("native_profile_label")
    @classmethod
    def validate_native_label(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 80 or not value.isprintable():
            raise ValueError("SK_NATIVE_PROFILE_LABEL debe tener entre 1 y 80 caracteres visibles.")
        return value

    @model_validator(mode="after")
    def validate_native_config(self) -> "Settings":
        if self.native_unique_id is not None and self.native_distro_id is None:
            raise ValueError("SK_NATIVE_UNIQUE_ID requiere SK_NATIVE_DISTRO_ID.")
        return self

    @property
    def access_mode(self) -> AccessMode:
        if self.access_token:
            return "token"
        return "local" if self.env == "development" else "disabled"

    @property
    def cloud_configured(self) -> bool:
        return bool(self.cloud_session_token and self.cloud_unique_id and self.cloud_distro_id)

    @property
    def cloud_admin_configured(self) -> bool:
        return self.cloud_admin_token is not None

    @property
    def cloud_write_ready(self) -> bool:
        return self.cloud_write_enabled and self.cloud_configured and self.cloud_admin_configured

    @property
    def native_store_path(self) -> Path:
        return self.native_store_dir or Path.home() / ".local" / "share" / "sk-under" / "native"

    @property
    def native_backup_path(self) -> Path:
        return self.native_backup_dir or Path.home() / ".local" / "share" / "sk-under" / "native-backups"

    @property
    def native_configured(self) -> bool:
        return self.native_auth_enabled and self.native_store_key is not None
