from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def format_cents(cents: int | None, currency: str = "EUR") -> Markup:
    """Formatea céntimos como importe. Va envuelto en <span class="amt"> para que
    el modo demo pueda difuminar todas las cifras de la app de una vez."""
    if cents is None:
        return Markup('<span class="amt">-</span>')
    value = cents / 100
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    symbol = "€" if currency == "EUR" else currency
    return Markup(f'<span class="amt">{formatted}&nbsp;{symbol}</span>')


def format_date_es(value: date | datetime | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.strftime("%d/%m/%Y")


from app.i18n import LANGUAGES, t  # noqa: E402

templates.env.filters["eur"] = format_cents
templates.env.filters["fecha"] = format_date_es
templates.env.globals["app_name"] = get_settings().app_name
templates.env.globals["t"] = t
templates.env.globals["languages"] = LANGUAGES
