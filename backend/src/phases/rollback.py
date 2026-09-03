from ..store import StateError


def reconcile(store, github, pack_id, now):
    pack = store.pack(pack_id)
    if pack["status"] not in ("publishing", "uncertain"):
        raise StateError("only interrupted or uncertain publications can be reconciled")
    found = github.release_for_tag(pack["tag"])
    if found is None:
        result, detail, url = "absent", "no release exists for the intended tag", None
    elif found.title == pack["title"] and found.body == pack["body"]:
        result, detail, url = "matching", "GitHub release matches the approved pack", found.html_url
    else:
        result, detail, url = "conflict", "tag exists with different title or body", found.html_url
    store.reconcile(pack_id, result, now, detail, url)
    return result
