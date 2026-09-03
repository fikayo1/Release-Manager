"""C2: repository-only Vercel artifacts exist and no second platform is added."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ENV = [
    "DATABASE_URL", "POSTGRES_URL", "RELEASE_MANAGER_WEB_URL", "RELEASE_MANAGER_API_URL",
    "GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET", "GITHUB_OAUTH_CALLBACK_URL",
    "SESSION_SECRET", "CRON_SECRET",
]

FORBIDDEN = [
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "railway.json",
    "railway.toml", "render.yaml", "fly.toml", "Procfile", "app.yaml", "vercel-alt.json",
]


def test_vercel_json_references_the_next_app_and_python_function():
    config = json.loads((ROOT / "vercel.json").read_text())
    text = json.dumps(config)
    assert "api/index.py" in text
    assert "crons" in config and config["crons"]
    assert any("/api/cron/scheduler" in c.get("path", "") for c in config["crons"])
    assert config["crons"] == [
        {"path": "/api/cron/scheduler", "schedule": "0 9 * * *"}
    ]


def test_python_entrypoint_imports_the_app_and_disables_the_scheduler():
    source = (ROOT / "api" / "index.py").read_text()
    assert "from src.app import create_app" in source
    assert "enable_scheduler=False" in source


def test_env_example_lists_names_with_placeholder_values_only():
    lines = (ROOT / ".env.example").read_text().splitlines()
    assignments = {line.split("=", 1)[0].strip(): line.split("=", 1)[1].strip()
                   for line in lines if "=" in line and not line.strip().startswith("#")}
    for name in REQUIRED_ENV:
        assert name in assignments, f"{name} missing from .env.example"
    # Placeholders only: no real-looking GitHub token or long secret material.
    blob = (ROOT / ".env.example").read_text()
    assert "ghp_" not in blob
    assert "ghs_" not in blob


def test_no_second_hosting_platform_descriptor_is_present():
    for name in FORBIDDEN:
        matches = list(ROOT.rglob(name))
        matches = [m for m in matches if "node_modules" not in m.parts and ".venv" not in m.parts]
        assert not matches, f"unexpected second-platform config: {matches}"
