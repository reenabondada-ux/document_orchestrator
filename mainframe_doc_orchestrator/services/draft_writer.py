from __future__ import annotations

from mainframe_doc_orchestrator.models import (
    DocumentRequest,
    DocumentSection,
    EvidencePack,
)
from mainframe_doc_orchestrator.services.prompt_engine import PromptEngine


class SectionDraftWriter:
    def __init__(
        self,
        llm_client,
        prompt_engine: PromptEngine | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_engine = prompt_engine or PromptEngine()

    async def write(
        self,
        *,
        request: DocumentRequest,
        section: DocumentSection,
        evidence_pack: EvidencePack,
        prior_pass_count: int = 0,
        prior_drafts: dict[str, str] | None = None,
    ) -> str:
        system_prompt, user_prompt = self.prompt_engine.build_section_prompts(
            request=request,
            section=section,
            evidence_pack=evidence_pack,
            prior_pass_count=prior_pass_count,
            prior_drafts=prior_drafts,
        )
        # Use the section's blueprint max_tokens as the LLM output cap when set.
        # This ensures complex estates (larger top_k → higher max_tokens in the plan)
        # get proportionally more space to enumerate all assets.
        section_max_tokens: int | None = section.max_tokens if section.max_tokens > 0 else None
        return await self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=section_max_tokens,
        )
