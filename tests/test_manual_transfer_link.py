"""Vincular a mano dos movimientos ya existentes como las dos patas de un traspaso.

Cubre el caso que la deteccion automatica de la importacion no pilla (fechas
separadas, importes con comision, ficheros importados en momentos distintos).
"""

from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Account, Transaction
from app.models.enums import TransactionType
from app.services import stats, transfers


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def accounts(session):
    origin = Account(name="Ibercaja", initial_balance_cents=100000)
    destination = Account(name="Revolut", initial_balance_cents=50000)
    session.add(origin)
    session.add(destination)
    session.commit()
    session.refresh(origin)
    session.refresh(destination)
    return origin, destination


def _tx(session, *, account_id, amount_cents, tx_date, description="Traspaso"):
    tx = Transaction(
        date=tx_date,
        amount_cents=amount_cents,
        description=description,
        account_id=account_id,
        transaction_type=(
            TransactionType.expense if amount_cents < 0 else TransactionType.income
        ),
        content_hash=f"{account_id}-{amount_cents}-{tx_date}-{description}",
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_linking_removes_both_legs_from_cashflow(session, accounts):
    origin, destination = accounts
    salida = _tx(session, account_id=origin.id, amount_cents=-20000, tx_date=date(2026, 3, 1))
    entrada = _tx(session, account_id=destination.id, amount_cents=20000, tx_date=date(2026, 3, 4))

    # Antes de vincular cuentan como gasto e ingreso reales.
    assert stats.monthly_cashflow(session, months=1) != []

    transfers.link(session, salida, entrada)
    session.commit()

    assert salida.transaction_type == TransactionType.transfer
    assert entrada.transaction_type == TransactionType.transfer
    assert salida.transfer_transaction_id == entrada.id
    assert entrada.transfer_transaction_id == salida.id
    assert salida.transfer_account_id == destination.id
    assert entrada.transfer_account_id == origin.id

    assert stats.monthly_cashflow(session, months=1) == []
    # El dinero sigue habiendo salido de una cuenta y entrado en la otra.
    assert stats.current_balance(session, origin) == 100000 - 20000
    assert stats.current_balance(session, destination) == 50000 + 20000
    assert stats.total_current_balance(session) == 100000 + 50000


def test_unlinking_restores_expense_and_income(session, accounts):
    origin, destination = accounts
    salida = _tx(session, account_id=origin.id, amount_cents=-20000, tx_date=date(2026, 3, 1))
    entrada = _tx(session, account_id=destination.id, amount_cents=20000, tx_date=date(2026, 3, 4))

    transfers.link(session, salida, entrada)
    session.commit()

    # Deshacer desde una pata debe soltar tambien la otra.
    transfers.unlink(session, salida)
    session.commit()

    for leg in (salida, entrada):
        assert leg.transfer_transaction_id is None
        assert leg.transfer_account_id is None
    assert salida.transaction_type == TransactionType.expense
    assert entrada.transaction_type == TransactionType.income


def test_candidates_only_offers_opposite_sign_from_other_accounts(session, accounts):
    origin, destination = accounts
    salida = _tx(session, account_id=origin.id, amount_cents=-20000, tx_date=date(2026, 3, 1))

    pareja = _tx(session, account_id=destination.id, amount_cents=20000, tx_date=date(2026, 3, 4))
    _tx(session, account_id=destination.id, amount_cents=-20000, tx_date=date(2026, 3, 4))  # mismo signo
    _tx(session, account_id=origin.id, amount_cents=20000, tx_date=date(2026, 3, 4))  # misma cuenta
    _tx(session, account_id=destination.id, amount_cents=20000, tx_date=date(2026, 5, 1))  # lejos
    _tx(session, account_id=destination.id, amount_cents=90000, tx_date=date(2026, 3, 4))  # otro importe

    assert [c.id for c in transfers.candidates(session, salida)] == [pareja.id]


def test_relinking_releases_the_previous_pair(session, accounts):
    origin, destination = accounts
    salida = _tx(session, account_id=origin.id, amount_cents=-20000, tx_date=date(2026, 3, 1))
    entrada = _tx(session, account_id=destination.id, amount_cents=20000, tx_date=date(2026, 3, 4))
    otra_entrada = _tx(session, account_id=destination.id, amount_cents=20000, tx_date=date(2026, 3, 5))

    transfers.link(session, salida, entrada)
    session.commit()
    transfers.link(session, salida, otra_entrada)
    session.commit()

    assert salida.transfer_transaction_id == otra_entrada.id
    # La pata que se queda suelta vuelve a ser un ingreso normal, no un traspaso huerfano.
    assert entrada.transfer_transaction_id is None
    assert entrada.transaction_type == TransactionType.income
