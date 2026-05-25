from __future__ import annotations
from dataclasses import asdict
from typing import Any
from mainframe_doc_orchestrator.assembler import MarkdownDocumentAssembler
from mainframe_doc_orchestrator.contracts import (
    DocumentAssembler,
    DocumentPlanner,
    EvidenceValidator,
    LLMClient,
    RetrievalClient,
)
from mainframe_doc_orchestrator.models import (
    DocumentDraft,
    DocumentRequest,
    EvidencePack,
    SectionDraft,
)
from mainframe_doc_orchestrator.planner import MainframeDocumentPlanner
from mainframe_doc_orchestrator.prompt_library import PROMPTS, render_template
from mainframe_doc_orchestrator.validator import MainframeEvidenceValidator


class DocumentOrchestrator:
    def __init__(
        self,
        retrieval_client: RetrievalClient,
        llm_client: LLMClient,
        planner: DocumentPlanner | None = None,
        validator: EvidenceValidator | None = None,
        assembler: DocumentAssembler | None = None,
    ) -> None:
        self.retrieval_client = retrieval_client
        self.llm_client = llm_client
        self.planner = planner or MainframeDocumentPlanner()
        self.validator = validator or MainframeEvidenceValidator()
        self.assembler = assembler or MarkdownDocumentAssembler()

    def run(self, request: DocumentRequest) -> DocumentDraft:
        evidence_pack = self._get_evidence_pack(request)
        plan = self.planner.plan(request, evidence_pack)
        section_drafts: list[SectionDraft] = []
        for section in plan.sections:
            section_markdown = self._generate_section(
                request, evidence_pack, section.section_name
            )
            notes = self.validator.validate_section(section_markdown, evidence_pack)
            section_drafts.append(
                SectionDraft(
                    section.section_id,
                    section.section_name,
                    section.title,
                    section_markdown,
                    evidence_pack.evidence_request_id,
                    evidence_pack.confidence,
                    notes,
                )
            )
        draft = DocumentDraft(
            request.run_id,
            request.system_id,
            f"System Appreciation Document - {request.system_id}",
            section_drafts,
            "",
            evidence_pack.confidence,
            {
                "plan_id": plan.plan_id,
                "evidence_request_id": evidence_pack.evidence_request_id,
            },
        )
        draft.rendered_markdown = self.assembler.assemble(draft)
        return draft

    def _get_evidence_pack(self, request: DocumentRequest) -> EvidencePack:
        if request.retrieval_request is not None:
            return self.retrieval_client.retrieve(request.retrieval_request)
        if "evidence_request_id" in request.metadata:
            return self.retrieval_client.fetch_evidence_pack(
                str(request.metadata["evidence_request_id"])
            )
        raise ValueError(
            "DocumentRequest must include retrieval_request or evidence_request_id metadata."
        )

    def _generate_section(
        self, request: DocumentRequest, evidence_pack: EvidencePack, section_name: str
    ) -> str:
        prompt_bundle = PROMPTS[section_name]
        context = {
            "system_id": request.system_id,
            "section_name": section_name,
            "question": evidence_pack.question,
            "user_role": request.user_role,
            "prior_pass_count": len(request.prior_request_ids),
            "supporting_chunks": evidence_pack.supporting_chunks,
            "chunk_contents": {
                k: asdict(v) for k, v in evidence_pack.chunk_contents.items()
            },
            "graph_paths": [
                self._path_as_dict(path) for path in evidence_pack.graph_paths
            ],
            "supporting_data": evidence_pack.supporting_data,
            "evidence_items": [asdict(item) for item in evidence_pack.evidence_items],
            "confidence": evidence_pack.confidence,
        }
        user_prompt = render_template(prompt_bundle["user"], context)
        return self.llm_client.generate(
            system_prompt=prompt_bundle["system"],
            user_prompt=user_prompt,
        )

    @staticmethod
    def _path_as_dict(path: Any) -> dict[str, Any]:
        return {
            "path_id": path.path_id,
            "path_label": path.path_label,
            "supporting_chunks": path.supporting_chunks,
            "nodes": [asdict(node) for node in path.nodes],
            "edges": [asdict(edge) for edge in path.edges],
        }
