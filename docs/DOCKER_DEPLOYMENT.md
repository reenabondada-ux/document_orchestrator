# Docker Deployment

## Quick Start

The document orchestrator can run in Docker while reusing the shared Postgres database from `rag-aws-portfolio` on port **5432**.

```bash
# Build and start
docker compose up -d

# View logs
docker compose logs -f document-orchestrator-app

# Stop
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

## Architecture

```
┌─────────────────────────────────────┐
│  document-orchestrator-app:8010     │
│  ├─ FastAPI app                     │
│  ├─ Calls mainframe-rag via HTTP    │
│  └─ Connects to shared Postgres     │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  postgres:5432 (rag-aws-portfolio)  │
│  ├─ Shared DB service               │
│  └─ Managed by rag-aws-portfolio    │
└─────────────────────────────────────┘
```

## Port Allocation

| Service                        | Internal | External | Notes                          |
|--------------------------------|----------|----------|--------------------------------|
| document-orchestrator-app      | 8010     | 8010     | FastAPI app                    |
| postgres (shared, rag stack)   | 5432     | 5432     | Started from rag-aws-portfolio |

## Environment Configuration

The `.env` file is automatically loaded by `docker-compose.yml`. Key variables:

```bash
# Database (shared)
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_pass
POSTGRES_DB=postgres_db

# Retrieval endpoint (point to mainframe-rag-app)
# If rag-app is on host: http://host.docker.internal:8001/v1/retrieve
# If rag-app is in same Docker network: http://mainframe-rag-app:8001/v1/retrieve
RETRIEVAL_ENDPOINT=http://host.docker.internal:8001/v1/retrieve
RETRIEVAL_EVIDENCE_ENDPOINT_TEMPLATE=http://host.docker.internal:8001/v1/evidence-packs/{request_id}

# LLM provider (openai | bedrock | stub)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### Connecting to Other Docker Services

**If mainframe-rag-app is also running in Docker:**

1. Create a shared network or merge the compose files
2. Update `.env`:
   ```bash
   RETRIEVAL_ENDPOINT=http://mainframe-rag-app:8001/v1/retrieve
   ```

**If mainframe-rag-app is running locally (uvicorn on host):**

Keep the default `host.docker.internal` URLs (already configured).

## Database Access

**From host machine:**
```bash
psql postgresql://postgres_user:postgres_pass@localhost:5432/postgres_db
```

**From inside the container:**
```bash
docker exec -it document-orchestrator-app psql "$POSTGRES_DSN"
```

## Rebuilding After Code Changes

```bash
# Rebuild image and restart
docker compose up -d --build

# Force full rebuild (no cache)
docker compose build --no-cache
docker compose up -d
```

## Healthchecks

The app service has a healthcheck:

- **app**: `curl http://localhost:8010/docs` every 10s (20s startup grace period)

Check health status:
```bash
docker ps  # Look for "healthy" status
docker compose ps  # Detailed status
```

## Troubleshooting

### "Connection refused" to mainframe-rag-app

**Symptom**: Orchestrator logs show `httpx.ConnectError: [Errno 61] Connection refused`

**Fix**: Ensure mainframe-rag-app is running and accessible:
```bash
# If rag-app is on host
curl http://localhost:8001/docs

# If rag-app is in Docker
docker inspect mainframe-rag-app | grep IPAddress
```

Update `RETRIEVAL_ENDPOINT` in `.env` accordingly.

### Schema not applied

**Symptom**: `relation "document_runs" does not exist`

**Fix**: Apply schema to the shared database:
```bash
psql postgresql://postgres_user:postgres_pass@localhost:5432/postgres_db -f database/schema.sql
```

### Shared Postgres not reachable

Ensure `rag-aws-portfolio` services are running and healthy, then restart the app:
```bash
docker compose restart document-orchestrator-app
```

## Production Deployment

For production (ECS, Lambda, etc.):

1. **Use managed Postgres** (RDS, Aurora) — update `POSTGRES_DSN` in production `.env`
2. **Remove `build:`** from docker-compose — use pre-built images from ECR
3. **Add secrets management** — use AWS Secrets Manager, not `.env`
4. **Enable TLS** — set `POSTGRES_DSN` to `?sslmode=require`
5. **Scale horizontally** — multiple app containers share the same DB

See `docs/ARCHITECTURE_DIAGRAMS.md` for deployment patterns.
