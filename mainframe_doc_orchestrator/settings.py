from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ============================================
    # APPLICATION
    # ============================================
    app_name: str = "Mainframe Document Orchestrator"
    default_user_role: str = "analyst"

    # ============================================
    # DATABASE
    # ============================================
    postgres_dsn: str = ""  # Required — set in .env

    # ============================================
    # LLM — choose provider, then fill that section
    # Options: stub | openai | bedrock
    # ============================================
    llm_provider: str = "stub"

    # stub
    stub_llm_model: str = "echo"
    stub_max_output_tokens: int = 4096

    # openai (any OpenAI-compatible endpoint: OpenAI, Azure, Ollama, vLLM …)
    openai_base_url: str = ""
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_max_output_tokens: int = (
        4096  # gpt-4o-mini: 16384 / gpt-4o: 16384 / Ollama: model-dependent
    )

    # bedrock
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_region: str = "us-east-1"
    bedrock_max_output_tokens: int = (
        4096  # Claude 3 Sonnet/Haiku: 4096 / Claude 3.5 Sonnet: 8192
    )

    # Sampling temperature applied to all providers. Low values (0.0–0.3) are
    # preferred for factual, evidence-grounded generation. Override in .env for
    # deterministic testing (0.0) or richer prose in staging (0.3).
    llm_temperature: float = 0.2

    # ============================================
    # RETRIEVAL — choose provider, then fill that section
    # Options: http | stub
    # ============================================
    retrieval_provider: str = "http"

    # http
    retrieval_endpoint: str = "http://localhost:8001/v1/retrieve"
    retrieval_evidence_endpoint_template: str = (
        "http://localhost:8001/v1/evidence-packs/{request_id}"
    )
    retrieval_timeout: int = 60

    # stub (path to a local evidence-pack JSON file)
    retrieval_stub_path: str = ""

    # ============================================
    # RETRIEVAL PARAMETERS
    # ============================================
    top_k_chunks: int = 8
    top_k_paths: int = 5


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
