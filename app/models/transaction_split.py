from typing import Optional

from sqlmodel import Field, SQLModel


class TransactionSplit(SQLModel, table=True):
    """Parte de un movimiento asignada a una categoría distinta de la principal.

    La suma de las divisiones debe ser <= |importe| del movimiento; el resto
    no repartido se contabiliza en la categoría principal del movimiento.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transaction.id", index=True)
    category_id: int = Field(foreign_key="category.id")
    amount_cents: int = Field(description="Importe positivo (porción del cargo)")
    note: Optional[str] = None
