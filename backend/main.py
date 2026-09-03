"""Vercel FastAPI entrypoint for the backend deployment.

This project is deliberately deployed separately from the Next.js console.
Vercel discovers this ``app`` as a FastAPI application and serves its native
``/health``, ``/api/*``, OAuth, and scheduler routes without Next rewrites.
"""
from src.app import create_app

app = create_app(enable_scheduler=False)
