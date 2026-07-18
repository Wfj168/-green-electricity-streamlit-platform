from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    inputs: dict[str, Any]


class JobCreate(BaseModel):
    scenario_version_id: str
    model_kind: Literal["realtime_dispatch", "integrated_planning"] = "realtime_dispatch"
    request: dict[str, Any] = Field(default_factory=dict)


class JobTransition(BaseModel):
    action: str


class TokenRequest(BaseModel):
    bootstrap_key: str
    user_id: str = Field(min_length=1, max_length=120)
    role: str
