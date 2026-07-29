from datetime import date, timedelta
from statistics import median

from sqlmodel import Session, select

from app.models import Rule, Subscription, Transaction
from app.models.enums import MatchField, MatchType, SubscriptionFrequency, TransactionType
from app.services.categorization import apply_rule_to_uncategorized
from app.services.importing.dedup import normalize_description
from app.services.recurring import analyze_amounts

# Las reglas nacidas de una suscripcion mandan sobre las genericas: prioridad mas baja = antes
SUBSCRIPTION_RULE_PRIORITY = 1

FREQ_DAYS = {
    SubscriptionFrequency.weekly: 7,
    SubscriptionFrequency.monthly: 30,
    SubscriptionFrequency.yearly: 365,
    SubscriptionFrequency.other: 30,
}

FREQ_LABEL = {
    SubscriptionFrequency.weekly: "Semanal",
    SubscriptionFrequency.monthly: "Mensual",
    SubscriptionFrequency.yearly: "Anual",
    SubscriptionFrequency.other: "Otra",
}


def monthly_equivalent_cents(amount_cents: int, frequency: SubscriptionFrequency) -> int:
    if frequency == SubscriptionFrequency.weekly:
        return round(amount_cents * 4.33)
    if frequency == SubscriptionFrequency.yearly:
        return round(amount_cents / 12)
    return amount_cents


def matched_transactions(session: Session, sub: Subscription) -> list[Transaction]:
    query = select(Transaction).where(Transaction.transaction_type == TransactionType.expense)
    if sub.account_id:
        query = query.where(Transaction.account_id == sub.account_id)
    txs = session.exec(query.order_by(Transaction.date)).all()
    pattern = sub.match_pattern.strip().lower()
    return [t for t in txs if pattern in normalize_description(t.description)]


def subscription_stats(session: Session, sub: Subscription) -> dict:
    txs = matched_transactions(session, sub)
    today = date.today()
    freq_days = FREQ_DAYS[sub.frequency]

    stats: dict = {
        "subscription": sub,
        "tx_count": len(txs),
        "last_amount_cents": None,
        "prev_median_cents": None,
        "change_pct": None,
        "price_label": None,
        "last_date": None,
        "next_estimate": None,
        "status": "activa",
        "amounts_series": [],
    }

    if sub.end_date and sub.end_date <= today:
        stats["status"] = "finalizada"

    if txs:
        amounts = [abs(t.amount_cents) for t in txs]
        stats["last_amount_cents"] = amounts[-1]
        stats["last_date"] = txs[-1].date
        stats["amounts_series"] = [
            {"date": t.date.isoformat(), "amount_cents": abs(t.amount_cents)} for t in txs[-12:]
        ]
        if len(amounts) >= 2:
            stats["prev_median_cents"] = round(median(amounts[:-1]))
            change_pct, price_label = analyze_amounts(amounts)
            stats["change_pct"] = change_pct
            stats["price_label"] = price_label

        if stats["status"] != "finalizada":
            stats["next_estimate"] = txs[-1].date + timedelta(days=freq_days)
            if (today - txs[-1].date).days > freq_days * 2:
                stats["status"] = "sin_cargos"

    display_amount = stats["last_amount_cents"] or sub.expected_amount_cents or 0
    stats["display_amount_cents"] = display_amount
    stats["monthly_cents"] = (
        monthly_equivalent_cents(display_amount, sub.frequency) if stats["status"] != "finalizada" else 0
    )
    return stats


def all_subscription_stats(session: Session) -> list[dict]:
    subs = session.exec(select(Subscription).order_by(Subscription.name)).all()
    return [subscription_stats(session, s) for s in subs]


def subscription_rule(session: Session, sub: Subscription) -> Rule | None:
    return session.exec(select(Rule).where(Rule.subscription_id == sub.id)).first()


def sync_subscription_rule(session: Session, sub: Subscription) -> tuple[Rule | None, int]:
    """Mantiene una regla de categorizacion espejo de la suscripcion.

    Con categoria asignada crea (o actualiza) la regla y la aplica a los movimientos
    sin categorizar. Sin categoria, borra la regla que hubiera. Devuelve (regla, aplicados).
    """
    rule = subscription_rule(session, sub)
    pattern = (sub.match_pattern or "").strip().lower()

    if sub.category_id is None or not pattern:
        if rule:
            session.delete(rule)
        return None, 0

    if rule is None:
        rule = Rule(
            name=f"Suscripción: {sub.name}",
            priority=SUBSCRIPTION_RULE_PRIORITY,
            match_field=MatchField.description,
            match_type=MatchType.contains,
            pattern=pattern,
            category_id=sub.category_id,
            subscription_id=sub.id,
        )
    else:
        rule.name = f"Suscripción: {sub.name}"
        rule.match_field = MatchField.description
        rule.match_type = MatchType.contains
        rule.pattern = pattern
        rule.category_id = sub.category_id

    session.add(rule)
    applied = apply_rule_to_uncategorized(session, rule) if rule.is_active else 0
    return rule, applied


def untracked_recurring(session: Session, detected: list[dict]) -> list[dict]:
    """Filtra los recurrentes detectados que aún no están cubiertos por una suscripción."""
    patterns = [s.match_pattern.strip().lower() for s in session.exec(select(Subscription)).all()]
    return [item for item in detected if not any(p and p in item["pattern"] for p in patterns)]
