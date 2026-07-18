import calendar
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Budget, Category
from app.models.enums import BudgetPeriod
from app.services.stats import expense_allocation
from app.templating import templates
from app.utils import parse_amount_input

router = APIRouter(prefix="/budgets")


@router.get("")
def list_budgets(
    request: Request,
    year: int = 0,
    month: int = 0,
    session: Session = Depends(get_session),
):
    today = date.today()
    year = year or today.year
    month = month or today.month
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    budgets = session.exec(select(Budget)).all()
    active = [
        b
        for b in budgets
        if b.start_date <= month_end and (b.end_date is None or b.end_date >= month_start)
    ]

    categories_by_id = {c.id: c for c in session.exec(select(Category)).all()}
    month_alloc = expense_allocation(session, date_from=month_start, date_to=month_end)

    budget_rows = []
    for b in active:
        if b.period == BudgetPeriod.monthly:
            spent = month_alloc.get(b.category_id, 0)
        else:
            range_alloc = expense_allocation(
                session, date_from=b.start_date, date_to=b.end_date or today
            )
            spent = range_alloc.get(b.category_id, 0)

        pct = round(spent / b.amount_limit_cents * 100) if b.amount_limit_cents else 0
        budget_rows.append(
            {
                "budget": b,
                "category": categories_by_id.get(b.category_id),
                "spent_cents": spent,
                "remaining_cents": b.amount_limit_cents - spent,
                "pct": min(pct, 100),
                "real_pct": pct,
                "over_budget": spent > b.amount_limit_cents,
            }
        )

    budget_rows.sort(key=lambda r: r["real_pct"], reverse=True)

    return templates.TemplateResponse(
        "budgets/list.html",
        {
            "request": request,
            "budget_rows": budget_rows,
            "categories": sorted(categories_by_id.values(), key=lambda c: c.name),
            "year": year,
            "month": month,
            "today": today,
        },
    )


@router.post("/new")
def create_budget(
    category_id: int = Form(...),
    amount_limit: str = Form(...),
    period: BudgetPeriod = Form(BudgetPeriod.monthly),
    start_date: str = Form(...),
    end_date: str = Form(""),
    year: int = Form(0),
    month: int = Form(0),
    session: Session = Depends(get_session),
):
    session.add(
        Budget(
            category_id=category_id,
            amount_limit_cents=parse_amount_input(amount_limit),
            period=period,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date) if end_date else None,
        )
    )
    session.commit()
    suffix = f"?year={year}&month={month}" if year and month else ""
    return RedirectResponse(url=f"/budgets{suffix}", status_code=303)


@router.post("/{budget_id}/delete")
def delete_budget(
    budget_id: int,
    year: int = Form(0),
    month: int = Form(0),
    session: Session = Depends(get_session),
):
    budget = session.get(Budget, budget_id)
    if budget:
        session.delete(budget)
        session.commit()
    suffix = f"?year={year}&month={month}" if year and month else ""
    return RedirectResponse(url=f"/budgets{suffix}", status_code=303)
