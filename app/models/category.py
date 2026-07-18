from typing import Optional

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id")
    color: str = Field(default="#6366f1")
    icon: Optional[str] = Field(default=None, description="Emoji o nombre de icono corto")
    is_active: bool = Field(default=True)
