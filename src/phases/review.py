def approve(store,pack_id,actor,now): store.decide(pack_id,"approved",actor,None,now)
def reject(store,pack_id,actor,reason,now): store.decide(pack_id,"rejected",actor,reason,now)
