from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Account, ImportBatch, MappingTemplate, Transaction, TransactionSplit
from app.models.enums import ImportBatchStatus
from app.services.importing.mapping import ColumnMapping
from app.services.importing.orchestrator import build_preview, insert_transactions, parse_uploaded_file, source_from_filename
from app.services.importing.upload_store import delete_upload, load_upload, save_upload
from app.templating import templates

router = APIRouter(prefix="/imports")


@router.get("")
def list_imports(request: Request, session: Session = Depends(get_session)):
    batches = session.exec(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).all()
    accounts = {a.id: a for a in session.exec(select(Account)).all()}
    return templates.TemplateResponse(
        "imports/list.html", {"request": request, "batches": batches, "accounts": accounts}
    )


@router.get("/new")
def new_import_form(request: Request, session: Session = Depends(get_session)):
    accounts = session.exec(select(Account).where(Account.is_active == True)).all()  # noqa: E712
    templates_list = session.exec(select(MappingTemplate)).all()
    return templates.TemplateResponse(
        "imports/upload.html",
        {"request": request, "accounts": accounts, "mapping_templates": templates_list},
    )


@router.post("/upload")
async def upload_file(
    request: Request,
    account_id: int = Form(...),
    mapping_template_id: str = Form(""),
    file: UploadFile = None,
    session: Session = Depends(get_session),
):
    content = await file.read()
    upload_id = save_upload(content, file.filename)
    source = source_from_filename(file.filename)

    try:
        df = parse_uploaded_file(content, file.filename)
    except ValueError as exc:
        delete_upload(upload_id)
        accounts = session.exec(select(Account).where(Account.is_active == True)).all()  # noqa: E712
        templates_list = session.exec(select(MappingTemplate)).all()
        return templates.TemplateResponse(
            "imports/upload.html",
            {
                "request": request,
                "accounts": accounts,
                "mapping_templates": templates_list,
                "error": str(exc),
            },
            status_code=400,
        )

    template = None
    if mapping_template_id:
        template = session.get(MappingTemplate, int(mapping_template_id))

    columns = list(df.columns)
    sample_rows = df.head(8).to_dict(orient="records")

    return templates.TemplateResponse(
        "imports/mapping.html",
        {
            "request": request,
            "upload_id": upload_id,
            "account_id": account_id,
            "filename": file.filename,
            "source": source.value,
            "columns": columns,
            "sample_rows": sample_rows,
            "template": template,
        },
    )


def _mapping_from_form(
    date_column: str,
    description_column: str,
    amount_column: str,
    debit_column: str,
    credit_column: str,
    external_id_column: str,
    date_format: str,
    decimal_separator: str,
    thousands_separator: str,
) -> ColumnMapping:
    return ColumnMapping(
        date_column=date_column,
        description_column=description_column,
        amount_column=amount_column or None,
        debit_column=debit_column or None,
        credit_column=credit_column or None,
        external_id_column=external_id_column or None,
        date_format=date_format or "%d/%m/%Y",
        decimal_separator=decimal_separator or ",",
        thousands_separator=thousands_separator or ".",
    )


