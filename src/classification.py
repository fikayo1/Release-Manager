"""Deterministic, evidence-backed release-worthiness rules."""
import re
from .models import Bump, Evidence, Scan, Verdict

_DOC=re.compile(r"^(docs?)(\(.+\))?:", re.I)
def classify(scan: Scan) -> Verdict:
    items=scan.pulls or scan.commits
    signals: list[tuple[Bump,Evidence]]=[]
    docs=[]
    for item in items:
        text=item.title
        labels={x.lower() for x in item.labels}
        if labels & {"breaking","breaking-change","breaking change"} or re.search(r"^[a-z]+(?:\([^)]*\))?!:",text,re.I) or "BREAKING CHANGE" in text:
            signals.append((Bump.MAJOR,item))
        elif re.search(r"^feat(?:\(.+\))?:",text,re.I) or labels & {"feature","enhancement"}: signals.append((Bump.MINOR,item))
        elif re.search(r"^fix(?:\(.+\))?:",text,re.I) or labels & {"fix","bug"}: signals.append((Bump.PATCH,item))
        elif _DOC.search(text) or labels == {"documentation"}: docs.append(item.id)
    if not signals:
        ids=tuple(i.id for i in items)
        reason="No changes were found." if not items else ("Changes are documentation-only." if len(docs)==len(items) else "No feature, fix, or breaking-change signal was found.")
        return Verdict(False,Bump.NONE,reason,ids)
    rank={Bump.PATCH:1,Bump.MINOR:2,Bump.MAJOR:3}; bump=max((x[0] for x in signals),key=rank.get)
    cited=tuple(i.id for b,i in signals)
    return Verdict(True,bump,f"A {bump.value} release is required by {len(cited)} classified change(s).",cited)
