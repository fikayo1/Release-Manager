"""The smoke test.

One test, always passing, present from the first commit. Its job is not to
verify the product — there is no product yet. Its job is to prove the suite
runs, so that the first red result means something.
"""

from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app)


def test_health_reports_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
