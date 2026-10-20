import pytest
from fastapi import HTTPException

from app.routes import require_import_key, validate_import_content_type


def test_import_requires_secret_key(monkeypatch):
    monkeypatch.setenv('IMPORT_API_KEY', 'x' * 32)
    with pytest.raises(HTTPException, match='valid X-Import-Key'):
        require_import_key(None)
    require_import_key('x' * 32)


def test_import_requires_configured_secret(monkeypatch):
    monkeypatch.delenv('IMPORT_API_KEY', raising=False)
    with pytest.raises(HTTPException, match='Configure an IMPORT_API_KEY'):
        require_import_key(None)


@pytest.mark.parametrize('content_type', ['application/json', None, 'text/plain'])
def test_import_accepts_only_csv_content_type(content_type):
    with pytest.raises(HTTPException) as error:
        validate_import_content_type(content_type)
    assert error.value.status_code == 415


def test_import_accepts_csv_content_type_parameters():
    validate_import_content_type('text/csv; charset=utf-8')
