from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Account, Category, Transaction, TransactionSplit
from app.models.enums import TransactionType
from app.templating import templates
from app.utils import parse_amount_input

router = APIRouter(prefix="/transactions")

PAGE_SIZE = 50


def _apply_filters(
    query,
    *,
    q: str,
    account_id: str,
    category_id: str,
    transaction_type: str,
    date_from: str,
    date_to: str,
    uncategorized: bool,
):
    if q:
        query = query.where(Transaction.description.contains(q))
    if account_id:
        query = query.where(Transaction.account_id == int(account_id))
    if uncategorized:
        query = query.where(Transaction.category_id.is_(None))
    elif category_id:
        query = query.where(Transaction.category_id == int(category_id))
    if transaction_type:
        query = query.where(Transaction.transaction_type == TransactionType(transaction_type))
    if date_from:
        query = query.where(Transaction.date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(Transaction.date <= date.fromisoformat(date_to))
    return query


@router.get("")
def list_transactions(
    request: Request,
    q: str = "",
    account_id: str = "",
    category_id: str = "",
    transaction_type: str = "",
    date_from: str = "",
    date_to: str = "",
    uncategorized: bool = False,
    page: int = 1,
    session: Session = Depends(get_session),
):
    query = select(Transaction)
    query = _apply_filters(
        query,
        q=q,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        uncategorized=uncategorized,
    )
    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())

    all_matching = session.exec(query).all()
    total = len(all_matching)
    page = max(1, page)
    start = (page - 1) * PAGE_SIZE
    page_items = all_matching[start : start + PAGE_SIZE]

    accounts = session.exec(select(Account)).all()
    categories = session.exec(select(Category)).all()

    return templates.TemplateResponse(
        "transactions/list.html",
        {
            "request": request,
            "transactions": page_items,
            "accounts": accounts,
            "categories": categories,
            "accounts_by_id": {a.id: a for a in accounts},
            "categories_by_id": {c.id: c for c in categories},
            "total": total,
            "page": page,
            "page_size": PAGE_SIZE,
            "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
            "filters": {
                "q": q,
                "account_id": account_id,
                "category_id": category_id,
                "transaction_type": transaction_type,
                "date_from": date_from,
                "date_to": date_to,
                "uncategorized": uncategorized,
            },
        },
    )


@router.get("/review")
def review_uncategorized(request: Request, session: Session = Depends(get_session)):
    transactions = session.exec(
        select(Transaction)
        .where(Transaction.category_id.is_(None))
        .order_by(Transaction.date.desc())
    ).all()
    accounts = {a.id: a for a in session.exec(select(Account)).all()}
    categories = session.exec(select(Category)).all()

    return templates.TemplateResponse(
        "transactions/review.html",
        {
            "request": request,
            "transactions": transactions,
            "accounts_by_id": accounts,
            "categories": categories,
        },
    )


@router.post("/bulk-categorize")
def bulk_categorize(
    category_id: int = Form(...),
    transaction_ids: list[int] = Form(default=[]),
    session: Session = Depends(get_session),
):
    if transaction_ids:
        txs = session.exec(select(Transaction).where(Transaction.id.in_(transaction_ids))).all()
        for tx in txs:
            tx.category_id = category_id
            session.add(tx)
        session.commit()
    return RedirectResponse(url="/transactions/review", status_code=303)


@router.get("/new")
def new_transaction_form(request: Request, session: Session = Depends(get_session)):
    accounts = session.exec(select(Account).where(Account.is_active == True)).all()  # noqa: E712
    categories = session.exec(select(Category)).all()
    return templates.TemplateResponse(
        "transactions/form.html",
        {"request": request, "transaction": None, "accounts": accounts, "categories": categories},
    )


