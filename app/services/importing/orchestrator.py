from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from app.models import Account, Category, ImportBatch, Transaction
from app.models.enums import ImportBatchStatus, ImportSource, TransactionType
from app.services.categorization import suggest_category
from app.services.importing.dedup import compute_content_hash
from app.services.importing.mapping import ColumnMapping, NormalizedRow, normalize_rows
from app.services.importing.parsers import parse_csv, parse_excel, parse_pdf

TRANSFER_MATCH_MAX_DAYS = 4


def _transfer_candidates(session: Session, *, exclude_account_id: int) -> dict[int, list[Transaction]]:
    """Movimientos de OTRAS cuentas (no transferencias) indexados por importe."""
    txs = session.exec(
        select(Transaction).where(
            Transaction.transaction_type != TransactionType.transfer,
            Transaction.account_id != exclude_account_id,
        )
    ).all()
    by_amount: dict[int, list[Transaction]] = {}
    for t in txs:
        by_amount.setdefault(t.amount_cents, []).append(t)
    return by_amount


def _pop_transfer_match(
    by_amount: dict[int, list[Transaction]], row: NormalizedRow
) -> Optional[Transaction]:
    """Busca (y consume) un movimiento de otra cuenta con importe opuesto en fechas cercanas."""
    candidates = by_amount.get(-row.amount_cents, [])
    for i, tx in enumerate(candidates):
        if abs((tx.date - row.tx_date).days) <= TRANSFER_MATCH_MAX_DAYS:
            return candidates.pop(i)
    return None


def parse_uploaded_file(
    content: bytes,
    filename: str,
    *,
    delimiter: str = ";",
    encoding: str = "utf-8",
    header_row: int = 0,
) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv") or lower.endswith(".txt"):
        return parse_csv(content, delimiter=delimiter, encoding=encoding, header_row=header_row)
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return parse_excel(content, header_row=header_row)
    if lower.endswith(".pdf"):
        return parse_pdf(content)
    raise ValueError(f"Formato de fichero no soportado: {filename}")


def source_from_filename(filename: str) -> ImportSource:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return ImportSource.pdf
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return ImportSource.excel
    return ImportSource.csv


def build_preview(session: Session, df: pd.DataFrame, mapping: ColumnMapping, *, account_id: int) -> dict:
    rows = normalize_rows(df, mapping)
    categories = {c.id: c for c in session.exec(select(Category)).all()}
    accounts = {a.id: a for a in session.exec(select(Account)).all()}

    account_txs = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    existing_external_ids = {t.external_id for t in account_txs if t.external_id}
    existing_hashes = {t.content_hash for t in account_txs}

    transfer_index = _transfer_candidates(session, exclude_account_id=account_id)

    preview_rows = []
    seen_hashes_in_file: set[str] = set()
    seen_external_in_file: set[str] = set()
    duplicate_count = 0
    error_count = 0
    transfer_count = 0

    for row in rows:
        entry = {
            "row_index": row.row_index,
            "date": row.tx_date.isoformat() if row.tx_date else None,
            "description": row.description,
            "amount_cents": row.amount_cents,
            "external_id": row.external_id,
            "error": row.error,
            "is_duplicate": False,
            "duplicate_reason": None,
            "suggested_category_id": None,
            "suggested_category_name": None,
        }

        if row.error:
            error_count += 1
            preview_rows.append(entry)
            continue

        content_hash = compute_content_hash(
            account_id=account_id,
            tx_date=row.tx_date,
            amount_cents=row.amount_cents,
            description=row.description,
        )
        entry["content_hash"] = content_hash

        is_dup = False
        reason = None
        if row.external_id and (
            row.external_id in existing_external_ids or row.external_id in seen_external_in_file
        ):
            is_dup = True
            reason = "ID externo ya existente"
        elif content_hash in existing_hashes or content_hash in seen_hashes_in_file:
            is_dup = True
            reason = "Movimiento identico ya importado (fecha + importe + descripcion)"

        if is_dup:
            duplicate_count += 1
        entry["is_duplicate"] = is_dup
        entry["duplicate_reason"] = reason

        if row.external_id:
            seen_external_in_file.add(row.external_id)
        seen_hashes_in_file.add(content_hash)

        category_id = suggest_category(
            session, description=row.description, amount_cents=row.amount_cents, account_id=account_id
        )
        if category_id and category_id in categories:
            entry["suggested_category_id"] = category_id
            entry["suggested_category_name"] = categories[category_id].name

        entry["possible_transfer"] = False
        if not is_dup:
            match = _pop_transfer_match(transfer_index, row)
            if match:
                transfer_count += 1
                other = accounts.get(match.account_id)
                entry["possible_transfer"] = True
                entry["transfer_account_name"] = other.name if other else "otra cuenta"
                entry["transfer_date"] = match.date.isoformat()

        preview_rows.append(entry)

    return {
        "rows": preview_rows,
        "total_rows": len(preview_rows),
        "duplicate_rows": duplicate_count,
        "error_rows": error_count,
        "transfer_rows": transfer_count,
        "insertable_rows": len(preview_rows) - duplicate_count - error_count,
    }


