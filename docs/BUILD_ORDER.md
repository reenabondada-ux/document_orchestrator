# Document Orchestrator Build Order

## 1. Domain contract layer
Create the request/response models for retrieval and document generation.
Why first: every later component should compile against these shapes.

## 2. Retrieval client layer
Add the client that fetches an EvidencePack from the RAG service.
Why second: the orchestrator depends on a stable evidence contract.

## 3. Prompt library
Write one prompt per document section.
Why third: section prompts define the narrative boundaries and evidence expectations.

## 4. Planner
Generate a section plan from the request and evidence pack.
Why fourth: the document should be planned before any prose generation begins.

## 5. LLM provider abstraction
Add local, OpenAI-compatible, and Bedrock adapters.
Why fifth: this keeps model choice plug-and-play.

## 6. Section writer
Generate one section at a time.
Why sixth: section-level generation is easier to validate and retry.

## 7. Validator
Check that the generated section is evidence-backed.
Why seventh: this prevents unsupported prose from entering the final document.

## 8. Assembler
Combine the section drafts into markdown or doc-ready output.
Why eighth: final formatting should happen only after validation.

## 9. CLI / API
Expose the orchestrator as a runnable tool or service.
Why last: the core engine should be stable before you expose it.
