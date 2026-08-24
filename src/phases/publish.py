def publish(store,github,pack_id,now):
    pack=store.pack(pack_id); attempt=store.claim_publish(pack_id,now)
    try:
        receipt=github.create_release(pack["tag"],pack["title"],pack["body"])
    except Exception as exc:
        store.finish(pack_id,attempt,"uncertain",now,error=str(exc),status="uncertain"); raise
    store.finish(pack_id,attempt,"success",now,url=receipt.html_url); return receipt