def insert_transactions(
    session: Session,
    *,
    df: pd.DataFrame,
    mapping: ColumnMapping,
    account_id: int,
    filename: str,
    source: ImportSource,
    included_row_indices: set[int],
    total_rows: int,
    duplicate_rows: int,
    mapping_template_id: Optional[int] = None,
    transfer_row_indices: Optional[set[int]] = None,
) -> ImportBatch:
    rows = normalize_rows(df, mapping)
    transfer_row_indices = transfer_row_indices or set()
    transfer_index = _transfer_candidates(session, exclude_account_id=account_id)

    batch = ImportBatch(
        filename=filename,
        account_id=account_id,
        source=source,
        mapping_template_id=mapping_template_id,
        total_rows=total_rows,
        duplicate_rows=duplicate_rows,
        status=ImportBatchStatus.completed,
    )
    session.add(batch)
    session.flush()

    inserted = 0
    for row in rows:
        if row.error or row.row_index not in included_row_indices:
            continue

        content_hash = compute_content_hash(
            account_id=account_id,
            tx_date=row.tx_date,
            amount_cents=row.amount_cents,
            description=row.description,
        )

        # Transferencia interna confirmada por el usuario: se guardan las DOS patas
        # (una por cuenta, enlazadas por transfer_account_id) para que el traspaso
        # aparezca en el listado de movimientos de ambas cuentas, no solo en una.
        if row.row_index in transfer_row_indices:
            match = _pop_transfer_match(transfer_index, row)
            if match:
                leg = Transaction(
                    date=row.tx_date,
                    amount_cents=row.amount_cents,
                    description=row.description,
                    account_id=account_id,
                    transfer_account_id=match.account_id,
                    transfer_transaction_id=match.id,
                    transaction_type=TransactionType.transfer,
                    external_id=row.external_id,
                    content_hash=content_hash,
                    source=source,
                    import_batch_id=batch.id,
                )
                session.add(leg)
                session.flush()  # necesita id para enlazar la pata contraria
                inserted += 1
                match.transaction_type = TransactionType.transfer
                match.transfer_account_id = account_id
                match.transfer_transaction_id = leg.id
                match.category_id = None
                session.add(match)
                continue

        transaction_type = TransactionType.income if row.amount_cents >= 0 else TransactionType.expense
        category_id = suggest_category(
            session, description=row.description, amount_cents=row.amount_cents, account_id=account_id
        )

        session.add(
            Transaction(
                date=row.tx_date,
                amount_cents=row.amount_cents,
                description=row.description,
                account_id=account_id,
                category_id=category_id,
                transaction_type=transaction_type,
                external_id=row.external_id,
                content_hash=content_hash,
                source=source,
                import_batch_id=batch.id,
            )
        )
        inserted += 1

    batch.inserted_rows = inserted
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch
