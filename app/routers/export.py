import csv
import io
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Account, Category, Transaction
from app.templating import templates

router = APIRouter(prefix="/export")


@router.get("")
def export_page(request: Request):
    return templates.TemplateResponse("export.html", {"request": request})


@router.get("/transactions.csv")
def export_transactions_csv(session: Session = Depends(get_session)):
    accounts = {a.id: a.name for a in session.exec(select(Account)).all()}
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}
    transactions = session.exec(select(Transaction).order_by(Transaction.date)).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["fecha", "descripcion", "importe", "cuenta", "categoria", "tipo", "notas"])
    for t in transactions:
        writer.writerow(
            [
                t.date.isoformat(),
                t.description,
                f"{t.amount_cents / 100:.2f}",
                accounts.get(t.account_id, ""),
                categories.get(t.category_id, ""),
                t.transaction_type.value,
                t.notes or "",
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transacciones.csv"},
    )


@router.get("/transactions.json")
def export_transactions_json(session: Session = Depends(get_session)):
    accounts = {a.id: a.name for a in session.exec(select(Account)).all()}
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}
    transactions = session.exec(select(Transaction).order_by(Transaction.date)).all()

    data = [
        {
            "fecha": t.date.isoformat(),
            "descripcion": t.description,
            "importe": t.amount_cents / 100,
            "cuenta": accounts.get(t.account_id),
            "categoria": categories.get(t.category_id),
            "tipo": t.transaction_type.value,
            "notas": t.notes,
        }
        for t in transactions
    ]

    return StreamingResponse(
        iter([json.dumps(data, ensure_ascii=False, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=transacciones.json"},
    )
