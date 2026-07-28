from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.database import get_session
from app.services import recurring, stats
from app.templating import templates

router = APIRouter()


@router.get("/")
def dashboard(request: Request, month: str = "", session: Session = Depends(get_session)):
    today = date.today()
    try:
        year, mon = (int(p) for p in month.split("-"))
        selected = date(year, mon, 1)
    except (ValueError, TypeError):
        selected = date(today.year, today.month, 1)

    context = {
        "request": request,
        "total_series": stats.total_balance_series(session),
        "total_balance_cents": stats.total_current_balance(session),
        "cashflow": stats.monthly_cashflow(session, months=12),
        "expenses_month": stats.expenses_by_category(session, year=selected.year, month=selected.month)[:8],
        "expenses_year": stats.expenses_by_category(session, year=selected.year)[:8],
        "top_merchants": stats.top_merchants(session, year=selected.year, month=selected.month, limit=8),
        "savings_month": stats.monthly_savings(session, year=selected.year, month=selected.month),
        "yearly_totals": stats.yearly_totals(session),
        "recurring_items": recurring.detect_recurring(session)[:6],
        "current_month_label": selected.strftime("%m/%Y"),
        "selected_month": selected.strftime("%Y-%m"),
        "max_month": today.strftime("%Y-%m"),
    }
    return templates.TemplateResponse("dashboard.html", context)
