# ADR-0001 — Local-first modular monolith

Status: Proposed for Phase 1 approval

## Context
The workstation has 16 GB RAM, a 4-core/8-thread Xeon, Quadro P3000 6 GB and limited C: free space. Essential studio management must work without cloud services.

## Decision
Use one loopback FastAPI application, one SQLite database and one local worker. Keep application modules separate in code but avoid Redis, Celery, PostgreSQL, containers and public endpoints until measured requirements demand them.

## Consequences
- Lower operational and memory cost.
- Simpler backups and rollback.
- Write jobs are serialized initially.
- Future PostgreSQL migration remains possible through SQLAlchemy/Alembic.