@router.post("/preview")
def preview_import(
    request: Request,
    upload_id: str = Form(...),
    account_id: int = Form(...),
    filename: str = Form(...),
    source: str = Form(...),
    date_column: str = Form(...),
    description_column: str = Form(...),
    amount_column: str = Form(""),
    debit_column: str = Form(""),
    credit_column: str = Form(""),
    external_id_column: str = Form(""),
    date_format: str = Form("%d/%m/%Y"),
    decimal_separator: str = Form(","),
    thousands_separator: str = Form("."),
    save_template: bool = Form(False),
    template_name: str = Form(""),
    session: Session = Depends(get_session),
):
    content, _ = load_upload(upload_id)
    df = parse_uploaded_file(content, filename)

    mapping = _mapping_from_form(
        date_column,
        description_column,
        amount_column,
        debit_column,
        credit_column,
        external_id_column,
        date_format,
        decimal_separator,
        thousands_separator,
    )

    preview = build_preview(session, df, mapping, account_id=account_id)

    mapping_template_id = None
    if save_template and template_name:
        new_template = MappingTemplate(
            name=template_name,
            account_id=account_id,
            date_column=mapping.date_column,
            description_column=mapping.description_column,
            amount_column=mapping.amount_column,
            debit_column=mapping.debit_column,
            credit_column=mapping.credit_column,
            external_id_column=mapping.external_id_column,
            date_format=mapping.date_format,
            decimal_separator=mapping.decimal_separator,
            thousands_separator=mapping.thousands_separator,
        )
        session.add(new_template)
        session.commit()
        session.refresh(new_template)
        mapping_template_id = new_template.id

    return templates.TemplateResponse(
        "imports/preview.html",
        {
            "request": request,
            "upload_id": upload_id,
            "account_id": account_id,
            "filename": filename,
            "source": source,
            "mapping": mapping,
            "mapping_template_id": mapping_template_id or "",
            "preview": preview,
        },
    )


@router.post("/confirm")
def confirm_import(
    upload_id: str = Form(...),
    account_id: int = Form(...),
    filename: str = Form(...),
    source: str = Form(...),
    date_column: str = Form(...),
    description_column: str = Form(...),
    amount_column: str = Form(""),
    debit_column: str = Form(""),
    credit_column: str = Form(""),
    external_id_column: str = Form(""),
    date_format: str = Form("%d/%m/%Y"),
    decimal_separator: str = Form(","),
    thousands_separator: str = Form("."),
    total_rows: int = Form(0),
    duplicate_rows: int = Form(0),
    mapping_template_id: str = Form(""),
    include: list[int] = Form(default=[]),
    transfer: list[int] = Form(default=[]),
    session: Session = Depends(get_session),
):
    from app.models.enums import ImportSource

    content, _ = load_upload(upload_id)
    df = parse_uploaded_file(content, filename)

    mapping = _mapping_from_form(
        date_column,
        description_column,
        amount_column,
        debit_column,
        credit_column,
        external_id_column,
        date_format,
        decimal_separator,
        thousands_separator,
    )

    batch = insert_transactions(
        session,
        df=df,
        mapping=mapping,
        account_id=account_id,
        filename=filename,
        source=ImportSource(source),
        included_row_indices=set(include),
        total_rows=total_rows,
        duplicate_rows=duplicate_rows,
        mapping_template_id=int(mapping_template_id) if mapping_template_id else None,
        transfer_row_indices=set(transfer),
    )

    delete_upload(upload_id)

    return RedirectResponse(
        url=f"/transactions?account_id={account_id}&msg=Importados {batch.inserted_rows} movimientos",
        status_code=303,
    )


@router.post("/{batch_id}/undo")
def undo_import(batch_id: int, session: Session = Depends(get_session)):
    batch = session.get(ImportBatch, batch_id)
    if not batch or batch.status == ImportBatchStatus.undone:
        return RedirectResponse(url="/imports", status_code=303)

    txs = session.exec(select(Transaction).where(Transaction.import_batch_id == batch_id)).all()
    deleted = 0
    for tx in txs:
        for s in session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all():
            session.delete(s)
        session.delete(tx)
        deleted += 1

    batch.status = ImportBatchStatus.undone
    session.add(batch)
    session.commit()
    return RedirectResponse(
        url=f"/imports?msg=Importación deshecha: {deleted} movimientos eliminados", status_code=303
    )


@router.post("/templates/{template_id}/delete")
def delete_mapping_template(template_id: int, session: Session = Depends(get_session)):
    template = session.get(MappingTemplate, template_id)
    if template:
        session.delete(template)
        session.commit()
    return RedirectResponse(url="/imports/new", status_code=303)
