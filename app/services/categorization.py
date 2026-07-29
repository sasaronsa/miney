import re
from typing import Optional

from sqlmodel import Session, select

from app.models import Rule, Transaction
from app.models.enums import MatchField, MatchType


def suggest_category(
    session: Session, *, description: str, amount_cents: int, account_id: int
) -> Optional[int]:
    """Devuelve el category_id de la primera regla activa que coincide, ordenada por prioridad."""
    rules = session.exec(
        select(Rule).where(Rule.is_active == True).order_by(Rule.priority)  # noqa: E712
    ).all()

    for rule in rules:
        if rule_matches(rule, description=description, amount_cents=amount_cents, account_id=account_id):
            return rule.category_id
    return None


def apply_rule_to_uncategorized(session: Session, rule: Rule) -> int:
    """Aplica la regla a los movimientos que aun no tienen categoria. No pisa categorias ya puestas."""
    txs = session.exec(select(Transaction).where(Transaction.category_id.is_(None))).all()
    applied = 0
    for tx in txs:
        if rule_matches(rule, description=tx.description, amount_cents=tx.amount_cents, account_id=tx.account_id):
            tx.category_id = rule.category_id
            session.add(tx)
            applied += 1
    return applied


def rule_matches(rule: Rule, *, description: str, amount_cents: int, account_id: int) -> bool:
    if rule.match_field == MatchField.amount:
        return rule_matches_amount_range(rule.pattern, amount_cents)

    if rule.match_field == MatchField.account:
        text = str(account_id)
        pattern = rule.pattern
    else:
        text = description.lower()
        pattern = rule.pattern.lower()

    if rule.match_type == MatchType.contains:
        return pattern in text
    if rule.match_type == MatchType.exact:
        return text == pattern
    if rule.match_type == MatchType.starts_with:
        return text.startswith(pattern)
    if rule.match_type == MatchType.regex:
        try:
            return bool(re.search(rule.pattern, description, re.IGNORECASE))
        except re.error:
            return False
    return False


def rule_matches_amount_range(pattern: str, amount_cents: int) -> bool:
    """pattern con formato 'min,max' en euros, ej: '-50,-10' para gastos entre 10 y 50 euros."""
    try:
        min_str, max_str = pattern.split(",")
        min_cents = round(float(min_str.strip()) * 100)
        max_cents = round(float(max_str.strip()) * 100)
        return min_cents <= amount_cents <= max_cents
    except (ValueError, IndexError):
        return False
