"""Shipyard integration declaration.

The checkout exposes no importable Shipyard runtime API. This manifest is not a
substitute engine: the deployment harness should register these callables and
mandatory gate with its genuine runtime.
"""
from dataclasses import dataclass
from typing import Callable
from .phases import scan,draft,approve,publish,reconcile
@dataclass(frozen=True)
class Phase: name:str; function:Callable; gate:str|None=None
PHASES=(Phase("scan",scan),Phase("draft",draft),Phase("review",approve,"mandatory-human-approval"),Phase("publish",publish,"approved-pack-only"),Phase("rollback",reconcile))
