from tests.conftest import register


def transaction(kind, external_id, amount="100.00", reference="INV-1"):
    return {"kind": kind, "external_id": external_id, "reference": reference, "vendor": "Apex", "amount": amount, "currency": "USD", "transaction_date": "2026-01-10"}


def test_auth_rejects_bad_password(client, auth):
    response = client.post("/api/v1/auth/login", json={"email": "analyst@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_tenant_isolation(client):
    one = register(client, "one@example.com", "Org One"); two = register(client, "two@example.com", "Org Two")
    assert client.post("/api/v1/transactions", headers=one, json=transaction("bank", "B-1")).status_code == 201
    assert len(client.get("/api/v1/transactions", headers=one).json()) == 1
    assert client.get("/api/v1/transactions", headers=two).json() == []


def test_duplicate_transaction_is_blocked(client, auth):
    assert client.post("/api/v1/transactions", headers=auth, json=transaction("bank", "B-1")).status_code == 201
    assert client.post("/api/v1/transactions", headers=auth, json=transaction("bank", "B-1")).status_code == 409


def test_full_reconciliation_workflow(client, auth):
    client.post("/api/v1/transactions", headers=auth, json=transaction("invoice", "I-1"))
    client.post("/api/v1/transactions", headers=auth, json=transaction("bank", "B-1"))
    rule = client.post("/api/v1/rules", headers=auth, json={"name":"Exact","amount_tolerance":"0","date_tolerance_days":1,"fuzzy_threshold":90,"auto_approve_threshold":95})
    response = client.post(f"/api/v1/reconciliations/run?rule_id={rule.json()['id']}", headers=auth)
    assert response.status_code == 200
    assert response.json()["matched_records"] == 1
    dashboard = client.get("/api/v1/dashboard", headers=auth).json()
    assert dashboard["match_percentage"] == 100


def test_invalid_upload_is_rejected(client, auth):
    response = client.post("/api/v1/uploads/csv", headers=auth, files={"file": ("bad.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_demo_anomaly_detection_uses_real_model(client):
    token = client.post("/api/v1/demo/session").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/anomalies/detect", headers=headers)
    assert response.status_code == 200
    assert response.json()["detected"] >= 1
    assert "not confirmed fraud" in response.json()["items"][0]["explanation"]
