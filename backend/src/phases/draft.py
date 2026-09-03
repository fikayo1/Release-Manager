from uuid import uuid4
from ..pack import build_pack

def draft(store,scan,verdict,now):
    if not verdict.worthy: return None
    pack=build_pack(scan,verdict,str(uuid4())); store.save_pack(pack,now); return pack
