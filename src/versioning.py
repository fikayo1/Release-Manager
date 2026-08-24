"""Strict semantic version calculation."""
import re
from .models import Bump
_PATTERN=re.compile(r"^(v?)(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

def next_version(previous: str|None, bump: Bump) -> tuple[str,str]:
    if bump is Bump.NONE: raise ValueError("a release requires a version bump")
    prefix=""
    if previous is None: major=minor=patch=0
    else:
        match=_PATTERN.fullmatch(previous)
        if not match: raise ValueError(f"latest release tag is not semantic version: {previous}")
        prefix, major, minor, patch=match.group(1), *map(int, match.groups()[1:])
    if bump is Bump.MAJOR: major,minor,patch=major+1,0,0
    elif bump is Bump.MINOR: minor,patch=minor+1,0
    else: patch+=1
    version=f"{major}.{minor}.{patch}"
    return version, prefix+version
