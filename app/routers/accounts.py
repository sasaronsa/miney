from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Account, Category, Transaction
from app.models.enums import AccountType
from app.services.stats import account_balance_series, current_balance
from app.templating import templates
from app.utils import parse_amount_input

router = APIRouter(prefix="/accounts")


@router.get("")
def list_accounts(request: Request, session: Session = Depends(get_session)):
    accounts = session.exec(select(Account).order_by(Account.name)).all()
    accounts_data = [{"account": a, "balance_cents": current_balance(session, a)} for a in accounts]
    total_cents = sum(row["balance_cents"] for row in accounts_data if row["account"].is_active)
    return templates.TemplateResponse(
        "accounts/list.html",
        {"request": request, "accounts_data": accounts_data, "total_cents": total_cents},
    )


@router.get("/new")
def new_account_form(request: Request):
    return templates.TemplateResponse(
        "accounts/form.html", {"request": request, "account": None, "account_types": list(AccountType)}
    )


@router.post("/new")
def create_account(
    name: str = Form(...),
    account_type: AccountType = Form(...),
    bank: str = Form(""),
    iban: str = Form(""),
    initial_balance: str = Form("0"),
    color: str = Form("#10b981"),
    session: Session = Depends(get_session),
):
    account = Account(
        name=name,
        account_type=account_type,
        bank=bank or None,
        iban=iban or None,
        initial_balance_cents=parse_amount_input(initial_balance),
        color=color,
    )
    session.add(account)
    session.commit()
    return RedirectResponse(url="/accounts", status_code=303)


@router.get("/{account_id}/edit")
def edit_account_form(account_id: int, request: Request, session: Session = Depends(get_session)):
    account = session.get(Account, account_id)
    return templates.TemplateResponse(
        "accounts/form.html", {"request": request, "account": account, "account_types": list(AccountType)}
    )


@router.post("/{account_id}/edit")
def update_account(
    account_id: int,
    name: str = Form(...),
    account_type: AccountType = Form(...),
    bank: str = Form(""),
    iban: str = Form(""),
    initial_balance: str = Form("0"),
    color: str = Form("#10b981"),
    is_active: bool = Form(False),
    session: Session = Depends(get_session),
):
    account = session.get(Account, account_id)
    if account:
        account.name = name
        account.account_type = account_type
        account.bank = bank or None
        account.iban = iban or None
        account.initial_balance_cents = parse_amount_input(initial_balance)
        account.color = color
        account.is_active = is_active
        session.add(account)
        session.commit()
    return RedirectResponse(url="/accounts", status_code=303)


@router.post("/{account_id}/delete")
def delete_account(account_id: int, session: Session = Depends(get_session)):
    account = session.get(Account, account_id)
    if account:
        has_txs = session.exec(
            select(Transaction).where(Transaction.account_id == account_id).limit(1)
        ).first()
        if has_txs:
            account.is_active = False
            session.add(account)
        else:
            session.delete(account)
        session.commit()
    return RedirectResponse(url="/accounts", status_code=303)


@router.get("/{account_id}")
def account_detail(account_id: int, request: Request, session: Session = Depends(get_session)):
    account = session.get(Account, account_id)
    if not account:
        return RedirectResponse(url="/accounts", status_code=303)

    series = account_balance_series(session, account_id)
    recent_txs = session.exec(
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(25)
    ).all()
    categories = session.exec(select(Category)).all()
    accounts = session.exec(select(Account)).all()

    return templates.TemplateResponse(
        "accounts/detail.html",
        {
            "request": request,
            "account": account,
            "series": series,
            "recent_txs": recent_txs,
            "balance_cents": current_balance(session, account),
            "categories_by_id": {c.id: c for c in categories},
            "accounts_by_id": {a.id: a for a in accounts},
        },
    )
