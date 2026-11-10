from __future__ import annotations

import json
from typing import Annotated, Self

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ConfigDict, Field, model_validator

Code = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_-]+$")]
Label = Annotated[str, Field(min_length=1, max_length=160)]
Reference = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]


def bounded_json(value: dict, *, schema: bool = False) -> None:
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("metadata must be finite JSON") from exc
    if len(encoded.encode("utf-8")) > 16384:
        raise ValueError("metadata must not exceed 16 KiB")

    def walk(node: object, depth: int = 0) -> None:
        if depth > 12:
            raise ValueError("metadata nesting must not exceed 12 levels")
        if isinstance(node, dict):
            for key, child in node.items():
                if schema and key in {"$ref", "$dynamicRef"} and (
                    not isinstance(child, str) or not child.startswith("#")
                ):
                    raise ValueError("only local schema references are permitted")
                walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                walk(child, depth + 1)

    walk(value)
    if schema:
        dialect = value.get("$schema", "https://json-schema.org/draft/2020-12/schema")
        if dialect != "https://json-schema.org/draft/2020-12/schema":
            raise ValueError("only JSON Schema draft 2020-12 is supported")
        try:
            Draft202012Validator.check_schema(value)
        except SchemaError as exc:
            raise ValueError("invalid JSON Schema draft 2020-12 declaration") from exc


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentCreate(StrictPayload):
    code: Code
    name: Label
    role: Annotated[str, Field(min_length=1, max_length=80)]
    description: Annotated[str, Field(max_length=2000)] = ""


class SkillCreate(StrictPayload):
    code: Code
    name: Label
    description: Annotated[str, Field(max_length=2000)] = ""


class AgentVersionCreate(StrictPayload):
    instruction: Annotated[str, Field(min_length=1, max_length=50000)]
    model_profile: Annotated[str, Field(max_length=128)] = ""
    allowed_tools: Annotated[list[Reference], Field(max_length=50)] = Field(default_factory=list)
    allowed_skills: Annotated[list[Reference], Field(max_length=50)] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_metadata(self) -> Self:
        bounded_json(self.config)
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("duplicate tool references")
        if len(set(self.allowed_skills)) != len(self.allowed_skills):
            raise ValueError("duplicate skill-version references")
        return self


class SkillVersionCreate(StrictPayload):
    instructions: Annotated[str, Field(min_length=1, max_length=50000)]
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_schemas(self) -> Self:
        bounded_json(self.input_schema, schema=True)
        bounded_json(self.output_schema, schema=True)
        return self
