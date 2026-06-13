from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mainframe_doc_orchestrator.models import (
    DocumentRequest,
    DocumentSection,
    EvidencePack,
)
from mainframe_doc_orchestrator.prompt_library import PROMPTS, render_template


class PromptEngine:
    def build_section_prompts(
        self,
        *,
        request: DocumentRequest,
        section: DocumentSection,
        evidence_pack: EvidencePack,
        prior_pass_count: int,
        prior_drafts: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        prompt_bundle = PROMPTS[section.section_name]
        chunk_contents_dict = {
            k: asdict(v) for k, v in evidence_pack.chunk_contents.items()
        }
        context = {
            "system_id": request.system_id,
            "section_name": section.section_name,
            "section_title": section.title,
            "objective": section.objective,
            "retrieval_hint": section.retrieval_hint,
            "question": evidence_pack.question,
            "prior_pass_count": prior_pass_count,
            "supporting_chunks": evidence_pack.supporting_chunks,
            "chunk_contents": chunk_contents_dict,
            "graph_paths": [
                self._path_as_dict(path) for path in evidence_pack.graph_paths
            ],
            "supporting_data": evidence_pack.supporting_data,
            "evidence_items": [asdict(item) for item in evidence_pack.evidence_items],
            "confidence": evidence_pack.confidence,
            "prior_section_drafts": self._format_prior_drafts(prior_drafts or {}),
            "jcl_step_map": self._build_jcl_step_map(chunk_contents_dict),
        }
        user_prompt = render_template(prompt_bundle["user"], context)
        return prompt_bundle["system"], user_prompt

    @staticmethod
    def _build_jcl_step_map(chunk_contents: dict[str, Any]) -> str:
        """Pre-resolve JCL job → step mapping with exec_kind already determined.

        Returns a plain-text block listing every job and every one of its steps
        with the resolved exec_kind (PROC or PGM) and exec_target.  This is
        injected as {{jcl_step_map}} so the LLM never has to parse JCL syntax or
        infer PROC-vs-PGM from the raw text — both are structurally ambiguous
        without the ``PGM=`` prefix convention that the parser already resolved.
        """
        # Collect job names and their steps from chunk metadata.
        jobs: dict[str, dict[str, Any]] = {}  # job_asset_id → {name, steps}
        steps_by_parent: dict[str, list[dict[str, Any]]] = {}

        for cc in chunk_contents.values():
            kind = cc.get("chunk_kind", "")
            asset_id = cc.get("asset_id", "")
            if kind == "job":
                jobs[asset_id] = {"name": cc.get("chunk_name", asset_id), "steps": []}
            elif kind == "step":
                # Parent job asset_id is the part before the last "."
                parent_id = asset_id.rsplit(".", 1)[0] if "." in asset_id else asset_id
                md = cc.get("metadata") or {}
                step_info = {
                    "name": cc.get("chunk_name", asset_id.rsplit(".", 1)[-1]),
                    "exec_kind": md.get("exec_kind", "UNKNOWN"),
                    "exec_target": md.get("exec_target", "?"),
                }
                steps_by_parent.setdefault(parent_id, []).append(step_info)

        # Also infer job entries from step chunks when root job chunk wasn't retrieved.
        for parent_id in steps_by_parent:
            if parent_id not in jobs:
                inferred_name = (
                    parent_id.split("__")[-1] if "__" in parent_id else parent_id
                )
                jobs[parent_id] = {"name": inferred_name, "steps": []}

        if not jobs:
            return "(no JCL job chunks found in evidence)"

        lines: list[str] = [
            "Pre-resolved JCL job → step breakdown (use this as the authoritative step list):"
        ]
        for job_id, job_info in sorted(jobs.items()):
            lines.append(f"\nJob: {job_info['name']}  (asset_id: {job_id})")
            steps = steps_by_parent.get(job_id, [])
            if not steps:
                lines.append("  (no step chunks retrieved for this job)")
            for step in steps:
                ek = step["exec_kind"]
                et = step["exec_target"]
                if ek == "PROC":
                    lines.append(
                        f"  - Step {step['name']}: EXEC PROC={et}  ← PROC invocation (look up PROC {et} in chunk_contents and graph_paths)"
                    )
                elif ek == "PGM":
                    lines.append(f"  - Step {step['name']}: EXEC PGM={et}")
                else:
                    lines.append(f"  - Step {step['name']}: EXEC {et} (kind={ek})")
        return "\n".join(lines)

    @staticmethod
    def _format_prior_drafts(prior_drafts: dict[str, str]) -> str:
        if not prior_drafts:
            return ""
        parts = [f"### {name}\n{draft}" for name, draft in prior_drafts.items()]
        return "\n\n".join(parts)

    @staticmethod
    def _path_as_dict(path: Any) -> dict[str, Any]:
        return {
            "path_id": path.path_id,
            "path_label": path.path_label,
            "supporting_chunks": path.supporting_chunks,
            "nodes": [asdict(node) for node in path.nodes],
            "edges": [asdict(edge) for edge in path.edges],
        }
