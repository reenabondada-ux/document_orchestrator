from __future__ import annotations

from typing import Protocol, runtime_checkable
from mainframe_doc_orchestrator.models import DocumentDraft, DocumentPlan, DocumentRequest, EvidencePack, RetrievalRequest

@runtime_checkable
class RetrievalClient(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> EvidencePack: ...
    async def fetch_evidence_pack(self, evidence_request_id: str) -> EvidencePack: ...

@runtime_checkable
class LLMClient(Protocol):
    model_name: str
    max_output_tokens: int
    temperature: float
    async def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str: ...

@runtime_checkable
class DocumentPlanner(Protocol):
    def plan(self, request: DocumentRequest, evidence_pack: EvidencePack | None = None) -> DocumentPlan: ...

@runtime_checkable
class EvidenceValidator(Protocol):
    def validate_section(self, section_markdown: str, evidence_pack: EvidencePack) -> list[str]: ...

@runtime_checkable
class DocumentAssembler(Protocol):
    def assemble(self, draft: DocumentDraft) -> str: ...
