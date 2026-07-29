from collections import defaultdict
from datetime import date
from statistics import median, pstdev

from sqlmodel import Session, select

from app.models import Transaction
from app.models.enums import TransactionType
from app.services.importing.dedup import normalize_description

# (gap mínimo, gap máximo, etiqueta, días nominales, valor enum de frecuencia)
FREQUENCY_RULES = [
    (25, 35, "Mensual", 30, "monthly"),
    (6, 8, "Semanal", 7, "weekly"),
    (350, 380, "Anual", 365, "yearly"),
]

# Umbrales sobre el % de cambio del último cargo respecto a la mediana anterior
STABLE_THRESHOLD_PCT = 2.0
PRICE_JUMP_THRESHOLD_PCT = 8.0
# Si el histórico previo ya varía más que esto (coef. de variación), un salto no es
# una "subida de precio" sino la volatilidad normal de esa factura (ej: luz, gasolina)
VOLATILE_CV_THRESHOLD = 0.10


def _price_label(change_pct: float) -> str:
    if abs(change_pct) < STABLE_THRESHOLD_PCT:
        return "estable"
    if change_pct >= PRICE_JUMP_THRESHOLD_PCT:
        return "subida"
    if change_pct <= -PRICE_JUMP_THRESHOLD_PCT:
        return "bajada"
    return "variacion"


def analyze_amounts(amounts: list[int]) -> tuple[float, str]:
    """Devuelve (% de cambio, etiqueta) del último importe frente a la mediana de los anteriores."""
    prev = amounts[:-1]
    prev_med = median(prev)
    change_pct = ((amounts[-1] - prev_med) / prev_med * 100) if prev_med else 0.0

    cv = (pstdev(prev) / prev_med) if prev_med and len(prev) > 1 else 0.0
    if cv > VOLATILE_CV_THRESHOLD:
        label = "variacion" if abs(change_pct) >= STABLE_THRESHOLD_PCT else "estable"
    else:
        label = _price_label(change_pct)
    return round(change_pct, 1), label


def transactions_for_pattern(session: Session, pattern: str) -> list[Transaction]:
    """Movimientos cuya descripcion normalizada coincide exactamente con el patron
    (mismo agrupamiento que usa detect_recurring), ordenados por fecha."""
    txs = session.exec(
        select(Transaction)
        .where(Transaction.transaction_type == TransactionType.expense)
        .order_by(Transaction.date)
    ).all()
    return [t for t in txs if normalize_description(t.description) == pattern]


def detect_recurring(session: Session, *, min_occurrences: int = 3) -> list[dict]:
    """Detecta gastos recurrentes agrupando por descripción normalizada.

    A diferencia de agrupar por (descripción, importe), agrupar solo por descripción
    permite seguir detectando la suscripción cuando sube de precio, y calcular la
    variación del último cargo frente a la mediana de los anteriores.
    """
    txs = session.exec(
        select(Transaction)
        .where(Transaction.transaction_type == TransactionType.expense)
        .order_by(Transaction.date)
    ).all()

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in txs:
        groups[normalize_description(tx.description)].append(tx)

    results = []
    today = date.today()

    for pattern, group_txs in groups.items():
        if len(group_txs) < min_occurrences:
            continue

        dates = sorted(t.date for t in group_txs)
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_gap = sum(gaps) / len(gaps)

        frequency = None
        for lo, hi, label, nominal_days, freq_value in FREQUENCY_RULES:
            if lo <= avg_gap <= hi:
                frequency, freq_days, freq_value_enum = label, nominal_days, freq_value
                break
        if frequency is None:
            continue

        ordered = sorted(group_txs, key=lambda t: t.date)
        amounts = [abs(t.amount_cents) for t in ordered]
        last_amount = amounts[-1]
        prev_median = median(amounts[:-1])
        change_pct, price_label = analyze_amounts(amounts)

        days_since_last = (today - dates[-1]).days
        possibly_cancelled = days_since_last > freq_days * 2

        results.append(
            {
                "description": ordered[-1].description,
                "pattern": pattern,
                "frequency": frequency,
                "frequency_value": freq_value_enum,
                "occurrences": len(group_txs),
                "first_date": dates[0].isoformat(),
                "last_date": dates[-1].isoformat(),
                "avg_amount_cents": round(sum(amounts) / len(amounts)),
                "last_amount_cents": last_amount,
                "prev_median_cents": round(prev_median),
                "change_pct": change_pct,
                "price_label": price_label,
                "possibly_cancelled": possibly_cancelled,
            }
        )

    results.sort(key=lambda r: r["last_amount_cents"], reverse=True)
    return results
