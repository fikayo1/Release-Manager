from tests.test_review_ui import GitHub, add_pack, client_for


def test_api_requires_reasons_and_approval_publishes(tmp_path):
    gh = GitHub(); client, store = client_for(tmp_path, gh); add_pack(store)
    assert client.post("/api/packs/p/approve", json={"actor":"alice", "reason":" "}).status_code == 409
    response = client.post("/api/packs/p/approve", json={"actor":"alice", "reason":"reviewed"})
    assert response.status_code == 200 and response.json()["status"] == "published" and gh.writes == 1


def test_api_rejection_never_publishes(tmp_path):
    gh = GitHub(); client, store = client_for(tmp_path, gh); add_pack(store)
    response = client.post("/api/packs/p/reject", json={"actor":"bob", "reason":"unsafe"})
    assert response.status_code == 200 and response.json()["status"] == "rejected" and gh.writes == 0


def test_api_publication_failure_is_not_success(tmp_path):
    client, store = client_for(tmp_path, GitHub(True)); add_pack(store)
    response = client.post("/api/packs/p/approve", json={"actor":"alice", "reason":"reviewed"})
    assert response.status_code == 502 and store.pack("p")["status"] == "uncertain"
