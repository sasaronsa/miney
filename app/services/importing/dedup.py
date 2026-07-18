import hashlib
import re
from datetime import date


def normalize_description(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def compute_content_hash(*, account_id: int, tx_date: date, amount_cents: int, description: str) -> str:
    normalized = normalize_description(description)
    raw = f"{account_id}|{tx_date.isoformat()}|{amount_cents}|{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
