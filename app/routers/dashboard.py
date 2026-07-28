from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.database import get_session
from app.i18n import MONTHS_ES
from app.services import recurring, stats
from app.templating import templates

router = APIRouter()


def _add_months(d: date, delta: int) -> date:
    total = d.year * 12 + (d.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


@router.get("/")
def dashboard(request: Request, month: str = "", session: Session = Depends(get_session)):
    today = date.today()
    try:
        year, mon = (int(p) for p in month.split("-"))
        selected = date(year, mon, 1)
    except (ValueError, TypeError):
        selected = date(today.year, today.month, 1)

    current_month_start = date(today.year, today.month, 1)
    next_month = _add_months(selected, 1)

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
        "month_name": MONTHS_ES[selected.month - 1],
        "selected_year": selected.year,
        "prev_month": _add_months(selected, -1).strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m") if next_month <= current_month_start else None,
    }
    return templates.TemplateResponse("dashboard.html", context)
