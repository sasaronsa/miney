from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import AccountType

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    account_type: AccountType = Field(default=AccountType.checking)
    bank: Optional[str] = None
    iban: Optional[str] = None
    initial_balance_cents: int = Field(default=0)
    currency: str = Field(default="EUR")
    color: str = Field(default="#10b981")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    transactions: list["Transaction"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={"foreign_keys": "Transaction.account_id"},
    )
