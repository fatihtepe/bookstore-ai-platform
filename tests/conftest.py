import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(app):
    return app.test_client()
