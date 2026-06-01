from __future__ import annotations
import argparse, json
from pathlib import Path
from mainframe_doc_orchestrator.clients.llm_clients import (
    BedrockLLMClient,
    EchoLLMClient,
    OpenAICompatibleLLMClient,
)
from mainframe_doc_orchestrator.clients.retrieval_client import (
    HttpRetrievalClient,
    RetrievalClientStub,
    evidence_pack_from_dict,
)
from mainframe_doc_orchestrator.models import (
    DocumentRequest,
    RetrievalFilters,
    RetrievalRequest,
)
from mainframe_doc_orchestrator.orchestrator import DocumentOrchestrator


def load_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_llm(config: dict):
    provider = config.get("llm_provider", "stub")
    model = config.get("llm_model", "local-demo")
    if provider == "stub":
        return EchoLLMClient(model_name=model)
    if provider == "openai_compatible":
        return OpenAICompatibleLLMClient(
            base_url=config["llm_base_url"],
            api_key=config.get("llm_api_key"),
            model_name=model,
        )
    if provider == "bedrock":
        return BedrockLLMClient(model_id=model, region_name=config.get("aws_region"))
    raise ValueError(f"Unsupported llm_provider: {provider}")


def build_retrieval_client(config: dict):
    if config.get("use_stub_evidence_pack"):
        pack = evidence_pack_from_dict(
            json.loads(
                Path(config["stub_evidence_pack_path"]).read_text(encoding="utf-8")
            )
        )
        return RetrievalClientStub(pack)
    return HttpRetrievalClient(
        endpoint=config["retrieval_endpoint"],
        evidence_endpoint_template=config.get("evidence_endpoint_template"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a mainframe system appreciation document."
    )
    parser.add_argument("--config", required=True, help="Path to JSON config.")
    parser.add_argument("--topic", default="", help="Document topic override.")
    parser.add_argument(
        "--section", default="batch_flow_overview", help="Initial section focus."
    )
    parser.add_argument("--system-id", default="", help="System id override.")
    args = parser.parse_args()
    config = load_config(args.config)
    llm_client = build_llm(config)
    retrieval_client = build_retrieval_client(config)
    system_id = args.system_id or config.get("system_id", "")
    topic = args.topic or config.get("topic", system_id)
    filters = RetrievalFilters(
        asset_types=config.get("asset_types", []),
        asset_ids=config.get("asset_ids", []),
        domains=config.get("domains", []),
    )
    retrieval_request = RetrievalRequest(
        query=topic,
        section_name=args.section,
        system_id=system_id,
        top_k_chunks=int(config.get("top_k_chunks", 8)),
        top_k_paths=int(config.get("top_k_paths", 5)),
        filters=filters,
    )
    request = DocumentRequest(
        system_id=system_id,
        document_style=config.get("document_style", "system_appreciation"),
        output_format=config.get("output_format", "markdown"),
        topic=topic,
        section_order=config.get("section_order", []),
        retrieval_request=retrieval_request,
        metadata={"evidence_request_id": config.get("evidence_request_id")},
    )
    orchestrator = DocumentOrchestrator(
        retrieval_client=retrieval_client,
        llm_client=llm_client,
    )
    print(orchestrator.run(request).rendered_markdown)


if __name__ == "__main__":
    main()
