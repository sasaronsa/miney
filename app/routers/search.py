from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Account, Category, Subscription, Transaction
from app.templating import templates

router = APIRouter()

MAX_TX_RESULTS = 25


@router.get("/search")
def global_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    q_clean = q.strip()
    results = {
        "transactions": [],
        "tx_total": 0,
        "accounts": [],
        "categories": [],
        "subscriptions": [],
    }

    if len(q_clean) >= 2:
        needle = q_clean.lower()

        all_txs = session.exec(
            select(Transaction)
            .where(Transaction.description.contains(q_clean))
            .order_by(Transaction.date.desc(), Transaction.id.desc())
        ).all()
        results["tx_total"] = len(all_txs)
        results["transactions"] = all_txs[:MAX_TX_RESULTS]

        results["accounts"] = [
            a
            for a in session.exec(select(Account)).all()
            if needle in a.name.lower() or (a.bank and needle in a.bank.lower())
        ]
        results["categories"] = [
            c for c in session.exec(select(Category)).all() if needle in c.name.lower()
        ]
        results["subscriptions"] = [
            s
            for s in session.exec(select(Subscription)).all()
            if needle in s.name.lower() or needle in s.match_pattern.lower()
        ]

    accounts_by_id = {a.id: a for a in session.exec(select(Account)).all()}
    categories_by_id = {c.id: c for c in session.exec(select(Category)).all()}

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "q": q_clean,
            "results": results,
            "accounts_by_id": accounts_by_id,
            "categories_by_id": categories_by_id,
            "max_tx": MAX_TX_RESULTS,
        },
    )
