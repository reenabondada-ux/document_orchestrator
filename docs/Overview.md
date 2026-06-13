# Mainframe Document Orchestrator 
## Python, FastAPI, LangChain, PostgreSQL

- Engineered an end-to-end agentic document generation system that transforms RAG-retrieved evidence packs into structured System Appreciation Documents via a multi-step LLM workflow
- Designed a layered architecture with a FastAPI service layer, async PostgreSQL persistence (asyncpg connection pool), and pluggable LLM clients supporting OpenAI, AWS Bedrock, and local models
- Implemented a full document lifecycle REST API (create → plan → generate → approve → regenerate → export) with per-section human-in-the-loop review and lifecycle event tracking
- Built a Planner → Validator → DraftWriter → Assembler pipeline with gap detection on retrieved evidence, prompt templating per document section, and idempotent Markdown export
- Integrated a retrieval client against an external RAG evidence-pack API, with structured contracts (Python Protocols) decoupling each pipeline stage for testability and model portability
- Managed schema evolution via numbered, idempotent SQL migration files applied by a custom migrate.py script — zero ORM DDL at runtime
