import io

import pytest
from openpyxl import Workbook

from app.services.importing.mapping import ColumnMapping, normalize_rows, parse_amount
from app.services.importing.parsers import parse_excel


def _build_xlsx(rows: list[tuple]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Fecha", "Concepto", "Importe", "IdExterno"])
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize(
    "value, decimal_sep, thousands_sep, expected_cents",
    [
        # Regresion: una celda de Excel numerica (int/float autentico) no debe
        # pasar por el reemplazo de separadores. El "." es el decimal real de
        # Python, no un separador de miles, aunque el usuario tenga configurado
        # miles="." (formato espanol, el mas comun). Antes esto multiplicaba el
        # importe x100 al borrar el punto y tratarlo como si ya fueran centimos.
        (-22.15, ",", ".", -2215),
        (-380.10, ",", ".", -38010),
        (-22.31, ".", "", -2231),
        (2964.44, ",", ".", 296444),
        (0.09, ",", ".", 9),
        (-32, ",", ".", -3200),  # entero, sin decimales
    ],
)
def test_parse_amount_uses_native_numbers_directly(value, decimal_sep, thousands_sep, expected_cents):
    assert parse_amount(value, decimal_sep, thousands_sep) == expected_cents


def test_parse_excel_keeps_amount_column_as_native_float():
    # dtype=str convertia estas celdas en texto ("-380.1"), perdiendo el tipo
    # numerico y con ello la unica senal fiable de que el punto es un decimal.
    content = _build_xlsx([("01/03/2024", "Compra", -380.10, 1)])
    df = parse_excel(content)
    assert df["Importe"].dtype.kind == "f"


def test_normalize_rows_excel_spanish_separators_end_to_end():
    # Reproduce el bug real reportado: fichero .xlsx con celdas de importe
    # numericas nativas y el mapeo por defecto (decimal=",", miles=".").
    content = _build_xlsx(
        [
            ("01/03/2024", "Compra A", -22.15, 1),
            ("02/03/2024", "Compra B", -380.10, 2),
            ("03/03/2024", "Nomina", 2964.44, 3),
        ]
    )
    df = parse_excel(content)
    mapping = ColumnMapping(
        date_column="Fecha",
        description_column="Concepto",
        amount_column="Importe",
        external_id_column="IdExterno",
        decimal_separator=",",
        thousands_separator=".",
    )
    rows = normalize_rows(df, mapping)
    assert [r.error for r in rows] == [None, None, None]
    assert [r.amount_cents for r in rows] == [-2215, -38010, 296444]


def test_normalize_rows_external_id_no_trailing_dot_zero_when_column_has_blanks():
    # Sin dtype=str, una columna de IDs con algun hueco se infiere como float
    # (NaN obliga a pandas a usar float64), y un ID entero como 2 se leeria
    # "2.0" en vez de "2" si no se limpia explicitamente.
    content = _build_xlsx(
        [
            ("01/03/2024", "Compra A", -10, 1),
            ("02/03/2024", "Compra B", -20, None),
            ("03/03/2024", "Compra C", -30, 3),
        ]
    )
    df = parse_excel(content)
    mapping = ColumnMapping(
        date_column="Fecha",
        description_column="Concepto",
        amount_column="Importe",
        external_id_column="IdExterno",
    )
    rows = normalize_rows(df, mapping)
    assert rows[0].external_id == "1"
    assert rows[1].external_id is None
    assert rows[2].external_id == "3"
