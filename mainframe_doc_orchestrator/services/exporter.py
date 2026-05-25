from __future__ import annotations

from mainframe_doc_orchestrator.assembler import MarkdownDocumentAssembler
from mainframe_doc_orchestrator.models import DocumentDraft


class DocumentExporter:
    def __init__(self, assembler: MarkdownDocumentAssembler | None = None) -> None:
        self.assembler = assembler or MarkdownDocumentAssembler()

    def export_markdown(self, draft: DocumentDraft) -> str:
        return self.assembler.assemble(draft)
