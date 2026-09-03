from fastapi.testclient import TestClient
from src.app import create_app


def test_health_reports_ok():
 with TestClient(create_app(validate=False)) as client:
  response=client.get('/health')
 assert response.status_code==200 and response.json()=={'status':'ok'}


def test_health_reports_safe_configuration_failure(monkeypatch):
 for name in (
     'GITHUB_OAUTH_CLIENT_ID', 'GITHUB_OAUTH_CLIENT_SECRET',
     'GITHUB_OAUTH_CALLBACK_URL', 'SESSION_SECRET', 'RELEASE_MANAGER_WEB_URL',
 ):
  monkeypatch.delenv(name, raising=False)
 with TestClient(create_app(enable_scheduler=False)) as client:
  response=client.get('/health')
 assert response.status_code==503
 assert response.json()['kind']=='configuration'
 assert 'Missing required configuration' in response.json()['detail']
