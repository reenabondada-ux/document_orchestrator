# Architecture Diagrams

Visual documentation of the Mainframe Document Orchestrator system architecture, data flow, and process workflows.

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "API Layer"
        API[FastAPI Application]
        Routes[Route Handlers]
        Schemas[Request/Response Schemas]
    end

    subgraph "Service Layer"
        WE[WorkflowEngine]
        DW[DraftWriter]
        PE[PromptEngine]
        EXP[Exporter]
        PRV[Previewer]
    end

    subgraph "Core Domain"
        PLN[Planner]
        VAL[Validator]
        ASM[Assembler]
        MOD[Models & Contracts]
    end

    subgraph "Client Layer"
        RC[RetrievalClient]
        LC[LLMClient]
    end

    subgraph "Persistence Layer"
        DR[DocumentRepository]
        RPS[RetrievalPassStore]
        PG[(PostgreSQL)]
    end

    subgraph "External Systems"
        RAG[RAG Service<br/>Evidence Pack API]
        LLM[LLM Provider<br/>OpenAI/Bedrock/Local]
    end

    API --> Routes
    Routes --> Schemas
    Routes --> WE

    WE --> PLN
    WE --> VAL
    WE --> DW
    WE --> EXP
    WE --> RC
    WE --> LC
    WE --> DR
    WE --> RPS

    DW --> PE
    DW --> LC
    EXP --> ASM
    PRV --> ASM

    DR --> PG
    RPS --> PG

    RC --> RAG
    LC --> LLM

    style API fill:#e1f5ff
    style WE fill:#fff4e1
    style DR fill:#f0e1ff
    style RAG fill:#ffe1e1
    style LLM fill:#ffe1e1
```

**Key Components:**
- **API Layer**: FastAPI endpoints, request validation, response serialization
- **Service Layer**: Orchestration, content generation, export/preview logic
- **Core Domain**: Business logic (planning, validation, assembly)
- **Client Layer**: Adapters for external services
- **Persistence**: Postgres repositories for state management
- **External Systems**: RAG evidence service and LLM providers

---

## 2. Document Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant WorkflowEngine
    participant Planner
    participant RetrievalClient
    participant LLMClient
    participant DraftWriter
    participant Repository
    participant RAG
    participant LLM

    User->>API: POST /documents<br/>{system_id, document_type}
    API->>WorkflowEngine: create_document_run(request)
    WorkflowEngine->>Planner: plan(request)
    Planner-->>WorkflowEngine: DocumentPlan with sections
    WorkflowEngine->>Repository: create_run(plan)
    Repository-->>WorkflowEngine: run_id
    WorkflowEngine-->>API: {run_id, status: "created"}
    API-->>User: 201 Created

    User->>API: POST /documents/{run_id}/generate-all
    
    loop For each section
        API->>WorkflowEngine: generate_section(run_id, section_name)
        
        alt Check Dependencies
            WorkflowEngine->>Repository: get_run(run_id)
            Repository-->>WorkflowEngine: current state
            WorkflowEngine->>WorkflowEngine: validate depends_on sections
        end
        
        WorkflowEngine->>RetrievalClient: get_evidence_pack(retrieval_request)
        RetrievalClient->>RAG: POST /v1/retrieve
        RAG-->>RetrievalClient: EvidencePack
        RetrievalClient-->>WorkflowEngine: evidence_pack
        
        WorkflowEngine->>Repository: store_retrieval_pass
        
        WorkflowEngine->>DraftWriter: generate_section_draft(section, evidence)
        DraftWriter->>LLMClient: generate_completion(prompt)
        LLMClient->>LLM: API call
        LLM-->>LLMClient: response
        LLMClient-->>DraftWriter: generated_text
        DraftWriter-->>WorkflowEngine: SectionDraft
        
        WorkflowEngine->>Repository: update_section(status: "review_ready")
    end
    
    WorkflowEngine-->>API: {run_id, status: "review_ready"}
    API-->>User: 200 OK
```

