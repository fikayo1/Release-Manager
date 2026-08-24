def publish(store,github,pack_id,now):
    pack=store.pack(pack_id); attempt=store.claim_publish(pack_id,now)
    try:
        receipt=github.create_release(pack["tag"],pack["title"],pack["body"])
    except Exception:
        # Persist a safe outcome without copying arbitrary transport text (which
        # may contain headers or credentials) into the audit database.
        store.finish(pack_id,attempt,"uncertain",now,error="GitHub publication outcome is unknown",status="uncertain"); raise
    store.finish(pack_id,attempt,"success",now,url=receipt.html_url); return receipt
