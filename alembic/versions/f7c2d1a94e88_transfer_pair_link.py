"""enlace exacto entre las dos patas de un traspaso

Hasta ahora las dos filas de un traspaso solo se relacionaban por
transfer_account_id (que apunta a la CUENTA contraria, no al movimiento).
Con varios traspasos del mismo importe entre las mismas dos cuentas no habia
forma fiable de saber cual era la pareja de cual. Se anade
transfer_transaction_id, que apunta al movimiento concreto, y se rellena para
los traspasos ya existentes emparejando por cuenta + importe opuesto + fecha
mas cercana.

Revision ID: f7c2d1a94e88
Revises: e51c7a9b4d20
Create Date: 2026-07-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7c2d1a94e88'
down_revision: Union[str, None] = 'e51c7a9b4d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transaction') as batch_op:
        batch_op.add_column(sa.Column('transfer_transaction_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_transaction_transfer_transaction_id', 'transaction', ['transfer_transaction_id'], ['id']
        )
    op.create_index(
        'ix_transaction_transfer_transaction_id', 'transaction', ['transfer_transaction_id']
    )

    bind = op.get_bind()
    legs = bind.execute(
        sa.text(
            'SELECT id, date, amount_cents, account_id, transfer_account_id '
            'FROM "transaction" '
            "WHERE transaction_type = 'transfer' AND transfer_account_id IS NOT NULL "
            'ORDER BY id'
        )
    ).fetchall()

    paired: set[int] = set()
    for leg in legs:
        if leg.id in paired:
            continue
        # Pareja: misma pareja de cuentas al reves, importe opuesto y aun sin emparejar.
        candidates = bind.execute(
            sa.text(
                'SELECT id, date FROM "transaction" '
                "WHERE transaction_type = 'transfer' "
                'AND account_id = :other_account AND transfer_account_id = :orig_account '
                'AND amount_cents = :opposite_amount '
                'AND transfer_transaction_id IS NULL AND id != :leg_id'
            ),
            {
                "other_account": leg.transfer_account_id,
                "orig_account": leg.account_id,
                "opposite_amount": -leg.amount_cents,
                "leg_id": leg.id,
            },
        ).fetchall()
        candidates = [c for c in candidates if c.id not in paired]
        if not candidates:
            continue

        # La fecha llega como str en SQLite; ordenar como texto ISO equivale a ordenar por fecha.
        match = min(candidates, key=lambda c: abs(_days_apart(str(c.date), str(leg.date))))
        for a, b in ((leg.id, match.id), (match.id, leg.id)):
            bind.execute(
                sa.text('UPDATE "transaction" SET transfer_transaction_id = :b WHERE id = :a'),
                {"a": a, "b": b},
            )
        paired.update({leg.id, match.id})


def _days_apart(a: str, b: str) -> int:
    from datetime import date

    def parse(s: str) -> date:
        return date.fromisoformat(s[:10])

    return (parse(a) - parse(b)).days


def downgrade() -> None:
    op.drop_index('ix_transaction_transfer_transaction_id', table_name='transaction')
    with op.batch_alter_table('transaction') as batch_op:
        batch_op.drop_constraint('fk_transaction_transfer_transaction_id', type_='foreignkey')
        batch_op.drop_column('transfer_transaction_id')
