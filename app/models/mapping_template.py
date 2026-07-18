from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class MappingTemplate(SQLModel, table=True):
    """Plantilla de mapeo de columnas para un banco/formato de exportacion concreto."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    bank_name: Optional[str] = None
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")

    date_column: str
    description_column: str
    amount_column: Optional[str] = Field(default=None, description="Columna de importe con signo")
    debit_column: Optional[str] = Field(default=None, description="Columna de cargos (alternativa a amount)")
    credit_column: Optional[str] = Field(default=None, description="Columna de abonos (alternativa a amount)")
    external_id_column: Optional[str] = None

    date_format: str = Field(default="%d/%m/%Y")
    decimal_separator: str = Field(default=",")
    thousands_separator: str = Field(default=".")
    delimiter: str = Field(default=";")
    encoding: str = Field(default="utf-8")
    header_row: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
