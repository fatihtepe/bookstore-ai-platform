"""MCP tools exercised end to end against the real Flask app (in-process, no network)."""
import asyncio

import httpx
import pytest

from mcp_server import server


@pytest.fixture(autouse=True)
def wire_mcp_to_app(app):
    server.set_client(httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://test"))
    yield
    server.set_client(None)


def test_registered_tools_have_no_delete():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert names == {"search_books", "get_book", "add_book", "update_book", "mark_sold"}


def test_search_and_mark_sold():
    trial = server.search_books(author_contains="kafka")["books"][0]
    assert trial["is_sold"] is False
    assert server.mark_sold(trial["book_id"])["book"]["is_sold"] is True


def test_add_and_update():
    book = server.add_book("Dune", "Frank Herbert")["book"]
    assert server.update_book(book["book_id"], title="Dune Messiah")["book"]["title"] == "Dune Messiah"


def test_validation_blocks_bad_input():
    with pytest.raises(ValueError):
        server.add_book("x" * 101)
    with pytest.raises(ValueError):
        server.search_books(limit=0)
    with pytest.raises(ValueError, match="404"):
        server.get_book(999)


def test_calls_are_audited(caplog):
    with caplog.at_level("INFO", logger="bookstore.mcp.audit"):
        server.get_book(1)
    assert '"tool": "get_book"' in caplog.text
