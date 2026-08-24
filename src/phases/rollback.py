def reconcile(store,github,pack_id,now):
    pack=store.pack(pack_id)
    if pack["status"]!="uncertain": raise ValueError("only uncertain publications can be reconciled")
    found=github.release_for_tag(pack["tag"])
    if found is None: result="absent"
    elif found.title==pack["title"] and found.body==pack["body"]: result="matching"
    else: result="conflict"
    store.reconcile(pack_id,result,now); return result
