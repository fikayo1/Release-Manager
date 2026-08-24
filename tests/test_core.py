from src.classification import classify
from src.models import Bump,Evidence,Scan
from src.pack import build_pack
from src.versioning import next_version

def snapshot(title="feat: launch"):
 e=Evidence("PR-1","pull",title,"alice","2026-01-02T00:00:00Z","https://github/x/1")
 return Scan("s","o/r","now","2026-01-01T00:00:00Z",True,None,(),(e,))
def test_worthy_pack_is_traceable():
 s=snapshot(); v=classify(s); p=build_pack(s,v,"p")
 assert v.worthy and v.bump==Bump.MINOR and p.version=="0.1.0"
 assert all(c.evidence_id=="PR-1" for c in p.claims)
def test_docs_are_not_worthy(): assert not classify(snapshot("docs: improve guide")).worthy
def test_semver_precedence():
 assert next_version("v1.2.3",Bump.PATCH)==("1.2.4","v1.2.4")
 assert next_version("1.2.3",Bump.MINOR)[0]=="1.3.0"
 assert next_version("1.2.3",Bump.MAJOR)[0]=="2.0.0"
