import io

import pandas as pd
import pdfplumber

MAX_PREVIEW_ROWS = 25


def parse_csv(content: bytes, *, delimiter: str = ";", encoding: str = "utf-8", header_row: int = 0) -> pd.DataFrame:
    try:
        df = pd.read_csv(
            io.BytesIO(content),
            delimiter=delimiter,
            encoding=encoding,
            header=header_row,
            dtype=str,
            skip_blank_lines=True,
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            io.BytesIO(content),
            delimiter=delimiter,
            encoding="latin-1",
            header=header_row,
            dtype=str,
            skip_blank_lines=True,
        )
    return _clean_dataframe(df)


def parse_excel(content: bytes, *, header_row: int = 0) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(content), header=header_row, dtype=str)
    return _clean_dataframe(df)


def parse_pdf(content: bytes) -> pd.DataFrame:
    """Extrae tablas de un PDF con texto seleccionable (no soporta PDFs escaneados/OCR)."""
    all_rows: list[list[str]] = []
    header: list[str] | None = None

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                if header is None:
                    header = [str(c or f"col_{i}") for i, c in enumerate(table[0])]
                    rows = table[1:]
                else:
                    rows = table
                    if rows and [str(c or "") for c in rows[0]] == header:
                        rows = rows[1:]
                all_rows.extend(rows)

    if not header or not all_rows:
        raise ValueError(
            "No se han detectado tablas con texto seleccionable en el PDF. "
            "Si es un extracto escaneado (imagen), exporta el movimiento como CSV/Excel desde tu banco."
        )

    df = pd.DataFrame(all_rows, columns=header)
    return _clean_dataframe(df)


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.reset_index(drop=True)
    return df
