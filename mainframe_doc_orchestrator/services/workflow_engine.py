"""Async document workflow engine.

All public methods are coroutines and must be awaited.  Repository and client
calls are never made synchronously; the event loop is never blocked.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from mainframe_doc_orchestrator.models import (
    DocumentDraft,
    DocumentPlan,
    DocumentRequest,
    DocumentSection,
    EvidencePack,
    RetrievalFilters,
    RetrievalRequest,
    SectionDraft,
)
from mainframe_doc_orchestrator.planner import MainframeDocumentPlanner
from mainframe_doc_orchestrator.validator import MainframeEvidenceValidator
from mainframe_doc_orchestrator.services.draft_writer import SectionDraftWriter
from mainframe_doc_orchestrator.services.exporter import DocumentExporter


class DocumentWorkflowEngine:
    def __init__(
        self,
        *,
        retrieval_client,
        llm_client,
        document_repository,
        retrieval_pass_repository,
        planner: MainframeDocumentPlanner | None = None,
        validator: MainframeEvidenceValidator | None = None,
        exporter: DocumentExporter | None = None,
        draft_writer: SectionDraftWriter | None = None,
    ) -> None:
        self.retrieval_client = retrieval_client
        self.llm_client = llm_client
        self.document_repository = document_repository
        self.retrieval_pass_repository = retrieval_pass_repository
        self.planner = planner or MainframeDocumentPlanner()
        self.validator = validator or MainframeEvidenceValidator()
        self.exporter = exporter or DocumentExporter()
        self.draft_writer = draft_writer or SectionDraftWriter(
            llm_client=llm_client,
        )

    async def create_document_run(
        self, request: DocumentRequest, document_title: str | None = None
    ) -> dict[str, Any]:
        plan = self.planner.plan(request)
        plan_state = self._plan_to_state(
            plan=plan, request=request, document_title=document_title
        )
        run = await self.document_repository.create_run(
            run_id=request.run_id,
            document_title=document_title
            or f"System Appreciation Document - {request.system_id}",
            system_id=request.system_id,
            plan=plan_state,
            status="created",
        )
        return run

    async def generate_section(
        self, run_id: str, section_name: str | None = None
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        plan = run["plan"]
        request = self._document_request_from_plan(plan, run_id)
        sections = plan.get("sections", [])
        section_state = self._select_section_state(sections, section_name)
        if section_state is None:
            raise ValueError("No matching section available for generation.")

        document_section = self._document_section_from_state(section_state)
        prior_pass_count = await self.retrieval_pass_repository.next_pass_number(
            run_id, document_section.section_name
        )
        retrieval_request = self._build_retrieval_request(
            request, document_section, plan
        )

        # Crash-recovery: if a completed pass already exists with an
        # evidence_request_id, the previous run completed retrieval but
        # crashed before finishing draft writing.  Re-fetch the pack via
        # GET /v1/evidence-packs/{id} instead of triggering a new retrieval.
        existing_pass = await self.retrieval_pass_repository.get_latest_completed_pass(
            run_id, document_section.section_name
        )
        if existing_pass and existing_pass.get("evidence_request_id"):
            retrieval_pass = existing_pass
            evidence_pack = await self.retrieval_client.fetch_evidence_pack(
                existing_pass["evidence_request_id"]
            )
        else:
            retrieval_pass = await self.retrieval_pass_repository.create_pass(
                run_id=run_id,
                section_name=document_section.section_name,
                pass_number=prior_pass_count,
                query=retrieval_request.query,
                evidence_request_id=None,
                status="in_progress",
            )
            evidence_pack = await self.retrieval_client.retrieve(retrieval_request)
            await self.retrieval_pass_repository.complete_pass(
                pass_id=retrieval_pass["pass_id"],
                evidence_request_id=evidence_pack.evidence_request_id,
                status="completed",
            )

        answer_summary = self._summarize_evidence_pack(evidence_pack)
        section_markdown = await self.draft_writer.write(
            request=request,
            section=document_section,
            evidence_pack=evidence_pack,
            prior_pass_count=prior_pass_count - 1,
        )
        notes = self.validator.validate_section(section_markdown, evidence_pack)
        section_state.update(
            {
                "status": "review_ready",
                "draft_markdown": section_markdown,
                "evidence_request_id": evidence_pack.evidence_request_id,
                "confidence": evidence_pack.confidence,
                "notes": notes,
                "retrieval_pass_id": retrieval_pass["pass_id"],
                "retrieval_pass_number": prior_pass_count,
                "evidence_overview": answer_summary,
                "updated_at": self._now_iso(),
            }
        )
        run_status = self._derive_run_status(sections)
        await self.document_repository.update_run(run_id, plan=plan, status=run_status)
        return await self.get_section(run_id, document_section.section_name)

    async def regenerate_section(
        self, run_id: str, section_name: str
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        plan = run["plan"]
        section_state = self._get_section_state(plan, section_name)
        section_state["status"] = "pending"
        section_state["updated_at"] = self._now_iso()
        await self.document_repository.update_run(
            run_id,
            plan=plan,
            status=self._derive_run_status(plan.get("sections", [])),
        )
        return await self.generate_section(run_id, section_name)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await self.document_repository.get_run(run_id)

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self.document_repository.list_runs(limit=limit)

    async def list_sections(self, run_id: str) -> list[dict[str, Any]]:
        return await self.document_repository.get_sections(run_id)

    async def get_section(self, run_id: str, section_name: str) -> dict[str, Any]:
        return await self.document_repository.get_section(run_id, section_name)

    async def generate_next_pending_section(self, run_id: str) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        sections = run["plan"].get("sections", [])
        next_section = next((s for s in sections if s.get("status") == "pending"), None)
        if next_section is None:
            raise ValueError("No pending sections left to generate.")
        return await self.generate_section(run_id, next_section["section_name"])

    async def approve_section(
        self, run_id: str, section_name: str, notes: str | None = None
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        plan = run["plan"]
        section_state = self._get_section_state(plan, section_name)
        section_state["status"] = "approved"
        if notes:
            section_state.setdefault("approval_notes", [])
            section_state["approval_notes"].append(notes)
        section_state["updated_at"] = self._now_iso()
        await self.document_repository.update_run(
            run_id,
            plan=plan,
            status=self._derive_run_status(plan.get("sections", [])),
        )
        return await self.get_section(run_id, section_name)

    async def export_document(
        self, run_id: str, output_format: str = "markdown"
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        draft = self._draft_from_plan(run)
        if output_format == "markdown":
            exported = self.exporter.export_markdown(draft)
        else:
            raise ValueError(f"Unsupported export format: {output_format}")
        await self.document_repository.update_run(
            run_id,
            status="exported",
            completed_at=self._now_iso(),
            export_artifact={"format": output_format, "content": exported},
        )
        return {"run_id": run_id, "format": output_format, "content": exported}

    async def get_events(self, run_id: str) -> list[dict[str, Any]]:
        run = await self.document_repository.get_run(run_id)
        passes = await self.retrieval_pass_repository.list_passes_for_run(run_id)
        events: list[dict[str, Any]] = [
            {
                "event_type": "run_created",
                "timestamp": run["created_at"],
                "status": run["status"],
            },
        ]
        for item in passes:
            events.append(
                {
                    "event_type": "retrieval_pass",
                    "timestamp": item["created_at"],
                    "section_name": item["section_name"],
                    "pass_number": item["pass_number"],
                    "status": item["status"],
                    "evidence_request_id": item.get("evidence_request_id"),
                }
            )
        if run.get("completed_at"):
            events.append(
                {
                    "event_type": "run_completed",
                    "timestamp": run["completed_at"],
                    "status": run["status"],
                }
            )
        return events

    # ------------------------------------------------------------------
    # Private helpers — all pure / synchronous
    # ------------------------------------------------------------------

    def _plan_to_state(
        self,
        *,
        plan: DocumentPlan,
        request: DocumentRequest,
        document_title: str | None,
    ) -> dict[str, Any]:
        plan_dict = asdict(plan)
        plan_dict["document_title"] = (
            document_title or f"System Appreciation Document - {request.system_id}"
        )
        plan_dict["document_style"] = request.document_style
        plan_dict["user_role"] = request.user_role
        plan_dict["topic"] = request.topic
        plan_dict["section_order"] = request.section_order
        plan_dict["metadata"] = {**plan_dict.get("metadata", {}), **request.metadata}
        for section in plan_dict["sections"]:
            section.setdefault("status", "pending")
            section.setdefault("draft_markdown", "")
            section.setdefault("confidence", 0.0)
            section.setdefault("notes", [])
            section.setdefault("evidence_request_id", None)
            section.setdefault("retrieval_pass_id", None)
            section.setdefault("retrieval_pass_number", None)
            section.setdefault("updated_at", self._now_iso())
        return plan_dict

    def _document_request_from_plan(
        self, plan: dict[str, Any], run_id: str
    ) -> DocumentRequest:
        filters_data = plan.get("metadata", {}).get("filters", {})
        retrieval_request_data = plan.get("metadata", {}).get("retrieval_request")
        retrieval_request = None
        if retrieval_request_data:
            retrieval_request = RetrievalRequest(
                query=retrieval_request_data.get("query", plan.get("topic", "")),
                section_name=retrieval_request_data.get(
                    "section_name", "batch_flow_overview"
                ),
                system_id=plan["system_id"],
                top_k_chunks=int(retrieval_request_data.get("top_k_chunks", 8)),
                top_k_paths=int(retrieval_request_data.get("top_k_paths", 5)),
                filters=RetrievalFilters(
                    asset_types=list(filters_data.get("asset_types", [])),
                    asset_ids=list(filters_data.get("asset_ids", [])),
                    domains=list(filters_data.get("domains", [])),
                ),
            )
        return DocumentRequest(
            run_id=run_id,
            system_id=plan["system_id"],
            user_role=plan.get("user_role", "analyst"),
            document_style=plan.get("document_style", "system_appreciation"),
            output_format=plan.get("metadata", {}).get("output_format", "markdown"),
            topic=plan.get("topic", ""),
            section_order=list(plan.get("section_order", [])),
            prior_run_ids=list(plan.get("metadata", {}).get("prior_run_ids", [])),
            retrieval_request=retrieval_request,
            metadata=plan.get("metadata", {}),
        )

    def _build_retrieval_request(
        self, request: DocumentRequest, section: DocumentSection, plan: dict[str, Any]
    ) -> RetrievalRequest:
        metadata = plan.get("metadata", {})
        existing = request.retrieval_request
        if existing and existing.section_name == section.section_name:
            return existing
        filters_data = metadata.get("filters", {})
        filters = RetrievalFilters(
            asset_types=list(filters_data.get("asset_types", [])),
            asset_ids=list(filters_data.get("asset_ids", [])),
            domains=list(filters_data.get("domains", [])),
        )
        query = request.topic or plan.get("document_title", request.system_id)
        query = (
            f"{query}. Section focus: {section.title}. {section.retrieval_hint}".strip()
        )
        return RetrievalRequest(
            query=query,
            section_name=section.section_name,
            system_id=request.system_id,
            top_k_chunks=int(metadata.get("top_k_chunks", 8)),
            top_k_paths=int(metadata.get("top_k_paths", 15)),
            filters=filters,
        )

    @staticmethod
    def _select_section_state(
        sections: list[dict[str, Any]], section_name: str | None
    ) -> dict[str, Any] | None:
        if section_name:
            return next(
                (s for s in sections if s.get("section_name") == section_name), None
            )
        return next((s for s in sections if s.get("status") == "pending"), None)

    @staticmethod
    def _document_section_from_state(section_state: dict[str, Any]) -> DocumentSection:
        return DocumentSection(
            section_id=section_state["section_id"],
            section_name=section_state["section_name"],
            title=section_state["title"],
            objective=section_state.get("objective", ""),
            prompt_key=section_state.get("prompt_key", section_state["section_name"]),
            required_evidence=list(section_state.get("required_evidence", [])),
            retrieval_hint=section_state.get("retrieval_hint", ""),
            min_chunks=int(section_state.get("min_chunks", 1)),
            min_paths=int(section_state.get("min_paths", 0)),
        )

    @staticmethod
    def _get_section_state(plan: dict[str, Any], section_name: str) -> dict[str, Any]:
        section = next(
            (
                s
                for s in plan.get("sections", [])
                if s.get("section_name") == section_name
            ),
            None,
        )
        if section is None:
            raise KeyError(f"Section not found: {section_name}")
        return section

    @staticmethod
    def _derive_run_status(sections: list[dict[str, Any]]) -> str:
        statuses = [str(section.get("status", "pending")) for section in sections]
        if all(status == "approved" for status in statuses) and statuses:
            return "approved"
        if any(status == "review_ready" for status in statuses):
            return "review_ready"
        if any(status == "in_progress" for status in statuses):
            return "in_progress"
        return "created"

    def _draft_from_plan(self, run: dict[str, Any]) -> DocumentDraft:
        plan = run["plan"]
        sections = []
        for section in plan.get("sections", []):
            if section.get("draft_markdown"):
                sections.append(
                    SectionDraft(
                        section_id=section["section_id"],
                        section_name=section["section_name"],
                        title=section["title"],
                        content_markdown=section.get("draft_markdown", ""),
                        evidence_request_id=section.get("evidence_request_id") or "",
                        confidence=float(section.get("confidence", 0.0)),
                        notes=list(section.get("notes", [])),
                    )
                )
        draft = DocumentDraft(
            run_id=run["run_id"],
            system_id=run["system_id"],
            title=run["document_title"],
            sections=sections,
            rendered_markdown="",
            confidence=0.0,
            metadata={"plan": plan, "run_status": run["status"]},
        )
        draft.rendered_markdown = self.exporter.export_markdown(draft)
        return draft

    @staticmethod
    def _summarize_evidence_pack(evidence_pack: EvidencePack) -> str:
        chunk_ids = ", ".join(evidence_pack.supporting_chunks[:5])
        path_ids = ", ".join(path.path_id for path in evidence_pack.graph_paths[:5])
        return (
            f"Retrieved {len(evidence_pack.supporting_chunks)} chunks and "
            f"{len(evidence_pack.graph_paths)} graph paths. "
            f"Key chunks: {chunk_ids}. Key paths: {path_ids}."
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
