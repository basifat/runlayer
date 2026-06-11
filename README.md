# RunLayer

Validate AI outputs through pluggable validators and produce signed, shareable proof artifacts.

**Status: early stage.** The core validation API and the Python SDK are implemented; everything else (web UI, TypeScript SDK, CLI) is planned. See [Roadmap](#roadmap).

## Why

AI output is probabilistic; most systems that consume it need something deterministic to trust. RunLayer sits between an AI system and its consumers: outputs are run through validators (schema checks, business rules, custom code), and successful validation produces a cryptographically signed proof artifact that can be stored, shared, and verified independently.

## What exists today

```
runlayer/
├── packages/
│   ├── core/                # Validation API (FastAPI)
│   │   ├── src/validators/  # Validator registry, execution framework, sandboxed Python executor
│   │   ├── src/proofs/      # Proof generation, signing, and storage
│   │   ├── src/storage/     # Content-addressed artifact storage (S3-compatible)
│   │   ├── src/redis/       # Cache, sessions, and job queue
│   │   ├── alembic/         # Database migrations (multi-tenant PostgreSQL)
│   │   └── tests/
│   └── sdk/
│       └── python/          # Python SDK: client, validator base classes, crypto utils
├── scripts/                 # Story-driven PR automation (see Development workflow)
└── docs/archive/            # Working documents from implemented stories
```

## Tech stack

- **API**: FastAPI (Python 3.11+), JWT auth, rate limiting, correlation-ID request tracing
- **Database**: PostgreSQL (async SQLAlchemy 2.0, Alembic migrations, multi-tenant)
- **Cache/queue**: Redis
- **Artifact storage**: S3-compatible object storage (boto3)
- **Proofs**: `cryptography`-based signing of validation results
- **Monorepo**: Turborepo workspaces

## Quick start

Prerequisites: Python 3.11+, PostgreSQL, and Redis running locally.

### Core API

```bash
cd packages/core
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configuration comes from environment variables (12-factor).
# See .env.example at the repo root for the full list.
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/runlayer"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="dev-secret-key-at-least-32-characters-long"

alembic upgrade head
uvicorn src.main:app --reload   # API at http://localhost:8000, docs at /docs
```

### Python SDK

```bash
cd packages/sdk/python
pip install -e .
python examples/basic_usage.py
```

### Tests

```bash
cd packages/core && pytest          # coverage gate at 80%
cd packages/sdk/python && pytest
```

## Development workflow

The project is built in story-sized increments, each landing as a reviewed PR. PR descriptions are generated from `stories-config.yml` by `scripts/auto-pr-generator.py`; the working documents for completed stories are kept in `docs/archive/` for reference.

## Roadmap

- TypeScript SDK
- CLI for running validators locally
- Web UI for browsing proofs
- Validator marketplace / sharing

## License

MIT
