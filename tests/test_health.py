from fastapi.testclient import TestClient
from src.app import create_app
def test_health_reports_ok():
 with TestClient(create_app(validate=False)) as client:
  response=client.get('/health')
 assert response.status_code==200 and response.json()=={'status':'ok'}
