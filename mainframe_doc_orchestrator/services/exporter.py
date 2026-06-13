from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from mainframe_doc_orchestrator.assembler import MarkdownDocumentAssembler
from mainframe_doc_orchestrator.models import DocumentDraft

_UNSAFE_CHARS = re.compile(r"[^\w\- ]+")
_MULTI_SPACE = re.compile(r"\s+")


def _safe_filename(value: str) -> str:
    """Reduce *value* to a filesystem-safe token (spaces → underscores)."""
    cleaned = _UNSAFE_CHARS.sub("", value)
    return _MULTI_SPACE.sub("_", cleaned).strip("_")


class DocumentExporter:
    """Renders a DocumentDraft into the requested output format and saves it
    to *output_dir* on disk.

    To add a new format:
      1. Add an ``export_<format>`` method below.
      2. Register it in ``_FORMAT_HANDLERS`` inside ``__init__``.
      3. Add the matching file extension in ``_FORMAT_EXTENSIONS``.
    """

    _FORMAT_EXTENSIONS: dict[str, str] = {
        "markdown": ".md",
        # "pdf": ".pdf",
    }

    def __init__(
        self,
        assembler: MarkdownDocumentAssembler | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.assembler = assembler or MarkdownDocumentAssembler()
        if output_dir is None:
            from mainframe_doc_orchestrator.settings import get_settings
            output_dir = get_settings().export_output_dir
        self.output_dir = Path(output_dir)
        self._FORMAT_HANDLERS: dict[str, Callable[[DocumentDraft], str]] = {
            "markdown": self.export_markdown,
            # "pdf": self.export_pdf,
        }

    def export(self, draft: DocumentDraft, output_format: str) -> str:
        """Dispatch to the correct format handler.

        Raises ``ValueError`` for unsupported formats so the caller gets a
        clear message without needing to know the handler map.
        """
        handler = self._FORMAT_HANDLERS.get(output_format)
        if handler is None:
            supported = ", ".join(sorted(self._FORMAT_HANDLERS))
            raise ValueError(
                f"Unsupported export format '{output_format}'. "
                f"Supported formats: {supported}."
            )
        return handler(draft)

    def save_to_disk(
        self, content: str | bytes, title: str, run_id: str, fmt: str
    ) -> str:
        """Write *content* to ``output_dir/<title>_<run_id><ext>`` and return
        the resolved absolute path as a string.

        The directory is created if it does not exist.
        """
        ext = self._FORMAT_EXTENSIONS.get(fmt, f".{fmt}")
        filename = f"{_safe_filename(title)}_{run_id}{ext}"
        dest = self.output_dir / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with dest.open(mode, encoding=encoding) as fh:
            fh.write(content)
        return str(dest.resolve())

    def export_markdown(self, draft: DocumentDraft) -> str:
        return self.assembler.assemble(draft)

    # ------------------------------------------------------------------
    # PDF export — uncomment and implement when weasyprint is added.
    # Requirements: pip install weasyprint; brew install weasyprint (macOS)
    # ------------------------------------------------------------------
    # def export_pdf(self, draft: DocumentDraft) -> bytes:
    #     import markdown as _md
    #     import weasyprint
    #     md_content = self.assembler.assemble(draft)
    #     html = _md.markdown(md_content, extensions=["tables", "fenced_code"])
    #     full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
    #     <style>body{{font-family:sans-serif;max-width:900px;margin:2rem auto;}}</style>
    #     </head><body>{html}</body></html>"""
    #     return weasyprint.HTML(string=full_html).write_pdf()
