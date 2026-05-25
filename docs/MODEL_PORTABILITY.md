# Model Portability

The orchestrator should support:
- local echo / openai-compatible / Ollama / vLLM style endpoints
- hosted model APIs
- AWS Bedrock

The only component that should know the provider is the LLM adapter.
All other code should depend on the `LLMClient` contract.
