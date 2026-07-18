import datetime as dt
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import BudgetPeriod


class Budget(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    amount_limit_cents: int
    period: BudgetPeriod = Field(default=BudgetPeriod.monthly)
    start_date: dt.date = Field(index=True)
    end_date: Optional[dt.date] = Field(default=None, description="Vacia = indefinido")
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
