"""M2: guard replacement conflicts independently of SQLite recursive triggers."""

import json
from contextlib import contextmanager
from itertools import product

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from studio_manager.agent_registry import TABLES, AgentRegistry
from studio_manager.database import create_database_engine, downgrade_database, upgrade_database
from studio_manager.models import AuditEvent

OLD = "0005_agent_skills_registry"
FIX = "0006_registry_snapshot_guards"
CASES = list(product(("agent", "skill"), ("APPROVED", "RETIRED"), ("pk", "owner_version"), (False, True)))


def all_rows(connection, table):
    return [dict(row) for row in connection.execute(select(table).order_by(table.c.id)).mappings()]


@contextmanager
def seeded(path, revision, kind, state, recursive):
    upgrade_database(path, revision)
    engine = create_database_engine(path)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA recursive_triggers=ON" if recursive else "PRAGMA recursive_triggers=OFF")
            parent, table, fk = TABLES[kind]
            now = "2026-11-11T00:00:00Z"
            owner = {"id": "owner", "code": "owner", "name": "Fixture", "created_at": now}
            if kind == "agent":
                owner.update(role="QA", updated_at=now)
            connection.execute(insert(parent).values(**owner))
            content = "instruction" if kind == "agent" else "instructions"
            connection.execute(insert(table).values(
                id="original", **{fk: "owner", "version": 1, content: "Original snapshot",
                                  "status": state, "created_at": now},
            ))
            connection.execute(insert(AuditEvent.__table__).values(
                actor="fixture", action="SEED", subject_kind="STUDIO_VERSION", subject_id="original",
                after_json=json.dumps({"status": state, "content": "Original snapshot"}), created_at=now,
            ))
            connection.commit()
            yield connection, table, fk, content
    finally:
        engine.dispose()


def replacement_values(connection, table, fk, content, conflict):
    values = all_rows(connection, table)[0].copy()
    values.update(status="DRAFT", **{content: "Replacement attempt"})
    if conflict == "pk":
        values["version"] = 2  # PK conflict only; the owner/version tuple is new.
    else:
        values["id"] = "replacement"  # Unique tuple conflict only; PK is new.
    return values


@pytest.mark.parametrize(("kind", "state", "conflict", "recursive"), CASES)
def test_historical_0005_replace_matrix(database_path, kind, state, conflict, recursive):
    """Document actual old-revision behavior, not a waiver for corrected HEAD."""
    with seeded(database_path, OLD, kind, state, recursive) as (connection, table, fk, content):
        original = all_rows(connection, table)
        values = replacement_values(connection, table, fk, content, conflict)
        try:
            connection.execute(insert(table).prefix_with("OR REPLACE").values(**values))
            connection.commit()
            outcome = "REPLACED"
        except IntegrityError:
            connection.rollback()
            outcome = "BLOCKED"
        resulting = all_rows(connection, table)
        print(json.dumps({"kind": kind, "state": state, "conflict": conflict, "recursive_triggers": recursive,
                          "original": original, "attempt": values, "result": resulting, "outcome": outcome}))
        assert outcome == ("BLOCKED" if recursive else "REPLACED")
        assert resulting == original if recursive else resulting[0][content] == "Replacement attempt"


@pytest.mark.parametrize(("kind", "state", "conflict", "recursive"), CASES)
def test_current_head_blocks_replace(database_path, kind, state, conflict, recursive):
    with seeded(database_path, "head", kind, state, recursive) as (connection, table, fk, content):
        original, audit = all_rows(connection, table), all_rows(connection, AuditEvent.__table__)
        values = replacement_values(connection, table, fk, content, conflict)
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(insert(table).prefix_with("OR REPLACE").values(**values))
        connection.rollback()
        assert all_rows(connection, table) == original
        assert all_rows(connection, AuditEvent.__table__) == audit


@pytest.mark.parametrize(("kind", "state", "recursive", "action"), list(product(
    ("agent", "skill"), ("APPROVED", "RETIRED"), (False, True), ("update", "delete"),
)))
def test_protected_update_delete_remain_blocked(database_path, kind, state, recursive, action):
    with seeded(database_path, "head", kind, state, recursive) as (connection, table, fk, content):
        original, audit = all_rows(connection, table), all_rows(connection, AuditEvent.__table__)
        statement = table.update().values(**{content: "Changed"}) if action == "update" else table.delete()
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(statement.where(table.c.id == "original"))
        connection.rollback()
        assert all_rows(connection, table) == original
        assert all_rows(connection, AuditEvent.__table__) == audit


