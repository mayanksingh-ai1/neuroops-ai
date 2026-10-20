from app.main import health_check


def test_health_endpoint_reports_api_process() -> None:
    assert health_check() == {"status": "ok", "service": "neuroops-api"}
