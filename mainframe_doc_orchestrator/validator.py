from __future__ import annotations

import re

from mainframe_doc_orchestrator.models import EvidencePack


# Match asset-like identifiers only (e.g. JCL__JOB1, COBOL__PROG_A).
# Requiring "__" avoids treating generic uppercase prose tokens (JCL, API, SQL)
# as candidate asset IDs.
ASSET_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*__[A-Z0-9_]+\b")


class MainframeEvidenceValidator:
    def validate_section(
        self, section_markdown: str, evidence_pack: EvidencePack
    ) -> list[str]:
        warnings: list[str] = []
        if not section_markdown.strip():
            warnings.append("Section is empty.")
        if evidence_pack.confidence < 0.4:
            warnings.append(f"Low retrieval confidence: {evidence_pack.confidence:.2f}")
        if not evidence_pack.supporting_chunks:
            warnings.append("No supporting chunks returned.")
        if not evidence_pack.graph_paths:
            warnings.append("No graph paths returned.")
        claimed_ids = ASSET_ID_PATTERN.findall(section_markdown)
        known_ids = {
            content.asset_id for content in evidence_pack.chunk_contents.values()
        }
        unknown = [item for item in claimed_ids if item not in known_ids]
        if unknown and known_ids:
            warnings.append(
                "Section mentions identifiers not seen in the supporting chunks: "
                + ", ".join(sorted(set(unknown)))
            )
        return warnings
