"""Serialization utilities for domain models.

Converts dataclasses to/from dicts for JSON storage in PostgreSQL.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mainframe_doc_orchestrator.models import DocumentSection


def section_to_dict(section: DocumentSection) -> dict[str, Any]:
    """Convert DocumentSection to dict for JSON serialization."""
    return asdict(section)


def dict_to_section(data: dict[str, Any]) -> DocumentSection:
    """Convert dict from JSON to DocumentSection object."""
    return DocumentSection(
        section_id=data["section_id"],
        section_name=data["section_name"],
        title=data["title"],
        objective=data["objective"],
        prompt_key=data["prompt_key"],
        required_evidence=list(data.get("required_evidence", [])),
        retrieval_hint=data.get("retrieval_hint", ""),
        min_chunks=int(data.get("min_chunks", 1)),
        min_paths=int(data.get("min_paths", 0)),
        max_tokens=int(data.get("max_tokens", 0)),
        asset_type_filter=list(data.get("asset_type_filter", [])),
        depends_on=list(data.get("depends_on", [])),
        cascade_from=list(data.get("cascade_from", [])),
        cascade_node_types=list(data.get("cascade_node_types", [])),
        # Runtime fields
        status=data.get("status", "pending"),
        draft_markdown=data.get("draft_markdown", ""),
        evidence_request_id=data.get("evidence_request_id"),
        confidence=float(data.get("confidence", 0.0)),
        notes=list(data.get("notes", [])),
        retrieval_pass_id=data.get("retrieval_pass_id"),
        retrieval_pass_number=data.get("retrieval_pass_number"),
        discovered_asset_ids=dict(data.get("discovered_asset_ids", {})),
        evidence_overview=data.get("evidence_overview", ""),
        updated_at=data.get("updated_at", ""),
        approval_notes=list(data.get("approval_notes", [])),
    )


def sections_map_to_stored_sections_list(
    sections_map: dict[str, DocumentSection],
) -> list[dict[str, Any]]:
    """Serialize sections map to a JSON-storable list (preserving insertion order)."""
    return [section_to_dict(s) for s in sections_map.values()]


def stored_sections_list_to_sections_map(
    sections_list: list[dict[str, Any]],
) -> dict[str, DocumentSection]:
    """Deserialize a stored list of sections into a section-name-keyed map for O(1) lookup."""
    return {s["section_name"]: dict_to_section(s) for s in sections_list}
