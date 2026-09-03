"""Typed domain contracts for immutable evidence and governed release state."""
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

class Bump(StrEnum): NONE="none"; PATCH="patch"; MINOR="minor"; MAJOR="major"
class PackStatus(StrEnum): PENDING="pending"; APPROVED="approved"; REJECTED="rejected"; PUBLISHING="publishing"; PUBLISHED="published"; UNCERTAIN="uncertain"; RETRY_SAFE="retry_safe"; CONFLICT="conflict"

@dataclass(frozen=True)
class Repository: default_branch: str; created_at: str; html_url: str
@dataclass(frozen=True)
class Release: tag: str; title: str; body: str; published_at: str; html_url: str
@dataclass(frozen=True)
class Evidence:
    id: str; kind: str; title: str; author: str; occurred_at: str; url: str
    labels: tuple[str,...]=(); sha: str=""
@dataclass(frozen=True)
class Scan:
    id: str; repository: str; captured_at: str; cutoff: str; no_prior_release: bool
    baseline_tag: str|None; commits: tuple[Evidence,...]; pulls: tuple[Evidence,...]
@dataclass(frozen=True)
class Verdict:
    worthy: bool; bump: Bump; reason: str; evidence_ids: tuple[str,...]
@dataclass(frozen=True)
class Claim:
    section: str; text: str; evidence_id: str
@dataclass(frozen=True)
class Pack:
    id: str; scan_id: str; version: str; tag: str; title: str; body: str; announcement: str
    rationale: str; claims: tuple[Claim,...]; status: PackStatus=PackStatus.PENDING

def primitive(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"): return {k: primitive(v) for k,v in asdict(value).items()}
    if isinstance(value, (tuple,list)): return [primitive(v) for v in value]
    if isinstance(value, StrEnum): return value.value
    return value
