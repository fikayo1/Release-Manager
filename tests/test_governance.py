import pytest
from src.models import Bump,Claim,Pack
from src.store import StateError,Store

def pack(): return Pack("p","s","0.1.0","v0.1.0","Release v0.1.0","body","copy","minor",(Claim("Features","x","e"),))
def setup(tmp_path):
 st=Store(str(tmp_path/"db"))
 with st.connect() as db: db.execute("INSERT INTO scans VALUES('s','{}','now')")
 st.save_pack(pack(),"now"); return st
def test_publish_requires_human_approval_and_decision_is_terminal(tmp_path):
 st=setup(tmp_path)
 with pytest.raises(StateError): st.claim_publish("p","now")
 st.decide("p","approved","alice","reviewed and ready","now")
 with pytest.raises(StateError): st.decide("p","rejected","bob","no","later")
 assert st.claim_publish("p","later")
def test_rejection_requires_reason_and_is_retained(tmp_path):
 st=setup(tmp_path)
 with pytest.raises(StateError): st.decide("p","rejected","alice","","now")
 st.decide("p","rejected","alice","unsafe","now")
 assert st.pack("p")["status"]=="rejected"
 assert any(x["kind"]=="decision" for x in st.audit())
