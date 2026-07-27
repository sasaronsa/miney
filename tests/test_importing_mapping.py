import pytest

from app.services.importing.mapping import parse_amount


@pytest.mark.parametrize(
    "raw, decimal_sep, thousands_sep, expected_cents",
    [
        # Separador de miles vacio a proposito: no debe reintroducirse "." ni "," por defecto.
        ("-22.31", ".", "", -2231),
        ("-122.5", ".", "", -12250),
        ("-1234.56", ".", "", -123456),
        # Formato espanol: coma decimal, punto de miles.
        ("-1.234,56", ",", ".", -123456),
        ("1.234,56", ",", ".", 123456),
        # Sin decimales, con o sin separador de miles, sigue funcionando.
        ("-32", ".", "", -3200),
        ("-21", ",", ".", -2100),
        ("-1.234", ",", ".", -123400),
    ],
)
def test_parse_amount_respects_explicit_empty_thousands_separator(
    raw, decimal_sep, thousands_sep, expected_cents
):
    assert parse_amount(raw, decimal_sep, thousands_sep) == expected_cents


def test_parse_amount_euro_symbol_is_stripped():
    assert parse_amount("22,31 €", ",", ".") == 2231
