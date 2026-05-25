from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mainframe_doc_orchestrator.models import DocumentRequest, DocumentSection, EvidencePack
from mainframe_doc_orchestrator.prompt_library import PROMPTS, render_template


class PromptEngine:
    def build_section_prompts(
        self,
        *,
        request: DocumentRequest,
        section: DocumentSection,
        evidence_pack: EvidencePack,
        prior_pass_count: int,
    ) -> tuple[str, str]:
        prompt_bundle = PROMPTS[section.section_name]
        context = {
            "system_id": request.system_id,
            "section_name": section.section_name,
            "section_title": section.title,
            "objective": section.objective,
            "retrieval_hint": section.retrieval_hint,
            "question": evidence_pack.question,
            "user_role": request.user_role,
            "prior_pass_count": prior_pass_count,
            "supporting_chunks": evidence_pack.supporting_chunks,
            "chunk_contents": {k: asdict(v) for k, v in evidence_pack.chunk_contents.items()},
            "graph_paths": [self._path_as_dict(path) for path in evidence_pack.graph_paths],
            "supporting_data": evidence_pack.supporting_data,
            "evidence_items": [asdict(item) for item in evidence_pack.evidence_items],
            "confidence": evidence_pack.confidence,
        }
        user_prompt = render_template(prompt_bundle["user"], context)
        return prompt_bundle["system"], user_prompt

    @staticmethod
    def _path_as_dict(path: Any) -> dict[str, Any]:
        return {
            "path_id": path.path_id,
            "path_label": path.path_label,
            "supporting_chunks": path.supporting_chunks,
            "nodes": [asdict(node) for node in path.nodes],
            "edges": [asdict(edge) for edge in path.edges],
        }
