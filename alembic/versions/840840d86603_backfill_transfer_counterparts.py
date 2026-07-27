"""backfill transfer counterparts

Hasta ahora un traspaso entre cuentas propias se guardaba como una unica fila
(el lado negativo, con transfer_account_id apuntando al destino) y el saldo de
la cuenta destino se calculaba "en el aire" en account_balance_series a partir
de esa fila ajena. Esto hacia que el traspaso fuera invisible en el listado de
movimientos de la cuenta destino. A partir de ahora se guardan las dos filas
(una por cuenta, ambas transaction_type=transfer, enlazadas por transfer_account_id)
y esta migracion crea la fila que falta para los traspasos ya existentes.

Revision ID: 840840d86603
Revises: 4adf617ccd87
Create Date: 2026-07-27 20:12:37.259194

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '840840d86603'
down_revision: Union[str, None] = '4adf617ccd87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _content_hash(*, account_id: int, tx_date, amount_cents: int, description: str) -> str:
    normalized = " ".join((description or "").strip().lower().split())
    raw = f"{account_id}|{tx_date}|{amount_cents}|{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()

    legs = bind.execute(
        sa.text(
            'SELECT id, date, amount_cents, description, notes, account_id, '
            'transfer_account_id, source '
            'FROM "transaction" '
            "WHERE transaction_type = 'transfer' AND transfer_account_id IS NOT NULL"
        )
    ).fetchall()

    for leg in legs:
        opposite_amount = -leg.amount_cents
        counterpart = bind.execute(
            sa.text(
                'SELECT id FROM "transaction" '
                "WHERE account_id = :other_account AND transfer_account_id = :orig_account "
                "AND amount_cents = :opposite_amount AND transaction_type = 'transfer'"
            ),
            {
                "other_account": leg.transfer_account_id,
                "orig_account": leg.account_id,
                "opposite_amount": opposite_amount,
            },
        ).fetchone()
        if counterpart:
            continue

        content_hash = _content_hash(
            account_id=leg.transfer_account_id,
            tx_date=leg.date,
            amount_cents=opposite_amount,
            description=leg.description,
        )

        bind.execute(
            sa.text(
                'INSERT INTO "transaction" '
                "(date, amount_cents, description, notes, account_id, transfer_account_id, "
                "category_id, transaction_type, external_id, content_hash, source, "
                "import_batch_id, created_at) "
                "VALUES (:date, :amount_cents, :description, :notes, :account_id, "
                ":transfer_account_id, NULL, 'transfer', NULL, :content_hash, :source, "
                "NULL, CURRENT_TIMESTAMP)"
            ),
            {
                "date": leg.date,
                "amount_cents": opposite_amount,
                "description": leg.description,
                "notes": leg.notes,
                "account_id": leg.transfer_account_id,
                "transfer_account_id": leg.account_id,
                "content_hash": content_hash,
                "source": leg.source,
            },
        )


def downgrade() -> None:
    # Backfill de datos: no se revierte (habria que distinguir las filas creadas
    # aqui de traspasos legitimos creados despues por la app con el nuevo modelo
    # de dos filas, y no hay forma fiable de diferenciarlos retroactivamente).
    pass
