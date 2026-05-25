from __future__ import annotations

import json
from pathlib import Path

from mainframe_doc_orchestrator.clients.llm_clients import EchoLLMClient
from mainframe_doc_orchestrator.clients.retrieval_client import (
    RetrievalClientStub,
    evidence_pack_from_dict,
)
from mainframe_doc_orchestrator.models import DocumentRequest, RetrievalRequest
from mainframe_doc_orchestrator.orchestrator import DocumentOrchestrator

if __name__ == "__main__":
    pack = evidence_pack_from_dict(
        json.loads(
            Path("examples/sample_evidence_pack.json").read_text(encoding="utf-8")
        )
    )
    retrieval = RetrievalClientStub(pack)
    llm = EchoLLMClient(model_name="demo")
    orchestrator = DocumentOrchestrator(retrieval_client=retrieval, llm_client=llm)
    req = DocumentRequest(
        system_id="ACME_MAINFRAME_POC",
        user_role="analyst",
        topic="Create system appreciation document for the billing flow",
        retrieval_request=RetrievalRequest(
            query=pack.question,
            section_name=pack.section_name,
            system_id=pack.system_id,
        ),
    )
    draft = orchestrator.run(req)
    print(draft.rendered_markdown)
