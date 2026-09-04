"""C2: frontend and FastAPI use separate Vercel projects, not rewrites."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BACKEND_ENV = [
    "DATABASE_URL", "POSTGRES_URL", "RELEASE_MANAGER_WEB_URL",
    "GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET", "GITHUB_OAUTH_CALLBACK_URL",
    "SESSION_SECRET", "CRON_SECRET",
]
FRONTEND_ENV = ["RELEASE_MANAGER_API_URL", "CRON_SECRET"]

FORBIDDEN = [
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "railway.json",
    "railway.toml", "render.yaml", "fly.toml", "Procfile", "app.yaml", "vercel-alt.json",
]


def test_frontend_vercel_project_has_only_next_and_cron_configuration():
    config = json.loads((ROOT / "frontend" / "vercel.json").read_text())
    assert "rewrites" not in config
    assert "api/index.py" not in json.dumps(config)
    assert config["functions"]["app/api/cron/scheduler/route.ts"]["maxDuration"] == 60
    # Every minute must be evaluated: user schedules can select any minute,
    # hour, weekday, day-of-month, and month in their five-field expression.
    assert config["crons"] == [
        {"path": "/api/cron/scheduler", "schedule": "* * * * *"}
    ]


def test_backend_has_a_native_fastapi_entrypoint_and_dependencies():
    source = (ROOT / "backend" / "api" / "index.py").read_text()
    assert "from src.app import create_app" in source
    assert "enable_scheduler=False" in source
    assert "fastapi" in (ROOT / "backend" / "requirements.txt").read_text().lower()
    config = json.loads((ROOT / "backend" / "vercel.json").read_text())
    assert config["functions"]["api/index.py"]["maxDuration"] == 60
    assert config["rewrites"] == [{"source": "/(.*)", "destination": "/api/index.py"}]


def test_env_examples_split_frontend_and_backend_configuration():
    lines = (ROOT / "backend" / ".env.example").read_text().splitlines()
    assignments = {line.split("=", 1)[0].strip(): line.split("=", 1)[1].strip()
                   for line in lines if "=" in line and not line.strip().startswith("#")}
    for name in BACKEND_ENV:
        assert name in assignments, f"{name} missing from backend/.env.example"
    frontend = (ROOT / "frontend" / ".env.example").read_text()
    for name in FRONTEND_ENV:
        assert f"{name}=" in frontend
    # Placeholders only: no real-looking GitHub token or long secret material.
    blob = (ROOT / "backend" / ".env.example").read_text() + frontend
    assert "ghp_" not in blob
    assert "ghs_" not in blob


def test_no_second_hosting_platform_descriptor_is_present():
    for name in FORBIDDEN:
        matches = list(ROOT.rglob(name))
        matches = [m for m in matches if "node_modules" not in m.parts and ".venv" not in m.parts]
        assert not matches, f"unexpected second-platform config: {matches}"
