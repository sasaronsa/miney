from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Category, Rule, Transaction
from app.models.enums import MatchField, MatchType
from app.services.categorization import rule_matches
from app.templating import templates

router = APIRouter(prefix="/rules")


@router.get("")
def list_rules(request: Request, session: Session = Depends(get_session)):
    rules = session.exec(select(Rule).order_by(Rule.priority)).all()
    categories = session.exec(select(Category)).all()
    categories_by_id = {c.id: c for c in categories}
    return templates.TemplateResponse(
        "rules/list.html",
        {
            "request": request,
            "rules": rules,
            "categories": categories,
            "categories_by_id": categories_by_id,
            "match_fields": list(MatchField),
            "match_types": list(MatchType),
        },
    )


@router.post("/new")
def create_rule(
    name: str = Form(...),
    priority: int = Form(100),
    match_field: MatchField = Form(...),
    match_type: MatchType = Form(...),
    pattern: str = Form(...),
    category_id: int = Form(...),
    session: Session = Depends(get_session),
):
    session.add(
        Rule(
            name=name,
            priority=priority,
            match_field=match_field,
            match_type=match_type,
            pattern=pattern,
            category_id=category_id,
        )
    )
    session.commit()
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/{rule_id}/edit")
def update_rule(
    rule_id: int,
    name: str = Form(...),
    priority: int = Form(100),
    match_field: MatchField = Form(...),
    match_type: MatchType = Form(...),
    pattern: str = Form(...),
    category_id: int = Form(...),
    is_active: bool = Form(False),
    session: Session = Depends(get_session),
):
    rule = session.get(Rule, rule_id)
    if rule:
        rule.name = name
        rule.priority = priority
        rule.match_field = match_field
        rule.match_type = match_type
        rule.pattern = pattern
        rule.category_id = category_id
        rule.is_active = is_active
        session.add(rule)
        session.commit()
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/{rule_id}/delete")
def delete_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(Rule, rule_id)
    if rule:
        session.delete(rule)
        session.commit()
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/{rule_id}/apply-retroactive")
def apply_rule_retroactively(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(Rule, rule_id)
    if not rule:
        return RedirectResponse(url="/rules", status_code=303)

    txs = session.exec(select(Transaction).where(Transaction.category_id.is_(None))).all()
    applied = 0
    for tx in txs:
        if rule_matches(rule, description=tx.description, amount_cents=tx.amount_cents, account_id=tx.account_id):
            tx.category_id = rule.category_id
            session.add(tx)
            applied += 1
    session.commit()
    return RedirectResponse(url=f"/rules?msg=Regla aplicada a {applied} movimientos", status_code=303)
