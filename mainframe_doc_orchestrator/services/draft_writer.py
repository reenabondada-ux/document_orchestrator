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
    ) -> str:
        system_prompt, user_prompt = self.prompt_engine.build_section_prompts(
            request=request,
            section=section,
            evidence_pack=evidence_pack,
            prior_pass_count=prior_pass_count,
        )
        return await self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
