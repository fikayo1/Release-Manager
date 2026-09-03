"""Canonical human review transitions."""


def approve(store, pack_id, actor, reason, now):
    store.decide(pack_id, "approved", actor, reason, now)


def reject(store, pack_id, actor, reason, now):
    store.decide(pack_id, "rejected", actor, reason, now)
