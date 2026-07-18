from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.database import get_session
from app.services import recurring, stats
from app.templating import templates

router = APIRouter()


@router.get("/")
def dashboard(request: Request, session: Session = Depends(get_session)):
    today = date.today()

    context = {
        "request": request,
        "total_series": stats.total_balance_series(session),
        "total_balance_cents": stats.total_current_balance(session),
        "cashflow": stats.monthly_cashflow(session, months=12),
        "expenses_month": stats.expenses_by_category(session, year=today.year, month=today.month)[:8],
        "expenses_year": stats.expenses_by_category(session, year=today.year)[:8],
        "top_merchants": stats.top_merchants(session, year=today.year, month=today.month, limit=8),
        "savings_rate_month": stats.savings_rate(session, year=today.year, month=today.month),
        "yearly_totals": stats.yearly_totals(session),
        "recurring_items": recurring.detect_recurring(session)[:6],
        "current_month_label": today.strftime("%m/%Y"),
    }
    return templates.TemplateResponse("dashboard.html", context)
