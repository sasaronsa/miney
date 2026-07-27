from app.routers.imports import _mapping_from_form
from app.services.importing.mapping import parse_amount


def _build(decimal_separator="", thousands_separator=""):
    return _mapping_from_form(
        date_column="fecha",
        description_column="concepto",
        amount_column="importe",
        debit_column="",
        credit_column="",
        external_id_column="",
        date_format="",
        decimal_separator=decimal_separator,
        thousands_separator=thousands_separator,
    )


def test_empty_thousands_separator_from_form_is_preserved_as_empty():
    # Regresion: un `or "."` en _mapping_from_form reintroducia el punto como
    # separador de miles aunque el usuario lo dejara vacio a proposito, rompiendo
    # el parseo de importes con decimales (ej. "-22.31" -> -2231.00 en vez de -22.31).
    mapping = _build(decimal_separator=".", thousands_separator="")
    assert mapping.thousands_separator == ""
    assert parse_amount("-22.31", mapping.decimal_separator, mapping.thousands_separator) == -2231


def test_decimal_separator_from_form_is_preserved_as_is():
    mapping = _build(decimal_separator=",", thousands_separator=".")
    assert mapping.decimal_separator == ","
    assert mapping.thousands_separator == "."
    assert parse_amount("-1.234,56", mapping.decimal_separator, mapping.thousands_separator) == -123456


def test_column_selectors_still_fall_back_to_none_when_empty():
    # amount_column/debit_column/etc si tienen semantica distinta: "" significa
    # "no se ha seleccionado columna", por lo que deben seguir convirtiendose a None.
    mapping = _mapping_from_form(
        date_column="fecha",
        description_column="concepto",
        amount_column="",
        debit_column="",
        credit_column="",
        external_id_column="",
        date_format="",
        decimal_separator=",",
        thousands_separator=".",
    )
    assert mapping.amount_column is None
    assert mapping.debit_column is None
    assert mapping.credit_column is None
    assert mapping.external_id_column is None
    assert mapping.date_format == "%d/%m/%Y"
