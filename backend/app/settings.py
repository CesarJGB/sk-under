from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
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

    @field_validator("access_token", mode="before")
    @classmethod
    def validate_token(cls, value: str | SecretStr | None) -> str | None:
        token = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not token:
            return None
        if len(token) < 32 or not all(char.isascii() and 33 <= ord(char) <= 126 for char in token):
            raise ValueError("SK_ACCESS_TOKEN debe tener al menos 32 caracteres ASCII visibles.")
        return token

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

    @property
    def access_mode(self) -> AccessMode:
        if self.access_token:
            return "token"
        return "local" if self.env == "development" else "disabled"
