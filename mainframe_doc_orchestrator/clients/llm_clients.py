"""Async LLM client implementations.

All clients expose ``async def generate()``.

- ``EchoLLMClient``            — in-process stub, no I/O.
- ``OpenAICompatibleLLMClient`` — uses ``httpx.AsyncClient`` for true async HTTP.
- ``BedrockLLMClient``          — wraps boto3 (sync-only SDK) in ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from mainframe_doc_orchestrator.contracts import LLMClient


class EchoLLMClient:
    def __init__(self, model_name: str = "echo", max_output_tokens: int = 4096, temperature: float = 0.2) -> None:
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    async def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return (
            "# Echo Model Output\n\n"
            f"## System Prompt\n{system_prompt}\n\n"
            f"## User Prompt\n{user_prompt}\n"
        )


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model_name: str,
        max_output_tokens: int,
        temperature: float,
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    async def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class BedrockLLMClient:
    def __init__(
        self, model_id: str, max_output_tokens: int, temperature: float, region_name: str | None = None
    ) -> None:
        self.model_name = model_id
        self.region_name = region_name
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    async def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return await asyncio.to_thread(
            self._generate_sync,
            system_prompt,
            user_prompt,
            self.temperature,
            self.max_output_tokens,
        )

    def _generate_sync(
        self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for BedrockLLMClient") from exc
        client = boto3.client("bedrock-runtime", region_name=self.region_name)
        response = client.converse(
            modelId=self.model_name,
            system=system_prompt,
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
        )
        output = response["output"]["message"]["content"]
        return "\n".join(part.get("text", "") for part in output)


def llm_client_from_settings(settings: object) -> "LLMClient":
    """Instantiate the correct LLM client from application settings.

    Set ``LLM_PROVIDER`` to one of: ``stub``, ``openai``, ``bedrock``.
    Each provider reads only its own prefixed settings variables.

    Raises:
        ValueError: If the provider is unrecognised or a required variable is missing.
    """
    provider = settings.llm_provider.lower()  # type: ignore[union-attr]

    if provider == "stub":
        return EchoLLMClient(
            model_name=settings.stub_llm_model,  # type: ignore[union-attr]
            max_output_tokens=settings.stub_max_output_tokens,  # type: ignore[union-attr]
            temperature=settings.llm_temperature,  # type: ignore[union-attr]
        )

    if provider == "openai":
        if not settings.openai_base_url:  # type: ignore[union-attr]
            raise ValueError("OPENAI_BASE_URL is required for the openai provider")
        if not settings.openai_api_key:  # type: ignore[union-attr]
            raise ValueError("OPENAI_API_KEY is required for the openai provider")
        if not settings.openai_max_output_tokens:  # type: ignore[union-attr]
            raise ValueError(
                "OPENAI_MAX_OUTPUT_TOKENS is required for the openai provider"
            )
        return OpenAICompatibleLLMClient(
            base_url=settings.openai_base_url,  # type: ignore[union-attr]
            api_key=settings.openai_api_key,  # type: ignore[union-attr]
            model_name=settings.openai_model,  # type: ignore[union-attr]
            max_output_tokens=settings.openai_max_output_tokens,  # type: ignore[union-attr]
            temperature=settings.llm_temperature,  # type: ignore[union-attr]
        )

    if provider == "bedrock":
        if not settings.bedrock_max_output_tokens:  # type: ignore[union-attr]
            raise ValueError(
                "BEDROCK_MAX_OUTPUT_TOKENS is required for the bedrock provider"
            )
        return BedrockLLMClient(
            model_id=settings.bedrock_model_id,  # type: ignore[union-attr]
            max_output_tokens=settings.bedrock_max_output_tokens,  # type: ignore[union-attr]
            temperature=settings.llm_temperature,  # type: ignore[union-attr]
            region_name=settings.bedrock_region,  # type: ignore[union-attr]
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: '{settings.llm_provider}'. "  # type: ignore[union-attr]
        "Valid options: 'stub', 'openai', 'bedrock'."
    )
