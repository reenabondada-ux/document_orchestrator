from __future__ import annotations
from mainframe_doc_orchestrator.models import DocumentDraft
from mainframe_doc_orchestrator.prompt_library import (
    DEFAULT_ASSEMBLY_ORDER,
    ASSEMBLY_ORDERS,
)


class MarkdownDocumentAssembler:
    def assemble(self, draft: DocumentDraft) -> str:
        # Resolve the reader-facing assembly order for this document type.
        document_type: str = draft.metadata.get("plan", {}).get(
            "document_type", ""
        ) or draft.metadata.get("document_type", "")
        assembly_order = ASSEMBLY_ORDERS.get(document_type, DEFAULT_ASSEMBLY_ORDER)
        order_index = {name: i for i, name in enumerate(assembly_order)}
        sections = sorted(
            draft.sections,
            key=lambda s: order_index.get(s.section_name, len(assembly_order)),
        )
        lines = [
            f"# {draft.title}",
            "",
            f"- Run ID: `{draft.run_id}`",
            f"- System ID: `{draft.system_id}`",
            f"- Confidence: `{draft.confidence:.2f}`",
            "",
            "## Table of Contents",
        ]
        for section in sections:
            lines.append(f"- [{section.title}](#{_anchor(section.title)})")
        lines.append("")
        for section in sections:
            lines += [f"## {section.title}", "", section.content_markdown.strip(), ""]
            if section.notes:
                lines.append("**Notes**")
                lines += [f"- {note}" for note in section.notes]
                lines.append("")
        return "\n".join(lines).strip() + "\n"


def _anchor(title: str) -> str:
    return title.lower().replace(" ", "-").replace("/", "-")
