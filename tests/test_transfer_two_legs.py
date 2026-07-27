"""Un traspaso importado entre dos cuentas propias debe guardarse como DOS filas
(una por cuenta, enlazadas por transfer_account_id) para que aparezca en el
listado de movimientos de ambas cuentas, y el saldo de cada una debe reflejarlo
sin contar el importe dos veces.
"""

from datetime import date

import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Account, Transaction
from app.models.enums import ImportSource, TransactionType
from app.services import stats
from app.services.importing.mapping import ColumnMapping
from app.services.importing.orchestrator import build_preview, insert_transactions


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


def _import_row(session, *, account_id, tx_date, amount_cents, description, mark_as_transfer):
    df = pd.DataFrame({"Fecha": [tx_date.strftime("%d/%m/%Y")], "Concepto": [description], "Importe": [amount_cents / 100]})
    mapping = ColumnMapping(date_column="Fecha", description_column="Concepto", amount_column="Importe")
    preview = build_preview(session, df, mapping, account_id=account_id)
    transfer_indices = {0} if mark_as_transfer else set()
    return insert_transactions(
        session,
        df=df,
        mapping=mapping,
        account_id=account_id,
        filename="test.xlsx",
        source=ImportSource.excel,
        included_row_indices={0},
        total_rows=preview["total_rows"],
        duplicate_rows=preview["duplicate_rows"],
        transfer_row_indices=transfer_indices,
    )


def test_transfer_creates_a_row_in_both_accounts(session, accounts):
    origin, destination = accounts

    # 1) Se importa primero el cargo en Ibercaja, sin marcar transferencia todavia
    #    (aun no hay nada con lo que emparejar en la otra cuenta).
    _import_row(
        session,
        account_id=origin.id,
        tx_date=date(2026, 3, 1),
        amount_cents=-20000,
        description="Transferencia con Revolut",
        mark_as_transfer=False,
    )

    # 2) Se importa el abono correspondiente en Revolut y se marca como traspaso;
    #    el emparejamiento con la fila de Ibercaja debe detectarse automaticamente.
    _import_row(
        session,
        account_id=destination.id,
        tx_date=date(2026, 3, 2),
        amount_cents=20000,
        description="Transferencia con Ibercaja",
        mark_as_transfer=True,
    )

    all_txs = session.exec(select(Transaction)).all()
    assert len(all_txs) == 2, "debe haber una fila por cuenta, ninguna borrada ni omitida"

    by_account = {t.account_id: t for t in all_txs}
    origin_leg = by_account[origin.id]
    dest_leg = by_account[destination.id]

    assert origin_leg.transaction_type == TransactionType.transfer
    assert dest_leg.transaction_type == TransactionType.transfer
    assert origin_leg.amount_cents == -20000
    assert dest_leg.amount_cents == 20000
    assert origin_leg.transfer_account_id == destination.id
    assert dest_leg.transfer_account_id == origin.id


def test_transfer_balances_without_double_counting(session, accounts):
    origin, destination = accounts

    _import_row(
        session,
        account_id=origin.id,
        tx_date=date(2026, 3, 1),
        amount_cents=-20000,
        description="Transferencia con Revolut",
        mark_as_transfer=False,
    )
    _import_row(
        session,
        account_id=destination.id,
        tx_date=date(2026, 3, 2),
        amount_cents=20000,
        description="Transferencia con Ibercaja",
        mark_as_transfer=True,
    )

    assert stats.current_balance(session, origin) == 100000 - 20000
    assert stats.current_balance(session, destination) == 50000 + 20000

    # El total (patrimonio) no debe moverse por un traspaso entre cuentas propias.
    assert stats.total_current_balance(session) == 100000 + 50000


def test_transfer_excluded_from_income_and_expense_stats(session, accounts):
    origin, destination = accounts

    _import_row(
        session,
        account_id=origin.id,
        tx_date=date(2026, 3, 1),
        amount_cents=-20000,
        description="Transferencia con Revolut",
        mark_as_transfer=False,
    )
    _import_row(
        session,
        account_id=destination.id,
        tx_date=date(2026, 3, 2),
        amount_cents=20000,
        description="Transferencia con Ibercaja",
        mark_as_transfer=True,
    )

    # Ambas filas son transaction_type=transfer, asi que no generan ni ingreso ni
    # gasto: no debe aparecer ningun bucket mensual con datos.
    cashflow = stats.monthly_cashflow(session, months=1)
    assert cashflow == []
