"""Pure release-pack generation from a stored snapshot and verdict."""
from .models import Bump, Claim, Pack, Scan, Verdict
from .versioning import next_version

def build_pack(scan: Scan, verdict: Verdict, pack_id: str) -> Pack:
    if not verdict.worthy: raise ValueError("a non-release-worthy scan cannot be drafted")
    version,tag=next_version(scan.baseline_tag,verdict.bump)
    items=scan.pulls or scan.commits; claims=[]
    sections={"Features":[],"Fixes":[],"Other":[]}
    for item in items:
        low=item.title.lower(); labels={x.lower() for x in item.labels}
        section="Features" if low.startswith("feat") or labels & {"feature","enhancement"} else "Fixes" if low.startswith("fix") or labels & {"fix","bug"} else "Other"
        text=f"{item.title} ([{item.id}]({item.url}))"
        sections[section].append(f"- {text}"); claims.append(Claim(section,text,item.id))
    body="\n\n".join(f"## {name}\n"+"\n".join(lines) for name,lines in sections.items() if lines)
    rationale=f"{verdict.bump.value.title()} bump to {version}: {verdict.reason}"
    # The bump itself is traceable to every classified signal.
    claims.extend(Claim("Version rationale",rationale,eid) for eid in verdict.evidence_ids)
    return Pack(pack_id,scan.id,version,tag,f"Release {tag}",body,f"Release {tag} is ready: {len(items)} change(s).",rationale,tuple(claims))
