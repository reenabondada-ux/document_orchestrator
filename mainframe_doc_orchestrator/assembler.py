from __future__ import annotations
from mainframe_doc_orchestrator.models import DocumentDraft
class MarkdownDocumentAssembler:
    def assemble(self, draft: DocumentDraft) -> str:
        lines = [f"# {draft.title}", "", f"- Request ID: `{draft.request_id}`", f"- System ID: `{draft.system_id}`", f"- Confidence: `{draft.confidence:.2f}`", "", "## Table of Contents"]
        for section in draft.sections: lines.append(f"- [{section.title}](#{_anchor(section.title)})")
        lines.append("")
        for section in draft.sections:
            lines += [f"## {section.title}", "", section.content_markdown.strip(), ""]
            if section.notes:
                lines.append("**Notes**")
                lines += [f"- {note}" for note in section.notes]
                lines.append("")
        return "\n".join(lines).strip() + "\n"

def _anchor(title: str) -> str:
    return title.lower().replace(" ", "-").replace("/", "-")
