from fastapi.testclient import TestClient

from demo.app import app


def test_synthetic_demo_renders_core_product_views_without_external_services():
    client = TestClient(app)

    dashboard = client.get("/dashboard")
    plan = client.get("/plan")
    review = client.get("/weekly-review")

    assert dashboard.status_code == 200
    assert "Training · 28 days" in dashboard.text
    assert "Autumn 10K" in client.get("/").text
    assert plan.status_code == 200
    assert "Controlled 10 km-specific cruise intervals" in plan.text
    assert review.status_code == 200
    assert "Training was consistent" in review.text
