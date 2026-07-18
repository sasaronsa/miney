"""budget date ranges + transaction splits

Revision ID: c9f31e2ab001
Revises: a4083081f4c4
Create Date: 2026-07-18

"""
import calendar
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "c9f31e2ab001"
down_revision: Union[str, None] = "a4083081f4c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transactionsplit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("category.id"), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index("ix_transactionsplit_transaction_id", "transactionsplit", ["transaction_id"])

    op.add_column("budget", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("budget", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("budget", sa.Column("period", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="monthly"))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, year, month FROM budget")).fetchall()
    for id_, year, month in rows:
        last_day = calendar.monthrange(year, month)[1]
        bind.execute(
            sa.text("UPDATE budget SET start_date = :s, end_date = :e WHERE id = :i"),
            {"s": f"{year:04d}-{month:02d}-01", "e": f"{year:04d}-{month:02d}-{last_day:02d}", "i": id_},
        )

    op.drop_index("ix_budget_year", table_name="budget")
    op.drop_index("ix_budget_month", table_name="budget")
    with op.batch_alter_table("budget") as batch_op:
        batch_op.drop_column("year")
        batch_op.drop_column("month")
        batch_op.alter_column("start_date", nullable=False)
    op.create_index("ix_budget_start_date", "budget", ["start_date"])


def downgrade() -> None:
    op.drop_index("ix_budget_start_date", table_name="budget")
    op.add_column("budget", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column("budget", sa.Column("month", sa.Integer(), nullable=True))
    bind = op.get_bind()
    for id_, start in bind.execute(sa.text("SELECT id, start_date FROM budget")).fetchall():
        year, month = int(str(start)[:4]), int(str(start)[5:7])
        bind.execute(sa.text("UPDATE budget SET year = :y, month = :m WHERE id = :i"), {"y": year, "m": month, "i": id_})
    with op.batch_alter_table("budget") as batch_op:
        batch_op.drop_column("start_date")
        batch_op.drop_column("end_date")
        batch_op.drop_column("period")
    op.create_index("ix_budget_year", "budget", ["year"])
    op.create_index("ix_budget_month", "budget", ["month"])
    op.drop_index("ix_transactionsplit_transaction_id", table_name="transactionsplit")
    op.drop_table("transactionsplit")
