"""Async document workflow engine.

All public methods are coroutines and must be awaited.  Repository and client
calls are never made synchronously; the event loop is never blocked.
"""

from __future__ import annotations

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
from mainframe_doc_orchestrator.planner import (
    DOCUMENT_TYPE_LABELS,
    MainframeDocumentPlanner,
)
from mainframe_doc_orchestrator.validator import MainframeEvidenceValidator
from mainframe_doc_orchestrator.services.draft_writer import SectionDraftWriter
from mainframe_doc_orchestrator.services.exporter import DocumentExporter
from mainframe_doc_orchestrator.serialization import (
    sections_map_to_stored_sections_list,
    stored_sections_list_to_sections_map,
)


SUMMARY_PREVIEW_LIMIT = 5


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

    async def create_document_run(self, request: DocumentRequest) -> dict[str, Any]:
        plan = self.planner.plan(request)
        plan_dict = self._plan_to_dict(plan=plan, request=request)
        run = await self.document_repository.create_run(
            run_id=request.run_id,
            document_title=plan_dict["document_title"],
            system_id=request.system_id,
            plan=plan_dict,
            status="created",
        )
        return run

    async def generate_section(
        self, run_id: str, section_name: str | None = None
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        plan_dict = run["plan"]
        request = self._document_request_from_plan(plan_dict, run_id)
        sections = stored_sections_list_to_sections_map(plan_dict.get("sections", []))

        section = self._select_section(sections, section_name)
        if section is None:
            raise ValueError("No matching section available for generation.")

        # Dependency guard: Phase 2 sections require all depends_on sections to be
        # review_ready or approved before generation can proceed.
        if section.depends_on:
            not_ready = [
                dep
                for dep in section.depends_on
                if sections[dep].status not in {"review_ready", "approved"}
            ]
            if not_ready:
                raise ValueError(
                    f"Section '{section.section_name}' depends on sections that "
                    f"are not yet review_ready or approved: {not_ready}"
                )

        # Collect prior drafts for synthesis sections.
        prior_drafts: dict[str, str] | None = None
        if section.depends_on:
            prior_drafts = {
                dep: sections[dep].draft_markdown for dep in section.depends_on
            }

        prior_pass_count = await self.retrieval_pass_repository.next_pass_number(
            run_id, section.section_name
        )
        retrieval_request = self._build_retrieval_request(section, sections, plan_dict)

        # Crash-recovery: if a completed pass already exists with an
        # evidence_request_id, the previous run completed retrieval but
        # crashed before finishing draft writing.  Re-fetch the pack via
        # GET /v1/evidence-packs/{id} instead of triggering a new retrieval.
        existing_pass = await self.retrieval_pass_repository.get_latest_completed_pass(
            run_id, section.section_name
        )
        if existing_pass and existing_pass.get("evidence_request_id"):
            retrieval_pass = existing_pass
            evidence_pack = await self.retrieval_client.fetch_evidence_pack(
                existing_pass["evidence_request_id"]
            )
        else:
            retrieval_pass = await self.retrieval_pass_repository.create_pass(
                run_id=run_id,
                section_name=section.section_name,
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
            section=section,
            evidence_pack=evidence_pack,
            prior_pass_count=prior_pass_count - 1,
            prior_drafts=prior_drafts,
        )
        notes = self.validator.validate_section(section_markdown, evidence_pack)

        # Update section with results
        section.status = "review_ready"
        section.draft_markdown = section_markdown
        section.evidence_request_id = evidence_pack.evidence_request_id
        section.confidence = evidence_pack.confidence
        section.notes = notes
        section.retrieval_pass_id = retrieval_pass["pass_id"]
        section.retrieval_pass_number = prior_pass_count
        section.evidence_overview = answer_summary
        section.discovered_asset_ids = self._harvest_asset_ids(
            evidence_pack, section.cascade_node_types
        )
        section.updated_at = self._now_iso()

        # Persist updated plan
        plan_dict["sections"] = sections_map_to_stored_sections_list(sections)
        run_status = self._derive_run_status(sections)
        await self.document_repository.update_run(
            run_id, plan=plan_dict, status=run_status
        )
        return await self.get_section(run_id, section.section_name)

    async def regenerate_section(
        self, run_id: str, section_name: str
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        plan_dict = run["plan"]
        sections = stored_sections_list_to_sections_map(plan_dict.get("sections", []))
        sections[section_name].status = "pending"
        sections[section_name].updated_at = self._now_iso()
        plan_dict["sections"] = sections_map_to_stored_sections_list(sections)
        await self.document_repository.update_run(
            run_id,
            plan=plan_dict,
            status=self._derive_run_status(sections),
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
        plan_dict = run["plan"]
        sections = stored_sections_list_to_sections_map(plan_dict.get("sections", []))
        next_section = next(
            (s for s in sections.values() if s.status == "pending"), None
        )
        if next_section is None:
            raise ValueError("No pending sections left to generate.")
        return await self.generate_section(run_id, next_section.section_name)

    async def approve_section(
        self, run_id: str, section_name: str, notes: str | None = None
    ) -> dict[str, Any]:
        run = await self.document_repository.get_run(run_id)
        plan_dict = run["plan"]
        sections = stored_sections_list_to_sections_map(plan_dict.get("sections", []))
        sections[section_name].status = "approved"
        if notes:
            sections[section_name].approval_notes.append(notes)
        sections[section_name].updated_at = self._now_iso()
        plan_dict["sections"] = sections_map_to_stored_sections_list(sections)
        await self.document_repository.update_run(
            run_id,
            plan=plan_dict,
            status=self._derive_run_status(sections),
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

    def _plan_to_dict(
        self,
        *,
        plan: DocumentPlan,
        request: DocumentRequest,
    ) -> dict[str, Any]:
        """Convert DocumentPlan to dict for JSON storage."""
        label = DOCUMENT_TYPE_LABELS.get(
            request.document_type,
            request.document_type.replace("_", " ").title(),
        )
        # Serialize sections to a list for JSON storage
        sections_list = sections_map_to_stored_sections_list(
            {s.section_name: s for s in plan.sections}
        )
        return {
            "plan_id": plan.plan_id,
            "system_id": plan.system_id,
            "run_id": plan.run_id,
            "document_title": f"{request.system_id} — {label}",
            "document_type": request.document_type,
            "user_role": request.user_role,
            "topic": request.topic,
            "section_order": request.section_order,
            "sections": sections_list,
            "metadata": {**plan.metadata, **request.metadata},
        }

    def _document_request_from_plan(
        self, plan: dict[str, Any], run_id: str
    ) -> DocumentRequest:
        return DocumentRequest(
            run_id=run_id,
            system_id=plan["system_id"],
            user_role=plan.get("user_role", "analyst"),
            document_type=plan.get("document_type", "system_appreciation"),
            output_format=plan.get("metadata", {}).get("output_format", "markdown"),
            topic=plan.get("topic", ""),
            section_order=list(plan.get("section_order", [])),
            prior_run_ids=list(plan.get("metadata", {}).get("prior_run_ids", [])),
            retrieval_request=None,
            metadata=plan.get("metadata", {}),
        )

    def _build_retrieval_request(
        self,
        section: DocumentSection,
        sections: dict[str, DocumentSection],
        plan_dict: dict[str, Any],
    ) -> RetrievalRequest:
        metadata = plan_dict.get("metadata", {})
        initial_request_filters = metadata.get("filters", {})
        # Section-level asset_type_filter takes precedence over plan-level filters that holds initial request values.
        asset_types = (
            list(section.asset_type_filter)
            if section.asset_type_filter
            else list(initial_request_filters.get("asset_types", []))
        )
        # Cascade: collect asset IDs discovered by upstream sections.
        cascaded_asset_ids: list[str] = []
        if section.cascade_from:
            for upstream_name in section.cascade_from:
                upstream_section = sections.get(upstream_name)
                if upstream_section is not None:
                    for asset_ids in upstream_section.discovered_asset_ids.values():
                        cascaded_asset_ids.extend(asset_ids)
        filters = RetrievalFilters(
            asset_types=asset_types,
            asset_ids=cascaded_asset_ids
            or list(initial_request_filters.get("asset_ids", [])),
            domains=list(initial_request_filters.get("domains", [])),
        )
        system_id = plan_dict["system_id"]
        query = plan_dict.get("topic", "") or plan_dict.get("document_title", system_id)
        query = (
            f"{query}. Section focus: {section.title}. {section.retrieval_hint}".strip()
        )
        return RetrievalRequest(
            query=query,
            section_name=section.section_name,
            system_id=system_id,
            top_k_chunks=int(metadata.get("top_k_chunks", 8)),
            top_k_paths=int(metadata.get("top_k_paths", 15)),
            filters=filters,
        )

    @staticmethod
    def _select_section(
        sections: dict[str, DocumentSection], section_name: str | None
    ) -> DocumentSection | None:
        """Select section by name, or first pending section if no name given."""
        if section_name:
            return sections.get(section_name)
        return next((s for s in sections.values() if s.status == "pending"), None)

    @staticmethod
    def _summarize_evidence_pack(evidence_pack: EvidencePack) -> str:
        chunk_ids = ", ".join(evidence_pack.supporting_chunks[:SUMMARY_PREVIEW_LIMIT])
        path_ids = ", ".join(
            path.path_id for path in evidence_pack.graph_paths[:SUMMARY_PREVIEW_LIMIT]
        )
        return (
            f"Retrieved {len(evidence_pack.supporting_chunks)} chunks and "
            f"{len(evidence_pack.graph_paths)} graph paths. "
            f"Key chunks: {chunk_ids}. Key paths: {path_ids}."
        )

    @staticmethod
    def _harvest_asset_ids(
        evidence_pack: EvidencePack, node_types: list[str]
    ) -> dict[str, list[str]]:
        """Extract unique node IDs by type from graph paths for cascade retrieval."""
        if not node_types:
            return {}
        discovered: dict[str, list[str]] = {}
        for path in evidence_pack.graph_paths:
            for node in path.nodes:
                if node.node_type in node_types:
                    bucket = discovered.setdefault(node.node_type, [])
                    if node.node_id not in bucket:
                        bucket.append(node.node_id)
        return discovered

    @staticmethod
    def _derive_run_status(sections: dict[str, DocumentSection]) -> str:
        """Derive overall run status from section statuses."""
        statuses = [s.status for s in sections.values()]
        if all(status == "approved" for status in statuses) and statuses:
            return "approved"
        if any(status == "review_ready" for status in statuses):
            return "review_ready"
        if any(status == "in_progress" for status in statuses):
            return "in_progress"
        return "created"

    def _draft_from_plan(self, run: dict[str, Any]) -> DocumentDraft:
        """Build DocumentDraft from run state."""
        plan_dict = run["plan"]
        sections = stored_sections_list_to_sections_map(plan_dict.get("sections", []))
        section_drafts = []
        for section in sections.values():
            if section.draft_markdown:
                section_drafts.append(
                    SectionDraft(
                        section_id=section.section_id,
                        section_name=section.section_name,
                        title=section.title,
                        content_markdown=section.draft_markdown,
                        evidence_request_id=section.evidence_request_id or "",
                        confidence=section.confidence,
                        notes=list(section.notes),
                    )
                )
        draft = DocumentDraft(
            run_id=run["run_id"],
            system_id=run["system_id"],
            title=run["document_title"],
            sections=section_drafts,
            rendered_markdown="",
            confidence=0.0,
            metadata={"plan": plan_dict, "run_status": run["status"]},
        )
        draft.rendered_markdown = self.exporter.export_markdown(draft)
        return draft

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
