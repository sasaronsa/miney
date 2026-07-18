import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import SubscriptionFrequency


class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    website: Optional[str] = Field(default=None, description="URL del servicio, ej: https://netflix.com")
    match_pattern: str = Field(
        description="Texto (en minúsculas) que aparece en la descripción del cargo para vincular movimientos"
    )
    frequency: SubscriptionFrequency = Field(default=SubscriptionFrequency.monthly)
    expected_amount_cents: Optional[int] = Field(default=None, description="Precio esperado por cargo")

    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")

    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = Field(default=None, description="Fecha de baja; vacía = activa")
    notes: Optional[str] = None

    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
