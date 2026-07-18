def parse_amount_input(raw: str) -> int:
    """Convierte un importe introducido en un formulario (con , o . como separador decimal) a centimos."""
    raw = (raw or "0").strip()
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    return round(float(raw or "0") * 100)
