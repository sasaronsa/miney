from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ImportBatchStatus, ImportSource


class ImportBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    account_id: int = Field(foreign_key="account.id")
    source: ImportSource
    mapping_template_id: Optional[int] = Field(default=None, foreign_key="mappingtemplate.id")
    imported_at: datetime = Field(default_factory=datetime.utcnow)
    total_rows: int = Field(default=0)
    duplicate_rows: int = Field(default=0)
    inserted_rows: int = Field(default=0)
    status: ImportBatchStatus = Field(default=ImportBatchStatus.pending)
