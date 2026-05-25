from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DocumentRunRecord:
    run_id: str
    document_title: str
    system_id: str
    plan: dict[str, Any]
    status: str
    created_at: datetime | str
    completed_at: datetime | str | None = None
    export_artifact: dict[str, Any] | None = None


@dataclass(slots=True)
class RetrievalPassRecord:
    pass_id: str
    run_id: str
    section_name: str
    pass_number: int
    query: str
    request_id: str | None
    status: str
    created_at: datetime | str