---

## 3. Section State Machine

```mermaid
stateDiagram-v2
    [*] --> planned: Section created in plan
    
    planned --> generating: Generate action triggered
    planned --> skipped: Dependencies not met / No assets found
    
    generating --> review_ready: Generation successful
    generating --> failed: Generation error
    generating --> generating: Retry attempt
    
    review_ready --> approved: User approval
    review_ready --> generating: Regenerate requested
    
    failed --> generating: Retry triggered
    failed --> skipped: Skip section
    
    approved --> [*]: Section finalized
    skipped --> [*]: Section excluded
    
    note right of planned
        Initial state after 
        document plan creation
    end note
    
    note right of review_ready
        Draft ready for human review.
        Can proceed to export or
        regenerate if needed.
    end note
    
    note right of approved
        User has validated content.
        No further changes expected.
    end note
```

**State Transitions:**
- `planned` → `generating`: When generate_section() is called
- `generating` → `review_ready`: Successful draft generation
- `generating` → `failed`: LLM error, timeout, or validation failure
- `review_ready` → `approved`: User explicitly approves section
- `review_ready` → `generating`: User requests regeneration
- `failed` → `generating`: Retry with same or modified parameters
- Any → `skipped`: Cascade sections with no upstream assets

---

## 4. Document Run Status Derivation

```mermaid
graph TD
    Start[Evaluate all sections] --> CheckFailed{Any section<br/>status = failed?}
    
    CheckFailed -->|Yes| Failed[Run status:<br/>FAILED]
    CheckFailed -->|No| CheckGenerating{Any section<br/>status = generating?}
    
    CheckGenerating -->|Yes| InProgress[Run status:<br/>IN_PROGRESS]
    CheckGenerating -->|No| CheckPlanned{Any section<br/>status = planned?}
    
    CheckPlanned -->|Yes| Created[Run status:<br/>CREATED]
    CheckPlanned -->|No| CheckReviewReady{All sections<br/>review_ready or approved?}
    
    CheckReviewReady -->|Yes| ReviewReady[Run status:<br/>REVIEW_READY]
    CheckReviewReady -->|No| CheckAllApproved{All sections<br/>approved?}
    
    CheckAllApproved -->|Yes| Approved[Run status:<br/>APPROVED]
    CheckAllApproved -->|No| PartiallyApproved[Run status:<br/>PARTIALLY_APPROVED]

    style Failed fill:#ffcccc
    style InProgress fill:#fff4cc
    style Created fill:#e1f5ff
    style ReviewReady fill:#ccffcc
    style Approved fill:#ccffcc
```

---

## 5. Retrieval Request Building

```mermaid
flowchart TD
    Start[Section requires generation] --> CheckCascade{Section has<br/>cascade_from?}
    
    CheckCascade -->|Yes| ExtractAssets[Extract discovered_asset_ids<br/>from upstream sections]
    ExtractAssets --> CheckAssetsFound{Asset IDs found?}
    
    CheckAssetsFound -->|No| SkipRetrieval[Skip retrieval<br/>Set status: review_ready<br/>with skip note]
    CheckAssetsFound -->|Yes| BuildFilters[Build RetrievalFilters<br/>with asset_ids]
    
    CheckCascade -->|No| CheckAssetFilter{Section has<br/>asset_type_filter?}
    CheckAssetFilter -->|Yes| BuildTypeFilters[Build RetrievalFilters<br/>with asset_types]
    CheckAssetFilter -->|No| NoFilters[Build RetrievalFilters<br/>empty = no constraints]
    
    BuildFilters --> CreateRequest[Create RetrievalRequest]
    BuildTypeFilters --> CreateRequest
    NoFilters --> CreateRequest
    
    CreateRequest --> CheckExisting{Crash recovery:<br/>completed pass exists?}
    
    CheckExisting -->|Yes| FetchExisting[GET /v1/evidence-packs/{id}]
    CheckExisting -->|No| NewRetrieval[POST /v1/retrieve]
    
    FetchExisting --> ProcessEvidence[Process EvidencePack]
    NewRetrieval --> StorePass[Store retrieval pass] --> ProcessEvidence
    
    ProcessEvidence --> GenerateDraft[Generate section draft]
    
    SkipRetrieval --> End[Return section result]
    GenerateDraft --> End

    style SkipRetrieval fill:#ffffcc
    style ProcessEvidence fill:#ccffcc
```

