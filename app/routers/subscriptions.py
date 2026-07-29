from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Account, Category, Subscription
from app.models.enums import SubscriptionFrequency
from app.services import recurring
from app.services.subscriptions import (
    all_subscription_stats,
    subscription_rule,
    sync_subscription_rule,
    untracked_recurring,
)
from app.templating import templates
from app.utils import parse_amount_input

router = APIRouter(prefix="/subscriptions")


@router.get("")
def list_subscriptions(request: Request, session: Session = Depends(get_session)):
    stats = all_subscription_stats(session)
    detected = untracked_recurring(session, recurring.detect_recurring(session))

    active_stats = [s for s in stats if s["status"] != "finalizada"]
    monthly_total = sum(s["monthly_cents"] for s in active_stats)

    return templates.TemplateResponse(
        "subscriptions/list.html",
        {
            "request": request,
            "stats": stats,
            "detected": detected,
            "monthly_total_cents": monthly_total,
            "yearly_total_cents": monthly_total * 12,
            "active_count": len(active_stats),
        },
    )


def _form_context(session: Session, sub: Subscription | None, request: Request) -> dict:
    return {
        "request": request,
        "sub": sub,
        "accounts": session.exec(select(Account).where(Account.is_active == True)).all(),  # noqa: E712
        "categories": session.exec(select(Category)).all(),
        "frequencies": list(SubscriptionFrequency),
    }


@router.get("/new")
def new_subscription_form(
    request: Request,
    name: str = "",
    pattern: str = "",
    amount: str = "",
    frequency: str = "",
    session: Session = Depends(get_session),
):
    prefill = Subscription(
        name=name.title() if name else "",
        match_pattern=pattern,
        expected_amount_cents=round(float(amount) * 100) if amount else None,
        frequency=SubscriptionFrequency(frequency) if frequency in SubscriptionFrequency.__members__ else SubscriptionFrequency.monthly,
    )
    context = _form_context(session, None, request)
    context["prefill"] = prefill
    return templates.TemplateResponse("subscriptions/form.html", context)


def _apply_form(
    sub: Subscription,
    name: str,
    website: str,
    match_pattern: str,
    frequency: SubscriptionFrequency,
    expected_amount: str,
    account_id: str,
    category_id: str,
    start_date: str,
    end_date: str,
    notes: str,
) -> None:
    sub.name = name
    sub.website = website.strip() or None
    sub.match_pattern = match_pattern.strip().lower()
    sub.frequency = frequency
    sub.expected_amount_cents = parse_amount_input(expected_amount) if expected_amount.strip() else None
    sub.account_id = int(account_id) if account_id else None
    sub.category_id = int(category_id) if category_id else None
    sub.start_date = date.fromisoformat(start_date) if start_date else None
    sub.end_date = date.fromisoformat(end_date) if end_date else None
    sub.notes = notes.strip() or None


def _saved_message(rule, applied: int) -> str:
    msg = "Suscripción guardada"
    if rule is None:
        return msg
    msg += f" · regla automática «{rule.name}»"
    if applied:
        plural = "movimiento" if applied == 1 else "movimientos"
        msg += f", aplicada a {applied} {plural} sin categoría"
    return msg


@router.post("/new")
def create_subscription(
    name: str = Form(...),
    website: str = Form(""),
    match_pattern: str = Form(...),
    frequency: SubscriptionFrequency = Form(SubscriptionFrequency.monthly),
    expected_amount: str = Form(""),
    account_id: str = Form(""),
    category_id: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    sub = Subscription(name=name, match_pattern=match_pattern)
    _apply_form(sub, name, website, match_pattern, frequency, expected_amount, account_id, category_id, start_date, end_date, notes)
    session.add(sub)
    session.commit()
    session.refresh(sub)

    rule, applied = sync_subscription_rule(session, sub)
    session.commit()
    return RedirectResponse(url=f"/subscriptions?msg={_saved_message(rule, applied)}", status_code=303)


@router.get("/{subscription_id}/edit")
def edit_subscription_form(subscription_id: int, request: Request, session: Session = Depends(get_session)):
    sub = session.get(Subscription, subscription_id)
    if not sub:
        return RedirectResponse(url="/subscriptions", status_code=303)
    context = _form_context(session, sub, request)
    context["prefill"] = sub
    return templates.TemplateResponse("subscriptions/form.html", context)


@router.post("/{subscription_id}/edit")
def update_subscription(
    subscription_id: int,
    name: str = Form(...),
    website: str = Form(""),
    match_pattern: str = Form(...),
    frequency: SubscriptionFrequency = Form(SubscriptionFrequency.monthly),
    expected_amount: str = Form(""),
    account_id: str = Form(""),
    category_id: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    sub = session.get(Subscription, subscription_id)
    if not sub:
        return RedirectResponse(url="/subscriptions", status_code=303)

    _apply_form(sub, name, website, match_pattern, frequency, expected_amount, account_id, category_id, start_date, end_date, notes)
    session.add(sub)
    session.commit()

    rule, applied = sync_subscription_rule(session, sub)
    session.commit()
    return RedirectResponse(url=f"/subscriptions?msg={_saved_message(rule, applied)}", status_code=303)


@router.post("/{subscription_id}/delete")
def delete_subscription(subscription_id: int, session: Session = Depends(get_session)):
    sub = session.get(Subscription, subscription_id)
    if sub:
        rule = subscription_rule(session, sub)
        if rule:
            session.delete(rule)
        session.delete(sub)
        session.commit()
    return RedirectResponse(url="/subscriptions", status_code=303)
