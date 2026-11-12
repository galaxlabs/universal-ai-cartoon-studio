"""Typed mappings; migrations, never create_all(), own the database schema."""

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from studio_manager.models import Base


class StudioAgent(Base):
    __tablename__ = "studio_agents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class StudioSkill(Base):
    __tablename__ = "studio_skills"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text)


class StudioAgentVersion(Base):
    __tablename__ = "studio_agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("studio_agents.id"))
    version: Mapped[int] = mapped_column(Integer)
    instruction: Mapped[str] = mapped_column(Text)
    model_profile: Mapped[str] = mapped_column(Text)
    allowed_tools_json: Mapped[str] = mapped_column(Text)
    allowed_skills_json: Mapped[str] = mapped_column(Text)
    config_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)


class StudioSkillVersion(Base):
    __tablename__ = "studio_skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("studio_skills.id"))
    version: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str] = mapped_column(Text)
    input_schema_json: Mapped[str] = mapped_column(Text)
    output_schema_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
