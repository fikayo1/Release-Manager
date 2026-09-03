"""Vercel Python serverless entrypoint for the FastAPI backend.

No business logic and no credentials: it re-exports the existing app factory
with the in-process lifespan scheduler disabled. Scheduled scans are driven by
``POST /scheduler/tick`` via Vercel Cron (see ``vercel.json``). Configuration is
read from the environment on the first request (FastAPI lifespan).
"""
# `backend` is the documented Vercel root. The package import also supports a
# repository-root project, where `pyproject.toml` explicitly selects this
# entrypoint instead of letting Vercel guess among the frontend/test modules.
try:
    from backend.src.app import create_app
except ModuleNotFoundError:  # backend is the Python import root
    from src.app import create_app

app = create_app(enable_scheduler=False)