@pytest.mark.parametrize("kind", ["agent", "skill"])
@pytest.mark.parametrize("recursive", [False, True])
def test_draft_new_versions_remain_functional(database_path, kind, recursive):
    with seeded(database_path, "head", kind, "DRAFT", recursive) as (connection, table, fk, content):
        connection.commit()
        reg = AgentRegistry(connection.engine)
        method = reg.create_agent_version if kind == "agent" else reg.create_skill_version
        version = method("owner", "Next DRAFT snapshot")
        assert version["status"] == "DRAFT" and version["version"] == 2
        assert reg.list_versions(kind, "owner")["count"] == 2
        # DRAFT snapshots were already immutable in0005; no editable-DRAFT mode.
        original = all_rows(connection, table)
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(insert(table).prefix_with("OR REPLACE").values(
                **replacement_values(connection, table, fk, content, "pk")
            ))
        connection.rollback()
        assert all_rows(connection, table) == original


@pytest.mark.parametrize("start", ["base", "0004_phase03a_foundation", OLD])
def test_forward_install_and_security_downgrade_cycle(database_path, start):
    if start == "base":
        upgrade_database(database_path)
        engine = create_database_engine(database_path)
    else:
        upgrade_database(database_path, start)
        engine = create_database_engine(database_path)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO skills(id,name,status) VALUES('legacy','Legacy','IMPORTED')"))
            connection.execute(text(
                "INSERT INTO audit_events(actor,action,subject_kind,subject_id,created_at) "
                "VALUES('fixture','SEED','LEGACY','legacy','now')"
            ))
        engine.dispose()
        upgrade_database(database_path)
        engine = create_database_engine(database_path)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == FIX
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        if start != "base":
            assert connection.execute(text("SELECT COUNT(*) FROM skills WHERE id='legacy'")).scalar_one() == 1
            assert connection.execute(
                text("SELECT COUNT(*) FROM audit_events WHERE subject_id='legacy'")
            ).scalar_one() == 1
    engine.dispose()
    #0006 downgrade must restore0005 exactly, not quietly claim the fix remains.
    downgrade_database(database_path, OLD)
    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == OLD
        trigger_names = set(connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'").scalars())
        assert "prevent_studio_agent_versions_insert" not in trigger_names
        assert "prevent_studio_skill_versions_insert" not in trigger_names
        assert "prevent_studio_agent_versions_update" in trigger_names
        if start != "base":
            assert connection.execute(text("SELECT COUNT(*) FROM skills WHERE id='legacy'")).scalar_one() == 1
    engine.dispose()
    upgrade_database(database_path, FIX)


@pytest.mark.parametrize("kind", ["agent", "skill"])
@pytest.mark.parametrize("state", ["DRAFT", "APPROVED", "RETIRED"])
def test_existing_0005_snapshots_and_audit_survive_migration_cycle(database_path, kind, state):
    schema_query = text(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE type IN ('table','index') ORDER BY type,name"
    )
    with seeded(database_path, OLD, kind, state, False) as (connection, table, fk, content):
        original, audit = all_rows(connection, table), all_rows(connection, AuditEvent.__table__)
        schema = connection.execute(schema_query).fetchall()
    for revision in (FIX, OLD, FIX):
        if revision == OLD:
            downgrade_database(database_path, OLD)
        else:
            upgrade_database(database_path, FIX)
        engine = create_database_engine(database_path)
        try:
            with engine.connect() as connection:
                assert all_rows(connection, table) == original
                assert all_rows(connection, AuditEvent.__table__) == audit
                assert connection.execute(schema_query).fetchall() == schema
                assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
                assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        finally:
            engine.dispose()


@pytest.mark.parametrize("kind", ["agent", "skill"])
def test_foreign_keys_checks_and_parent_uniqueness_preserved(database_path, kind):
    with seeded(database_path, "head", kind, "DRAFT", False) as (connection, table, fk, content):
        original = all_rows(connection, table)[0]
        audit = all_rows(connection, AuditEvent.__table__)
        parent = TABLES[kind][0]
        parent_row = all_rows(connection, parent)[0]
        attempts = (
            insert(table).values(**{**original, "id": "new_fk", "version": 2, fk: "missing"}),
            insert(table).values(**{**original, "id": "new_zero", "version": 0}),
            insert(table).values(**{**original, "id": "new_status", "version": 2, "status": "INVALID"}),
            insert(parent).values(**{**parent_row, "id": "duplicate_code"}),
            parent.update().values(enabled=2).where(parent.c.id == "owner"),
            parent.delete().where(parent.c.id == "owner"),
        )
        for statement in attempts:
            with pytest.raises(IntegrityError):
                connection.execute(statement)
            connection.rollback()
            assert all_rows(connection, table) == [original]
            assert all_rows(connection, parent) == [parent_row]
            assert all_rows(connection, AuditEvent.__table__) == audit
