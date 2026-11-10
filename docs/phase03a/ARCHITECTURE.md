# Phase 03-A Architecture

## Implemented
- The existing `src/studio_manager/` modular monolith remains authoritative; no competing backend was introduced.
- FastAPI owns the loopback application and exposes legacy `/api` compatibility plus authenticated `/api/v1` records.
- Pydantic v2 validates request contracts. SQLAlchemy 2.x owns database connectivity and typed ORM mappings. Alembic owns schema history.
- SQLite remains the system of record with foreign keys, WAL, synchronous `FULL`, a 5-second busy timeout, short transactions, and the native single-writer rule.
- Domain services are separated into catalog/lifecycle, Phase 03-A query/update, import, secure local storage, backup/recovery, and authorization modules.
- Binary payloads remain outside SQLite. The database stores paths, hashes, lifecycle states, provenance, and evidence.
- Phase 02 worker and MCP gateway behavior remains registered and unchanged. Phase 03-A stores jobs but adds no arbitrary execution route.

## Main components
- `models.py`: typed mappings for the 16 required domain models plus `ImportRecord` provenance.
- `service.py`: existing catalog, asset-version, job, and approval lifecycle transactions.
- `phase03a_service.py`: allow-listed filtering, pagination, updates, restricted deletes, variants, and audit writes.
- `storage_service.py`: confined create-only atomic file storage with SHA-256.
- `import_service.py`: source-specific Phase 02 adapters and conflict-aware import batches.
- `backup_service.py`: online SQLite snapshots, hash registration, integrity checks, and confined recovery copies.
- `api_v1.py`: authenticated local REST surface.

## Boundaries
- Listener: `127.0.0.1` only.
- Protected Blender sources: read-only and outside every managed write root.
- Managed writes: project storage zones only.
- Production approval: explicit lifecycle transition plus append-only approval evidence.
- No public CORS, shell endpoint, Python endpoint, arbitrary job runner, or new MCP execution surface.

## Deliberately deferred
- Phase 03-B frontend work.
- Multi-user identity provider and remote authentication.
- Full binary corpus backup; Phase 03-A backup covers SQLite and separately hashed managed-file references.
