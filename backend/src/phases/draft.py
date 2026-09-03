from uuid import uuid4
from ..pack import build_pack

def draft(store,scan,verdict,now):
    if not verdict.worthy: return None
    pack=build_pack(scan,verdict,str(uuid4()))
    # Repeated scans of unchanged evidence reuse the current repository/version
    # pack. This is safe for legacy stores and complements the user-scoped
    # database key used by authenticated requests.
    for existing in store.packs():
        try:
            prior_scan = store.scan(existing["scan_id"])
            if prior_scan.get("repository") == scan.repository and existing.get("version") == pack.version:
                return type(pack)(existing["id"], scan.id, pack.version, pack.tag, pack.title,
                                  pack.body, pack.announcement, pack.rationale, pack.claims, pack.status)
        except KeyError:
            pass
    store.save_pack(pack,now); return pack