---

## 6. Evidence Pack Structure

```mermaid
classDiagram
    class EvidencePack {
        +String evidence_request_id
        +String question
        +String section_name
        +String system_id
        +List~String~ supporting_chunks
        +Dict~String,ChunkContent~ chunk_contents
        +List~GraphPath~ graph_paths
        +Dict~String,Any~ supporting_data
        +Float confidence
        +List~EvidenceItem~ evidence_items
    }
    
    class ChunkContent {
        +String chunk_id
        +String asset_id
        +String asset_type
        +String chunk_kind
        +String chunk_name
        +String text
        +String source_file
        +Int line_start
        +Int line_end
        +Dict metadata
    }
    
    class GraphPath {
        +String path_id
        +String path_label
        +List~GraphPathNode~ nodes
        +List~GraphPathEdge~ edges
        +List~String~ supporting_chunks
    }
    
    class GraphPathNode {
        +String node_id
        +String node_type
        +Dict properties
    }
    
    class GraphPathEdge {
        +String source_id
        +String target_id
        +String edge_type
        +Dict properties
    }
    
    class EvidenceItem {
        +String item_type
        +String ref
        +String relevance
    }
    
    EvidencePack "1" --> "*" ChunkContent: contains
    EvidencePack "1" --> "*" GraphPath: includes
    EvidencePack "1" --> "*" EvidenceItem: categorizes
    GraphPath "1" --> "*" GraphPathNode: composed of
    GraphPath "1" --> "*" GraphPathEdge: connected by
```

---

## 7. Dependency Chain Resolution

```mermaid
graph LR
    subgraph "Phase 1: Independent Sections"
        S1[System Overview]
        S2[Technical Architecture]
        S3[JCL Analysis]
        S4[Data Structures]
    end
    
    subgraph "Phase 2: Synthesis Sections"
        S5[Integration Points]
        S6[Operational Patterns]
    end
    
    subgraph "Phase 2: Cascade Sections"
        S7[PROC Analysis]
        S8[COBOL Analysis]
    end
    
    subgraph "Phase 3: Final Synthesis"
        S9[System Summary]
    end
    
    S1 --> S5
    S2 --> S5
    S1 --> S6
    S3 --> S6
    
    S3 -.cascade_from.-> S7
    S7 -.cascade_from.-> S8
    
    S5 --> S9
    S6 --> S9
    S8 --> S9
    
    style S1 fill:#e1f5ff
    style S2 fill:#e1f5ff
    style S3 fill:#e1f5ff
    style S4 fill:#e1f5ff
    style S5 fill:#fff4e1
    style S6 fill:#fff4e1
    style S7 fill:#ffe1f5
    style S8 fill:#ffe1f5
    style S9 fill:#ccffcc
```

**Legend:**
- **Blue**: Phase 1 - Independent retrieval sections
- **Yellow**: Phase 2 - Synthesis sections (require upstream drafts)
- **Pink**: Phase 2 - Cascade sections (require upstream asset IDs)
- **Green**: Phase 3 - Final synthesis
- **Solid arrows**: `depends_on` relationship
- **Dotted arrows**: `cascade_from` relationship

---

## 8. Database Schema

```mermaid
erDiagram
    document_runs ||--o{ retrieval_passes : has
    
    document_runs {
        uuid run_id PK
        text document_title
        text system_id
        text status
        jsonb plan
        timestamptz created_at
        timestamptz updated_at
    }
    
    retrieval_passes {
        uuid pass_id PK
        uuid run_id FK
        text section_name
        int pass_number
        text status
        text evidence_request_id
        jsonb retrieval_request
        jsonb evidence_pack
        text error_message
        timestamptz created_at
        timestamptz completed_at
    }
```

