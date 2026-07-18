from collections import defaultdict
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app.models import Account, Category, Transaction, TransactionSplit
from app.models.enums import TransactionType
from app.services.importing.dedup import normalize_description


def expense_allocation(
    session: Session, *, date_from: Optional[date] = None, date_to: Optional[date] = None
) -> dict[Optional[int], int]:
    """Gasto por categoría en el rango, repartiendo los movimientos divididos.

    Cada división cuenta en su categoría; la parte no repartida del movimiento
    cuenta en la categoría principal del propio movimiento.
    """
    txs = session.exec(
        select(Transaction).where(Transaction.transaction_type == TransactionType.expense)
    ).all()
    txs = [
        t
        for t in txs
        if (date_from is None or t.date >= date_from) and (date_to is None or t.date <= date_to)
    ]

    splits_by_tx: dict[int, list[TransactionSplit]] = defaultdict(list)
    for s in session.exec(select(TransactionSplit)).all():
        splits_by_tx[s.transaction_id].append(s)

    totals: dict[Optional[int], int] = defaultdict(int)
    for tx in txs:
        total = abs(tx.amount_cents)
        assigned = 0
        for split in splits_by_tx.get(tx.id, []):
            portion = min(max(split.amount_cents, 0), total - assigned)
            if portion <= 0:
                continue
            totals[split.category_id] += portion
            assigned += portion
        if total - assigned > 0:
            totals[tx.category_id] += total - assigned
    return dict(totals)


def total_balance_series(session: Session, *, start: Optional[date] = None) -> list[dict]:
    accounts = session.exec(select(Account)).all()
    running = sum(a.initial_balance_cents for a in accounts)

    txs = session.exec(
        select(Transaction)
        .where(Transaction.transaction_type != TransactionType.transfer)
        .order_by(Transaction.date)
    ).all()

    if start:
        running += sum(t.amount_cents for t in txs if t.date < start)
        txs = [t for t in txs if t.date >= start]

    daily_delta: dict[date, int] = defaultdict(int)
    for tx in txs:
        daily_delta[tx.date] += tx.amount_cents

    series = []
    for d in sorted(daily_delta.keys()):
        running += daily_delta[d]
        series.append({"date": d.isoformat(), "balance_cents": running})
    return series


def account_balance_series(session: Session, account_id: int) -> list[dict]:
    account = session.get(Account, account_id)
    if account is None:
        return []

    own_txs = session.exec(
        select(Transaction).where(Transaction.account_id == account_id).order_by(Transaction.date)
    ).all()
    incoming_transfers = session.exec(
        select(Transaction).where(
            Transaction.transfer_account_id == account_id,
            Transaction.transaction_type == TransactionType.transfer,
        )
    ).all()

    daily_delta: dict[date, int] = defaultdict(int)
    for tx in own_txs:
        daily_delta[tx.date] += tx.amount_cents
    for tx in incoming_transfers:
        daily_delta[tx.date] += -tx.amount_cents

    series = []
    running = account.initial_balance_cents
    for d in sorted(daily_delta.keys()):
        running += daily_delta[d]
        series.append({"date": d.isoformat(), "balance_cents": running})
    return series


def current_balance(session: Session, account: Account) -> int:
    series = account_balance_series(session, account.id)
    if series:
        return series[-1]["balance_cents"]
    return account.initial_balance_cents


def total_current_balance(session: Session) -> int:
    series = total_balance_series(session)
    if series:
        return series[-1]["balance_cents"]
    accounts = session.exec(select(Account)).all()
    return sum(a.initial_balance_cents for a in accounts)


def expenses_by_category(session: Session, *, year: int, month: Optional[int] = None) -> list[dict]:
    import calendar as _calendar

    if month is None:
        date_from, date_to = date(year, 1, 1), date(year, 12, 31)
    else:
        date_from = date(year, month, 1)
        date_to = date(year, month, _calendar.monthrange(year, month)[1])

    categories = {c.id: c for c in session.exec(select(Category)).all()}
    totals = expense_allocation(session, date_from=date_from, date_to=date_to)

    result = []
    for category_id, total_cents in totals.items():
        category = categories.get(category_id)
        result.append(
            {
                "category_id": category_id,
                "category_name": category.name if category else "Sin categorizar",
                "color": category.color if category else "#94a3b8",
                "total_cents": total_cents,
            }
        )
    result.sort(key=lambda r: r["total_cents"], reverse=True)
    return result


def monthly_cashflow(session: Session, *, months: int = 12) -> list[dict]:
    txs = session.exec(
        select(Transaction).where(Transaction.transaction_type != TransactionType.transfer)
    ).all()

    buckets: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {"income_cents": 0, "expense_cents": 0})
    for tx in txs:
        key = (tx.date.year, tx.date.month)
        if tx.transaction_type == TransactionType.income:
            buckets[key]["income_cents"] += tx.amount_cents
        else:
            buckets[key]["expense_cents"] += abs(tx.amount_cents)

    ordered_keys = sorted(buckets.keys())[-months:]
    return [
        {
            "year": y,
            "month": m,
            "label": f"{y}-{m:02d}",
            "income_cents": buckets[(y, m)]["income_cents"],
            "expense_cents": buckets[(y, m)]["expense_cents"],
            "savings_cents": buckets[(y, m)]["income_cents"] - buckets[(y, m)]["expense_cents"],
        }
        for y, m in ordered_keys
    ]


def top_merchants(session: Session, *, year: Optional[int] = None, month: Optional[int] = None, limit: int = 10) -> list[dict]:
    query = select(Transaction).where(Transaction.transaction_type == TransactionType.expense)
    txs = session.exec(query).all()
    if year is not None:
        txs = [t for t in txs if t.date.year == year and (month is None or t.date.month == month)]

    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for tx in txs:
        key = normalize_description(tx.description)
        totals[key] += abs(tx.amount_cents)
        counts[key] += 1

    result = [
        {"description": desc, "total_cents": total, "count": counts[desc]}
        for desc, total in totals.items()
    ]
    result.sort(key=lambda r: r["total_cents"], reverse=True)
    return result[:limit]


def savings_rate(session: Session, *, year: int, month: Optional[int] = None) -> Optional[float]:
    txs = session.exec(
        select(Transaction).where(Transaction.transaction_type != TransactionType.transfer)
    ).all()
    txs = [t for t in txs if t.date.year == year and (month is None or t.date.month == month)]

    income = sum(t.amount_cents for t in txs if t.transaction_type == TransactionType.income)
    expense = sum(abs(t.amount_cents) for t in txs if t.transaction_type == TransactionType.expense)

    if income <= 0:
        return None
    return round((income - expense) / income * 100, 1)


def yearly_totals(session: Session) -> list[dict]:
    txs = session.exec(
        select(Transaction).where(Transaction.transaction_type != TransactionType.transfer)
    ).all()

    buckets: dict[int, dict[str, int]] = defaultdict(lambda: {"income_cents": 0, "expense_cents": 0})
    for tx in txs:
        if tx.transaction_type == TransactionType.income:
            buckets[tx.date.year]["income_cents"] += tx.amount_cents
        else:
            buckets[tx.date.year]["expense_cents"] += abs(tx.amount_cents)

    return [
        {"year": y, "income_cents": v["income_cents"], "expense_cents": v["expense_cents"]}
        for y, v in sorted(buckets.items())
    ]
