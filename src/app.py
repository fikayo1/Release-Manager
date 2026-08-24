"""The seed application.

Deliberately almost empty. It exists so that the test suite is GREEN the moment
bootstrap finishes — which is what lets a later phase tell "I broke this" from
"this was already broken". A scaffold that starts red teaches an agent that red
is normal.

Layers, innermost first: models -> github_client -> phases -> routes.
Dependencies run downward only. This app becomes the review interface and API
surface a later `routes` layer builds on top of `/health` — not a separate app.
"""

from fastapi import FastAPI

app = FastAPI(title="release-manager")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
