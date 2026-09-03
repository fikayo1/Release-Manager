from uuid import uuid4
from ..pack import build_pack

def draft(store,scan,verdict,now,user_id=None):
    if not verdict.worthy: return None
    pack=build_pack(scan,verdict,str(uuid4()))
    # Authenticated creation is an atomic, durable upsert keyed by identity,
    # repository and version.  Every scan remains immutable while the one
    # current pack is refreshed to point at the newest evidence snapshot.
    if user_id:
        return store.save_current_pack(pack, now, user_id, scan.repository)
    # Legacy/injected clients retain their original single-operator behavior.
    for existing in store.packs():
        try:
            prior_scan = store.scan(existing["scan_id"])
            if prior_scan.get("repository") == scan.repository and existing.get("version") == pack.version:
                return type(pack)(existing["id"], scan.id, pack.version, pack.tag, pack.title,
                                  pack.body, pack.announcement, pack.rationale, pack.claims, pack.status)
        except KeyError:
            pass
    store.save_pack(pack,now); return pack
