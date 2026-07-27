"""Datos de ejemplo para poder probar la app sin subir un extracto real.

Uso: python -m app.seed
"""

import random
from datetime import date

from sqlmodel import Session, select

from app.database import engine
from app.models import Account, Budget, Category, Rule, Transaction
from app.models.enums import AccountType, MatchField, MatchType, TransactionType
from app.services.importing.dedup import compute_content_hash

MERCHANTS_FOOD = ["Mercadona", "Carrefour Express", "Lidl", "Dia"]
MERCHANTS_RESTAURANT = ["Restaurante El Rincon", "Telepizza", "Kebab House"]


def shift_month(d: date, months_back: int) -> date:
    month = d.month - months_back
    year = d.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def run_seed() -> None:
    with Session(engine) as session:
        if session.exec(select(Account)).first():
            print("Ya existen datos: no se vuelve a sembrar.")
            return

        checking = Account(name="Cuenta Corriente", account_type=AccountType.checking, bank="BBVA", initial_balance_cents=250000, color="#2a78d6")
        savings = Account(name="Cuenta Ahorro", account_type=AccountType.savings, bank="BBVA", initial_balance_cents=800000, color="#1baf7a")
        cash = Account(name="Efectivo", account_type=AccountType.cash, initial_balance_cents=5000, color="#eda100")
        session.add_all([checking, savings, cash])
        session.commit()
        for a in (checking, savings, cash):
            session.refresh(a)

        def cat(name: str, parent: Category | None = None, color: str = "#6366f1", icon: str | None = None) -> Category:
            c = Category(name=name, parent_id=parent.id if parent else None, color=color, icon=icon)
            session.add(c)
            session.commit()
            session.refresh(c)
            return c

        alimentacion = cat("Alimentación", color="#1baf7a", icon="🛒")
        supermercado = cat("Supermercado", alimentacion, color="#1baf7a")
        restaurantes = cat("Restaurantes", alimentacion, color="#199e70")

        vivienda = cat("Vivienda", color="#4a3aa7", icon="🏠")
        alquiler = cat("Alquiler/Hipoteca", vivienda, color="#4a3aa7")
        suministros = cat("Suministros", vivienda, color="#9085e9")

        transporte = cat("Transporte", color="#eb6834", icon="🚗")
        ocio = cat("Ocio y suscripciones", color="#e87ba4", icon="🎬")
        salud = cat("Salud", color="#e34948", icon="💊")
        compras = cat("Compras", color="#eda100", icon="🛍️")
        nomina = cat("Nómina", color="#008300", icon="💼")
        transferencias = cat("Transferencias internas", color="#898781")

        session.add_all(
            [
                Rule(name="Mercadona", priority=10, match_field=MatchField.description, match_type=MatchType.contains, pattern="mercadona", category_id=supermercado.id),
                Rule(name="Carrefour", priority=10, match_field=MatchField.description, match_type=MatchType.contains, pattern="carrefour", category_id=supermercado.id),
                Rule(name="Lidl", priority=10, match_field=MatchField.description, match_type=MatchType.contains, pattern="lidl", category_id=supermercado.id),
                Rule(name="Netflix", priority=10, match_field=MatchField.description, match_type=MatchType.contains, pattern="netflix", category_id=ocio.id),
                Rule(name="Spotify", priority=10, match_field=MatchField.description, match_type=MatchType.contains, pattern="spotify", category_id=ocio.id),
                Rule(name="Gasolinera", priority=10, match_field=MatchField.description, match_type=MatchType.contains, pattern="repsol", category_id=transporte.id),
                Rule(name="Nómina", priority=5, match_field=MatchField.description, match_type=MatchType.contains, pattern="nomina", category_id=nomina.id),
            ]
        )
        session.commit()

        random.seed(42)
        today = date.today()

        def add_tx(d: date, amount_eur: float, desc: str, account: Account, category: Category | None, ttype: TransactionType) -> None:
            cents = round(amount_eur * 100)
            session.add(
                Transaction(
                    date=d,
                    amount_cents=cents,
                    description=desc,
                    account_id=account.id,
                    category_id=category.id if category else None,
                    transaction_type=ttype,
                    content_hash=compute_content_hash(account_id=account.id, tx_date=d, amount_cents=cents, description=desc),
                )
            )

        for months_ago in range(6, -1, -1):
            month_start = shift_month(today, months_ago)
            year, month = month_start.year, month_start.month

            add_tx(date(year, month, 28), 1850.00, "Nomina Empresa SL", checking, nomina, TransactionType.income)
            add_tx(date(year, month, 1), -750.00, "Alquiler piso", checking, alquiler, TransactionType.expense)
            add_tx(date(year, month, 5), -round(random.uniform(45, 90), 2), "Endesa Luz", checking, suministros, TransactionType.expense)
            add_tx(date(year, month, 6), -round(random.uniform(20, 35), 2), "Movistar Fibra", checking, suministros, TransactionType.expense)

            for _ in range(6):
                day = random.randint(2, 27)
                add_tx(date(year, month, day), -round(random.uniform(15, 70), 2), random.choice(MERCHANTS_FOOD), checking, supermercado, TransactionType.expense)

            for _ in range(3):
                day = random.randint(2, 27)
                add_tx(date(year, month, day), -round(random.uniform(12, 45), 2), random.choice(MERCHANTS_RESTAURANT), checking, restaurantes, TransactionType.expense)

            add_tx(date(year, month, random.randint(3, 25)), -round(random.uniform(35, 60), 2), "Repsol Gasolinera", checking, transporte, TransactionType.expense)
            add_tx(date(year, month, 8), -12.99, "Netflix.com", checking, ocio, TransactionType.expense)
            add_tx(date(year, month, 15), -9.99, "Spotify", checking, ocio, TransactionType.expense)
            add_tx(date(year, month, 20), -29.90, "Gimnasio BasicFit", checking, salud, TransactionType.expense)

            if random.random() > 0.4:
                add_tx(date(year, month, random.randint(1, 27)), -round(random.uniform(20, 150), 2), "Amazon", checking, compras, TransactionType.expense)

            transfer_amount = round(random.uniform(100, 300), 2)
            transfer_day = date(year, month, 27)
            transfer_cents = -round(transfer_amount * 100)
            # Un traspaso se guarda como una fila POR CUENTA (enlazadas por
            # transfer_account_id), asi aparece en el listado de movimientos de
            # las dos, no solo en la de origen.
            session.add(
                Transaction(
                    date=transfer_day,
                    amount_cents=transfer_cents,
                    description="Transferencia a ahorro",
                    account_id=checking.id,
                    transfer_account_id=savings.id,
                    category_id=transferencias.id,
                    transaction_type=TransactionType.transfer,
                    content_hash=compute_content_hash(
                        account_id=checking.id, tx_date=transfer_day, amount_cents=transfer_cents, description="Transferencia a ahorro"
                    ),
                )
            )
            session.add(
                Transaction(
                    date=transfer_day,
                    amount_cents=-transfer_cents,
                    description="Transferencia a ahorro",
                    account_id=savings.id,
                    transfer_account_id=checking.id,
                    category_id=transferencias.id,
                    transaction_type=TransactionType.transfer,
                    content_hash=compute_content_hash(
                        account_id=savings.id, tx_date=transfer_day, amount_cents=-transfer_cents, description="Transferencia a ahorro"
                    ),
                )
            )

        month_start = date(today.year, today.month, 1)
        session.add_all(
            [
                Budget(category_id=supermercado.id, amount_limit_cents=35000, start_date=month_start),
                Budget(category_id=restaurantes.id, amount_limit_cents=15000, start_date=month_start),
                Budget(category_id=ocio.id, amount_limit_cents=5000, start_date=month_start),
            ]
        )

        session.commit()
        print("Datos de ejemplo creados correctamente (3 cuentas, categorías, reglas, ~7 meses de movimientos).")


if __name__ == "__main__":
    run_seed()
