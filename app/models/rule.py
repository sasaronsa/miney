from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import MatchField, MatchType


class Rule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    priority: int = Field(default=100, description="Menor valor = se evalua antes")
    match_field: MatchField = Field(default=MatchField.description)
    match_type: MatchType = Field(default=MatchType.contains)
    pattern: str = Field(description="Texto, regex o rango (min,max para amount) a buscar")
    category_id: int = Field(foreign_key="category.id")
    is_active: bool = Field(default=True)
