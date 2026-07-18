import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    """Único usuario de la app. Se crea en el primer arranque (pantalla de registro)
    o automáticamente desde las variables de entorno si están definidas."""

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    password_hash: str = Field(description="Hash bcrypt (en BD no hay problema con los '$')")
    language: str = Field(default="es", description="Código de idioma de la interfaz: es | en")
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
