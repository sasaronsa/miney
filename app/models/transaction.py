import datetime as dt
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import ImportSource, TransactionType

if TYPE_CHECKING:
    from app.models.account import Account


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    amount_cents: int = Field(description="Negativo = gasto/salida, positivo = ingreso/entrada")
    description: str = Field(index=True)
    notes: Optional[str] = None

    account_id: int = Field(foreign_key="account.id", index=True)
    transfer_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    category_id: Optional[int] = Field(default=None, foreign_key="category.id", index=True)

    transaction_type: TransactionType = Field(default=TransactionType.expense, index=True)

    external_id: Optional[str] = Field(default=None, index=True)
    content_hash: str = Field(index=True, description="sha256(fecha+importe+descripcion normalizada+cuenta)")

    source: ImportSource = Field(default=ImportSource.manual)
    import_batch_id: Optional[int] = Field(default=None, foreign_key="importbatch.id", index=True)

    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

    account: Optional["Account"] = Relationship(
        back_populates="transactions",
        sa_relationship_kwargs={"foreign_keys": "Transaction.account_id"},
    )
