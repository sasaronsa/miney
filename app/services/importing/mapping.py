from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pandas as pd
from dateutil import parser as dateutil_parser

EMPTY_VALUES = {"", "nan", "none", "nat"}


@dataclass
class ColumnMapping:
    date_column: str
    description_column: str
    amount_column: Optional[str] = None
    debit_column: Optional[str] = None
    credit_column: Optional[str] = None
    external_id_column: Optional[str] = None
    date_format: str = "%d/%m/%Y"
    decimal_separator: str = ","
    thousands_separator: str = "."


@dataclass
class NormalizedRow:
    row_index: int
    tx_date: Optional[date]
    description: str
    amount_cents: Optional[int]
    external_id: Optional[str]
    error: Optional[str] = None


def _is_empty(value) -> bool:
    return value is None or str(value).strip().lower() in EMPTY_VALUES


def parse_amount(raw, decimal_sep: str, thousands_sep: str) -> int:
    if _is_empty(raw):
        raise ValueError("importe vacio")

    s = str(raw).strip()
    negative = False

    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    s = s.replace("€", "").replace("EUR", "").strip()

    if s.startswith("-"):
        negative = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]

    if thousands_sep:
        s = s.replace(thousands_sep, "")
    if decimal_sep and decimal_sep != ".":
        s = s.replace(decimal_sep, ".")

    value = float(s)
    if negative:
        value = -value
    return round(value * 100)


def parse_date(raw, date_format: str) -> date:
    if _is_empty(raw):
        raise ValueError("fecha vacia")

    s = str(raw).strip()
    try:
        return datetime.strptime(s, date_format).date()
    except ValueError:
        return dateutil_parser.parse(s, dayfirst=True).date()


def normalize_rows(df: pd.DataFrame, mapping: ColumnMapping) -> list[NormalizedRow]:
    results: list[NormalizedRow] = []

    for idx, row in df.iterrows():
        try:
            tx_date = parse_date(row.get(mapping.date_column), mapping.date_format)
            description = str(row.get(mapping.description_column) or "").strip()

            if mapping.amount_column:
                amount_cents = parse_amount(
                    row.get(mapping.amount_column), mapping.decimal_separator, mapping.thousands_separator
                )
            else:
                debit_raw = row.get(mapping.debit_column) if mapping.debit_column else None
                credit_raw = row.get(mapping.credit_column) if mapping.credit_column else None
                debit = (
                    abs(parse_amount(debit_raw, mapping.decimal_separator, mapping.thousands_separator))
                    if not _is_empty(debit_raw)
                    else 0
                )
                credit = (
                    parse_amount(credit_raw, mapping.decimal_separator, mapping.thousands_separator)
                    if not _is_empty(credit_raw)
                    else 0
                )
                amount_cents = credit - debit

            external_id = None
            if mapping.external_id_column:
                val = row.get(mapping.external_id_column)
                external_id = str(val).strip() if not _is_empty(val) else None

            if not description:
                raise ValueError("descripcion vacia")

            results.append(
                NormalizedRow(
                    row_index=idx,
                    tx_date=tx_date,
                    description=description,
                    amount_cents=amount_cents,
                    external_id=external_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 - fila invalida, se reporta al usuario
            results.append(
                NormalizedRow(
                    row_index=idx,
                    tx_date=None,
                    description=str(row.to_dict()),
                    amount_cents=None,
                    external_id=None,
                    error=str(exc),
                )
            )

    return results
