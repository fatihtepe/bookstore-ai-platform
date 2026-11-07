"""AI search tests use a fake Claude client, so they run without an API key or cost."""
from types import SimpleNamespace

import pytest

from app import ask, create_app


class FakeClaude:
    def __init__(self, content, stop_reason="tool_use"):
        self.response = SimpleNamespace(content=content, stop_reason=stop_reason)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def tool_use(**args):
    return SimpleNamespace(type="tool_use", name="search_books", input=args)


def text(t):
    return SimpleNamespace(type="text", text=t)


@pytest.fixture
def make_client(tmp_path):
    def _make(fake):
        return create_app(f"sqlite:///{tmp_path / 'ask.db'}", ai_client=fake).test_client()
    return _make


def test_question_becomes_validated_search(make_client):
    fake = FakeClaude([tool_use(title_contains=None, author_contains="Kafka", is_sold=False, limit=None)])
    resp = make_client(fake).get("/books/ask?q=unsold books by Kafka")
    assert resp.status_code == 200
    assert resp.json["filters"]["author_contains"] == "Kafka"
    assert [b["title"] for b in resp.json["books"]] == ["The Trial"]
    sent = fake.calls[0]
    assert sent["model"] == ask.MODEL
    assert sent["tools"][0]["strict"] is True
    assert sent["fallbacks"] == "default"


def test_invalid_model_arguments_are_rejected(make_client):
    fake = FakeClaude([tool_use(title_contains=None, author_contains=None, is_sold=None, limit=5000)])
    resp = make_client(fake).get("/books/ask?q=everything")
    assert resp.status_code == 422
    assert "invalid filters" in resp.json["error"]


def test_off_topic_question_returns_model_reply(make_client):
    fake = FakeClaude([text("That question is not about the bookstore inventory.")], stop_reason="end_turn")
    resp = make_client(fake).get("/books/ask?q=what is the weather")
    assert resp.status_code == 422
    assert "not about the bookstore" in resp.json["error"]


def test_refusal_is_reported(make_client):
    resp = make_client(FakeClaude([], stop_reason="refusal")).get("/books/ask?q=hmm")
    assert resp.status_code == 422


def test_no_credentials_returns_503(make_client):
    class NoCreds(FakeClaude):
        def _create(self, **kwargs):
            raise TypeError('"Could not resolve authentication method. Expected one of api_key, ..."')
    resp = make_client(NoCreds([])).get("/books/ask?q=kafka")
    assert resp.status_code == 503
    assert "not configured" in resp.json["error"]


def test_missing_question(make_client):
    assert make_client(FakeClaude([])).get("/books/ask").status_code == 400
