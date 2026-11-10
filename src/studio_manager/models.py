from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(Text)
    root_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
    series: Mapped[list[Series]] = relationship(back_populates="project")


class Series(Base):
    __tablename__ = "series"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    premise: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    project: Mapped[Project] = relationship(back_populates="series")
    episodes: Mapped[list[Episode]] = relationship(back_populates="series")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("series_id", "code"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"))
    code: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    series: Mapped[Series] = relationship(back_populates="episodes")
    scenes: Mapped[list[Scene]] = relationship(back_populates="episode")


class Scene(Base):
    __tablename__ = "scenes"
    __table_args__ = (UniqueConstraint("episode_id", "code"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"))
    code: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    episode: Mapped[Episode] = relationship(back_populates="scenes")
    shots: Mapped[list[Shot]] = relationship(back_populates="scene")


class Shot(Base):
    __tablename__ = "shots"
    __table_args__ = (UniqueConstraint("scene_id", "code"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id"))
    code: Mapped[str] = mapped_column(Text)
    frame_start: Mapped[int | None] = mapped_column(Integer)
    frame_end: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(Text)
    scene: Mapped[Scene] = relationship(back_populates="shots")


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    bible_status: Mapped[str] = mapped_column(Text)
    variants: Mapped[list[CharacterVariant]] = relationship(back_populates="character")


class CharacterVariant(Base):
    __tablename__ = "character_variants"
    __table_args__ = (UniqueConstraint("character_id", "code"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"))
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
    character: Mapped[Character] = relationship(back_populates="variants")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    asset_type: Mapped[str] = mapped_column(Text)
    lifecycle_state: Mapped[str] = mapped_column(Text)
    protected: Mapped[int] = mapped_column(Integer, default=0)
    versions: Mapped[list[AssetVersion]] = relationship(back_populates="asset")


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (UniqueConstraint("asset_id", "version"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    workspace_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    asset: Mapped[Asset] = relationship(back_populates="versions")


class Job(Base):
    __tablename__ = "production_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    job_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    target_application: Mapped[str | None] = mapped_column(Text)
    workspace_path: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str] = mapped_column(Text)
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_kind: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    dry_run: Mapped[int] = mapped_column(Integer, default=0)
    counts_json: Mapped[str] = mapped_column(Text, default="{}")
    unknown_fields_path: Mapped[str | None] = mapped_column(Text)
    error_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)


class ImportRecord(Base):
    __tablename__ = "import_records"
    __table_args__ = (UniqueConstraint("source_kind", "source_key"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    source_kind: Mapped[str] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(Text)
    target_kind: Mapped[str] = mapped_column(Text)
    target_id: Mapped[str] = mapped_column(Text)
    target_fingerprint: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[str] = mapped_column(Text)


class BackupRecord(Base):
    __tablename__ = "backups"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    restore_tested: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    api_token_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
