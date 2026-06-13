"""Async retrieval client implementations.

``HttpRetrievalClient`` uses ``httpx.AsyncClient`` for true async HTTP — no
thread pool overhead.  ``RetrievalClientStub`` is fully in-process.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from mainframe_doc_orchestrator.contracts import RetrievalClient

from mainframe_doc_orchestrator.models import ChunkContent, EvidenceItem, EvidencePack, GraphPath, GraphPathEdge, GraphPathNode, RetrievalRequest
from mainframe_doc_orchestrator.settings import Settings


class HttpRetrievalClient:
    def __init__(self, endpoint: str, evidence_endpoint_template: str | None = None, timeout: int = 60) -> None:
        self.endpoint = endpoint
        self.evidence_endpoint_template = (
            evidence_endpoint_template or endpoint.rstrip("/") + "/evidence-packs/{request_id}"
        )
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def retrieve(self, request: RetrievalRequest) -> EvidencePack:
        payload = {
            "query": request.query,
            "section_name": request.section_name,
            "system_id": request.system_id,
            "top_k_chunks": request.top_k_chunks,
            "top_k_paths": request.top_k_paths,
            "filters": asdict(request.filters),
        }
        response = await self._client.post(self.endpoint, json=payload)
        response.raise_for_status()
        # POST /v1/retrieve returns RetrievalResponse {request_id, query, confidence, evidence_pack}
        # The evidence_pack is nested — unwrap it.
        return evidence_pack_from_dict(response.json()["evidence_pack"])

    async def fetch_evidence_pack(self, evidence_request_id: str) -> EvidencePack:
        url = self.evidence_endpoint_template.format(request_id=evidence_request_id)
        response = await self._client.get(url)
        response.raise_for_status()
        return evidence_pack_from_dict(response.json())

    async def aclose(self) -> None:
        await self._client.aclose()


class RetrievalClientStub:
    def __init__(self, evidence_pack: EvidencePack | None = None) -> None:
        self._pack = evidence_pack

    async def retrieve(self, request: RetrievalRequest) -> EvidencePack:
        if self._pack is None:
            raise RuntimeError("Stub retrieval client has no evidence pack configured.")
        return self._pack

    async def fetch_evidence_pack(self, evidence_request_id: str) -> EvidencePack:
        if self._pack is None or self._pack.evidence_request_id != evidence_request_id:
            raise RuntimeError("Stub retrieval client has no matching evidence pack.")
        return self._pack


def evidence_pack_from_dict(data: dict[str, Any]) -> EvidencePack:
    """Deserialise a mainframe EvidencePack JSON dict into the orchestrator domain object.

    Call this on the *unwrapped* pack — i.e. response.json()["evidence_pack"] for POST
    /v1/retrieve, or response.json() directly for GET /v1/evidence-packs/{id}.
    """
    chunk_contents: dict[str, ChunkContent] = {
        chunk_id: ChunkContent(**content)
        for chunk_id, content in data.get("chunk_contents", {}).items()
    }
    graph_paths = [
        GraphPath(
            path_id=item["path_id"],
            path_label=item.get("path_label", ""),
            nodes=[GraphPathNode(**node) for node in item.get("nodes", [])],
            edges=[GraphPathEdge(**edge) for edge in item.get("edges", [])],
            supporting_chunks=list(item.get("supporting_chunks", [])),
        )
        for item in data.get("graph_paths", [])
    ]
    evidence_items = [
        EvidenceItem(
            item_type=item["item_type"],
            ref=item["ref"],
            relevance=item.get("relevance", ""),
        )
        for item in data.get("evidence_items", [])
    ]
    return EvidencePack(
        evidence_request_id=data["request_id"],
        question=data["question"],
        section_name=data.get("section_name") or "",
        system_id=data.get("system_id") or "",
        supporting_chunks=list(data.get("supporting_chunks", [])),
        chunk_contents=chunk_contents,
        graph_paths=graph_paths,
        supporting_data=dict(data.get("supporting_data") or {}),
        confidence=float(data.get("confidence", 0.0)),
        evidence_items=evidence_items,
    )


def retrieval_client_from_settings(settings: Settings) -> "RetrievalClient":
    """Instantiate the correct retrieval client from application settings.

    Set ``RETRIEVAL_PROVIDER`` to one of: ``http``, ``stub``.
    Each provider reads only its own prefixed settings variables.

    Raises:
        ValueError: If the provider is unrecognised or a required variable is missing.
    """
    provider = settings.retrieval_provider.lower()

    if provider == "stub":
        stub_path = settings.retrieval_stub_path
        if not stub_path:
            raise ValueError("RETRIEVAL_STUB_PATH is required for the stub retrieval provider")
        from pathlib import Path
        path = Path(stub_path)
        if not path.exists():
            raise ValueError(f"Stub evidence-pack file not found: {path}")
        pack = evidence_pack_from_dict(json.loads(path.read_text(encoding="utf-8")))
        return RetrievalClientStub(pack)

    if provider == "http":
        endpoint = settings.retrieval_endpoint
        if not endpoint:
            raise ValueError("RETRIEVAL_ENDPOINT is required for the http retrieval provider")
        return HttpRetrievalClient(
            endpoint=endpoint,
            evidence_endpoint_template=settings.retrieval_evidence_endpoint_template,
            timeout=settings.retrieval_timeout,
        )

    raise ValueError(
        f"Unsupported RETRIEVAL_PROVIDER: '{settings.retrieval_provider}'. "
        "Valid options: 'http', 'stub'."
    )
