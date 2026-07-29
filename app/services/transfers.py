"""Vinculación manual de dos movimientos como traspaso entre cuentas propias.

Un traspaso se guarda como DOS filas (una por cuenta) con transaction_type=transfer,
enlazadas entre sí por transfer_transaction_id. Al no ser ni gasto ni ingreso quedan
fuera del cashflow, de los totales por categoría y de los presupuestos, pero siguen
contando en el saldo de cada cuenta.
"""

from typing import Optional

from sqlmodel import Session, select

from app.models import Transaction
from app.models.enums import TransactionType

# Ventana para proponer candidatos. Más amplia que la de la importación automática:
# esto es justo para los casos que el emparejamiento automático no pilló.
CANDIDATE_MAX_DAYS = 20
# Holgura de importe: cubre comisiones o redondeos de cambio de divisa.
CANDIDATE_AMOUNT_TOLERANCE_PCT = 0.02
CANDIDATE_AMOUNT_TOLERANCE_MIN_CENTS = 100


def counterpart(session: Session, tx: Transaction) -> Optional[Transaction]:
    if tx.transfer_transaction_id is None:
        return None
    return session.get(Transaction, tx.transfer_transaction_id)


def candidates(session: Session, tx: Transaction) -> list[Transaction]:
    """Movimientos de otras cuentas que podrían ser la otra pata del traspaso.

    Un traspaso mueve dinero de una cuenta a otra: la contrapartida tiene el signo
    contrario. Se ordenan por importe más parecido y luego por fecha más cercana.
    """
    if tx.amount_cents == 0:
        return []

    tolerance = max(
        CANDIDATE_AMOUNT_TOLERANCE_MIN_CENTS,
        round(abs(tx.amount_cents) * CANDIDATE_AMOUNT_TOLERANCE_PCT),
    )

    others = session.exec(
        select(Transaction).where(
            Transaction.account_id != tx.account_id,
            Transaction.id != tx.id,
            Transaction.transaction_type != TransactionType.transfer,
        )
    ).all()

    scored = []
    for other in others:
        if (other.amount_cents > 0) == (tx.amount_cents > 0):
            continue
        days = abs((other.date - tx.date).days)
        if days > CANDIDATE_MAX_DAYS:
            continue
        diff = abs(abs(other.amount_cents) - abs(tx.amount_cents))
        if diff > tolerance:
            continue
        scored.append((diff, days, other))

    scored.sort(key=lambda row: (row[0], row[1]))
    return [other for _, _, other in scored]


def link(session: Session, a: Transaction, b: Transaction) -> None:
    """Marca los dos movimientos como las dos patas de un mismo traspaso."""
    # Si alguno ya estaba vinculado a un tercero, se suelta primero para no dejarlo huérfano.
    for tx in (a, b):
        old = counterpart(session, tx)
        if old is not None and old.id not in (a.id, b.id):
            _reset(session, old)

    for tx, other in ((a, b), (b, a)):
        tx.transaction_type = TransactionType.transfer
        tx.transfer_account_id = other.account_id
        tx.transfer_transaction_id = other.id
        session.add(tx)


def unlink(session: Session, tx: Transaction) -> None:
    """Deshace el traspaso en las dos patas y devuelve cada una a gasto/ingreso."""
    other = counterpart(session, tx)
    _reset(session, tx)
    if other is not None:
        _reset(session, other)


def _reset(session: Session, tx: Transaction) -> None:
    tx.transaction_type = (
        TransactionType.expense if tx.amount_cents < 0 else TransactionType.income
    )
    tx.transfer_account_id = None
    tx.transfer_transaction_id = None
    session.add(tx)
