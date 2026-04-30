"""Pydantic models for the shared entry schema.

Mirrors schema/entry.schema.json. Update both when the schema changes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Ecosystem(str, Enum):
    cargo = "cargo"
    maven = "maven"
    pip = "pip"
    npm = "npm"


class UpdateCategory(str, Enum):
    breaking = "breaking"
    non_breaking = "non-breaking"
    fix_after_update = "fix-after-update"
    unreproducible = "unreproducible"


class AuthorType(str, Enum):
    human = "human"
    bot = "bot"


class BotType(str, Enum):
    dependabot = "dependabot"
    renovate = "renovate"
    snyk = "snyk"
    other = "other"


class VersionUpdateType(str, Enum):
    major = "major"
    minor = "minor"
    patch = "patch"
    other = "other"


class Scope(str, Enum):
    runtime = "runtime"
    dev = "dev"
    build = "build"
    test = "test"
    other = "other"


class TopFailureCategory(str, Enum):
    COMPILATION_FAILURE = "COMPILATION_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    DEPENDENCY_RESOLUTION_FAILURE = "DEPENDENCY_RESOLUTION_FAILURE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    OTHER = "OTHER"


class UnreproducibilityReason(str, Enum):
    pre_breaking_build_failed = "pre_breaking_build_failed"
    breaking_build_passed = "breaking_build_passed"
    external_service_required = "external_service_required"
    toolchain_unavailable = "toolchain_unavailable"
    flaky_tests = "flaky_tests"
    timeout = "timeout"
    network_required = "network_required"
    other = "other"


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    organisation: str
    name: str


class PR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    number: int = Field(ge=1)
    author: str
    authorType: AuthorType
    botType: BotType | None = None
    merged: bool | None = None
    mergedAt: datetime | None = None


class Commits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preBreaking: str = Field(pattern=r"^[a-f0-9]{7,40}$")
    breaking: str = Field(pattern=r"^[a-f0-9]{7,40}$")
    preBreakingAuthorType: AuthorType | None = None
    breakingAuthorType: AuthorType | None = None


class Update(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dependencyName: str
    previousVersion: str
    newVersion: str
    versionUpdateType: VersionUpdateType
    scope: Scope | None = None


class Reproduction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preImage: str
    breakingImage: str
    toolchain: str
    verifiedOn: list[str] = Field(default_factory=list)


class Failure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topCategory: TopFailureCategory
    subCategory: str | None = None
    errorCodes: list[str] = Field(default_factory=list)


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(pattern=r"^(cargo|maven|pip|npm)-[a-f0-9]{7,40}$")
    schemaVersion: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    ecosystem: Ecosystem
    category: UpdateCategory
    project: Project
    pr: PR
    commits: Commits
    update: Update
    reproduction: Reproduction | None = None
    failure: Failure | None = None
    ecosystemMetadata: dict[str, Any] = Field(default_factory=dict)
    unreproducibilityReason: UnreproducibilityReason | None = None