@router.post("/new")
def create_transaction(
    tx_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    account_id: int = Form(...),
    category_id: str = Form(""),
    transaction_type: TransactionType = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    from app.services.importing.dedup import compute_content_hash

    parsed_date = date.fromisoformat(tx_date)
    amount_cents = parse_amount_input(amount)
    if transaction_type == TransactionType.expense:
        amount_cents = -abs(amount_cents)
    elif transaction_type == TransactionType.income:
        amount_cents = abs(amount_cents)

    content_hash = compute_content_hash(
        account_id=account_id, tx_date=parsed_date, amount_cents=amount_cents, description=description
    )

    session.add(
        Transaction(
            date=parsed_date,
            amount_cents=amount_cents,
            description=description,
            notes=notes or None,
            account_id=account_id,
            category_id=int(category_id) if category_id else None,
            transaction_type=transaction_type,
            content_hash=content_hash,
        )
    )
    session.commit()
    return RedirectResponse(url="/transactions", status_code=303)


@router.get("/{transaction_id}/edit")
def edit_transaction_form(transaction_id: int, request: Request, session: Session = Depends(get_session)):
    transaction = session.get(Transaction, transaction_id)
    accounts = session.exec(select(Account)).all()
    categories = session.exec(select(Category)).all()
    splits = []
    if transaction:
        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        ).all()
    splits_data = [
        {"category_id": str(s.category_id), "amount": "%.2f" % (s.amount_cents / 100)} for s in splits
    ]
    return templates.TemplateResponse(
        "transactions/form.html",
        {
            "request": request,
            "transaction": transaction,
            "accounts": accounts,
            "categories": categories,
            "splits_data": splits_data,
        },
    )


@router.post("/{transaction_id}/edit")
def update_transaction(
    transaction_id: int,
    tx_date: str = Form(...),
    description: str = Form(...),
    amount: str = Form(...),
    account_id: int = Form(...),
    category_id: str = Form(""),
    transaction_type: TransactionType = Form(...),
    notes: str = Form(""),
    split_category_id: list[str] = Form(default=[]),
    split_amount: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
):
    transaction = session.get(Transaction, transaction_id)
    if transaction:
        amount_cents = parse_amount_input(amount)
        if transaction_type == TransactionType.expense:
            amount_cents = -abs(amount_cents)
        elif transaction_type == TransactionType.income:
            amount_cents = abs(amount_cents)

        transaction.date = date.fromisoformat(tx_date)
        transaction.description = description
        transaction.amount_cents = amount_cents
        transaction.account_id = account_id
        transaction.category_id = int(category_id) if category_id else None
        transaction.transaction_type = transaction_type
        transaction.notes = notes or None
        session.add(transaction)

        old_splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        ).all()
        for s in old_splits:
            session.delete(s)

        total = abs(amount_cents)
        assigned = 0
        for cat, amt in zip(split_category_id, split_amount):
            if not cat or not amt.strip():
                continue
            cents = abs(parse_amount_input(amt))
            if cents <= 0 or assigned + cents > total:
                continue
            session.add(
                TransactionSplit(transaction_id=transaction_id, category_id=int(cat), amount_cents=cents)
            )
            assigned += cents

        session.commit()
    return RedirectResponse(url="/transactions", status_code=303)


@router.post("/{transaction_id}/delete")
def delete_transaction(transaction_id: int, session: Session = Depends(get_session)):
    transaction = session.get(Transaction, transaction_id)
    if transaction:
        for s in session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        ).all():
            session.delete(s)
        session.delete(transaction)
        session.commit()
    return RedirectResponse(url="/transactions", status_code=303)


@router.post("/{transaction_id}/quick-category")
def quick_set_category(
    transaction_id: int,
    request: Request,
    quick_category_id: str = Form(""),
    session: Session = Depends(get_session),
):
    transaction = session.get(Transaction, transaction_id)
    if transaction:
        transaction.category_id = int(quick_category_id) if quick_category_id else None
        session.add(transaction)
        session.commit()
    categories = session.exec(select(Category)).all()
    return templates.TemplateResponse(
        "partials/category_select.html",
        {"request": request, "transaction": transaction, "categories": categories},
    )
