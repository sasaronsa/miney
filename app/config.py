import base64
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/miney.db"
    data_dir: str = "./data"

    # Si no se define, se genera una aleatoria y se persiste en <data_dir>/secret_key
    secret_key: str = ""

    app_username: str = "admin"
    # Opción simple: contraseña en claro; se hashea con bcrypt al arrancar.
    app_password: str = ""
    # Opción avanzada (tiene prioridad): hash bcrypt en base64 generado con
    # `python -m app.cli set-password`. En base64 porque Docker Compose corrompe
    # el "$" de un hash bcrypt al interpolar variables.
    app_password_hash_b64: str = ""

    app_name: str = "Miney"
    default_currency: str = "EUR"
    upload_dir: str = "./data/uploads"

    @property
    def app_password_hash(self) -> str:
        if not self.app_password_hash_b64:
            return ""
        return base64.b64decode(self.app_password_hash_b64.encode()).decode()


def _load_or_create_secret_key(data_dir: Path) -> str:
    secret_file = data_dir / "secret_key"
    if secret_file.exists():
        return secret_file.read_text().strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    secret_file.write_text(key)
    return key


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if not settings.secret_key:
        settings.secret_key = _load_or_create_secret_key(Path(settings.data_dir))

    if not settings.app_password_hash_b64 and settings.app_password:
        from app.security import hash_password

        raw_hash = hash_password(settings.app_password)
        settings.app_password_hash_b64 = base64.b64encode(raw_hash.encode()).decode()

    return settings
