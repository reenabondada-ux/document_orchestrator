from __future__ import annotations

from typing import Protocol, runtime_checkable
from mainframe_doc_orchestrator.models import (
    DocumentDraft,
    DocumentPlan,
    DocumentRequest,
    EvidencePack,
    RetrievalRequest,
)


@runtime_checkable
class RetrievalClient(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> EvidencePack: ...
    async def fetch_evidence_pack(self, evidence_request_id: str) -> EvidencePack: ...


@runtime_checkable
class LLMClient(Protocol):
    model_name: str
    max_output_tokens: int
    temperature: float

    async def generate(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None
    ) -> str: ...


@runtime_checkable
class DocumentPlanner(Protocol):
    def plan(
        self, request: DocumentRequest, evidence_pack: EvidencePack | None = None
    ) -> DocumentPlan: ...


@runtime_checkable
class EvidenceValidator(Protocol):
    def validate_section(
        self, section_markdown: str, evidence_pack: EvidencePack
    ) -> list[str]: ...


@runtime_checkable
class DocumentAssembler(Protocol):
    def assemble(self, draft: DocumentDraft) -> str: ...


@runtime_checkable
class DocumentRepository(Protocol):
    async def create_run(
        self,
        *,
        run_id: str,
        document_title: str,
        system_id: str,
        plan: dict[str, object],
        status: str,
    ) -> dict[str, object]: ...

    async def get_run(self, run_id: str) -> dict[str, object]: ...

    async def list_runs(self, limit: int = 50) -> list[dict[str, object]]: ...

    async def update_run(
        self,
        run_id: str,
        *,
        plan: dict[str, object] | None = None,
        status: str | None = None,
        completed_at: str | None = None,
        export_artifact: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    async def get_sections(self, run_id: str) -> list[dict[str, object]]: ...

    async def get_section(
        self, run_id: str, section_name: str
    ) -> dict[str, object]: ...


@runtime_checkable
class RetrievalPassStore(Protocol):
    async def next_pass_number(self, run_id: str, section_name: str) -> int: ...

    async def create_pass(
        self,
        *,
        run_id: str,
        section_name: str,
        pass_number: int,
        query: str,
        evidence_request_id: str | None,
        status: str,
    ) -> dict[str, object]: ...

    async def complete_pass(
        self,
        *,
        pass_id: str,
        evidence_request_id: str,
        status: str = "completed",
    ) -> dict[str, object]: ...

    async def get_latest_completed_pass(
        self,
        run_id: str,
        section_name: str,
    ) -> dict[str, object] | None: ...

    async def list_passes_for_run(self, run_id: str) -> list[dict[str, object]]: ...