**Key Relationships:**
- One document run can have multiple retrieval passes
- Each retrieval pass tracks evidence gathering for one section
- Pass numbers increment for retries/regenerations
- Evidence pack stored as JSONB for easy querying

---

## 9. API Request Flow

```mermaid
flowchart TD
    Start[Client Request] --> Router{Route}
    
    Router -->|POST /documents| CreateRun[create_document_run]
    Router -->|POST /documents/{id}/generate-all| GenAll[generate_all_sections]
    Router -->|POST /documents/{id}/sections/{name}| GenOne[generate_section]
    Router -->|GET /documents/{id}| GetDoc[get_document_run]
    Router -->|GET /documents/{id}/sections/{name}| GetSec[get_section]
    Router -->|POST /documents/{id}/approve| Approve[approve_document]
    Router -->|GET /documents/{id}/export| Export[export_document]
    
    CreateRun --> Deps[Dependency Injection]
    GenAll --> Deps
    GenOne --> Deps
    GetDoc --> Deps
    GetSec --> Deps
    Approve --> Deps
    Export --> Deps
    
    Deps --> WE[WorkflowEngine]
    Deps --> Repos[Repositories]
    Deps --> Clients[External Clients]
    
    WE --> Process[Process Request]
    Process --> DB[(PostgreSQL)]
    Process --> RAG[RAG Service]
    Process --> LLM[LLM Provider]
    
    Process --> Response[Format Response]
    Response --> Client[Return to Client]

    style Start fill:#e1f5ff
    style Router fill:#fff4e1
    style WE fill:#ffe1e1
    style Response fill:#ccffcc
```

---

## 10. Prompt Engineering Flow

```mermaid
sequenceDiagram
    participant DW as DraftWriter
    participant PE as PromptEngine
    participant PL as PromptLibrary
    participant LC as LLMClient
    participant LLM as LLM Provider

    DW->>PE: build_prompt(section, evidence, prior_drafts)
    PE->>PL: get_template(section.prompt_key)
    PL-->>PE: prompt_template
    
    PE->>PE: Format evidence<br/>(chunks + graph paths)
    
    alt Synthesis Section (has prior_drafts)
        PE->>PE: Include prior section drafts
    end
    
    PE->>PE: Inject system_id, title, objective
    PE->>PE: Add evidence validation instructions
    PE-->>DW: formatted_prompt
    
    DW->>LC: generate_completion(prompt, max_tokens)
    LC->>LLM: API call with prompt
    LLM-->>LC: generated_text
    LC-->>DW: response
    
    DW->>DW: Extract markdown from response
    DW->>DW: Calculate confidence score
    DW-->>WorkflowEngine: SectionDraft
```

---

## Diagram Usage Guide

| Diagram | Use When |
|---------|----------|
| **System Architecture** | Understanding component relationships and responsibilities |
| **Document Generation Flow** | Tracing end-to-end request processing |
| **Section State Machine** | Understanding section lifecycle and valid transitions |
| **Document Run Status** | Debugging status calculation issues |
| **Retrieval Request Building** | Understanding cascade logic and asset filtering |
| **Evidence Pack Structure** | Working with retrieval responses |
| **Dependency Chain** | Planning section generation order |
| **Database Schema** | Writing queries or migrations |
| **API Request Flow** | API integration or debugging |
| **Prompt Engineering Flow** | Debugging generation or prompt issues |

---

## Related Documentation

- [REPO_STRUCTURE.md](./REPO_STRUCTURE.md) - Code organization
- [API.md](./API.md) - API endpoints and examples
- [BUILD_ORDER.md](./BUILD_ORDER.md) - Development sequence
- [PERSISTENCE.md](./PERSISTENCE.md) - Database design
- [MODEL_PORTABILITY.md](./MODEL_PORTABILITY.md) - LLM provider switching
