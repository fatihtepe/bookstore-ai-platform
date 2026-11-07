"""MCP server: lets an AI agent (Claude Desktop, Claude Code, ...) operate the
bookstore through the REST API, with guardrails:

- Only the tools below exist. There is deliberately no delete tool.
- Every call goes through the same validation as the REST API.
- Every call is written to an audit log (stderr, so stdio transport stays clean).

Run:  BOOKSTORE_API_URL=http://localhost:8080 python -m mcp_server.server
"""
import json
import logging
import os
import sys

import httpx
from mcp.server.mcpserver import MCPServer

from app import validation

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
audit = logging.getLogger("bookstore.mcp.audit")

API_URL = os.environ.get("BOOKSTORE_API_URL", "http://localhost:8080")

mcp = MCPServer(
    name="bookstore",
    instructions="Manage the bookstore inventory. You can search, view, add and update books, "
                 "and mark books as sold. Deleting books is not available to agents.",
)

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(base_url=API_URL, timeout=10)
    return _client


def set_client(c) -> None:
    """Inject an HTTP client (tests use Flask's app via httpx WSGI transport)."""
    global _client
    _client = c


def _call(tool: str, method: str, path: str, **kwargs) -> dict:
    audit.info(json.dumps({"tool": tool, "method": method, "path": path, "body": kwargs.get("json"),
                           "params": kwargs.get("params")}))
    resp = client().request(method, path, **kwargs)
    if resp.status_code >= 400:
        detail = resp.json().get("error", resp.text) if resp.headers.get("content-type", "").startswith(
            "application/json") else resp.text
        raise ValueError(f"{resp.status_code}: {detail}")
    return resp.json()


@mcp.tool()
def search_books(title_contains: str | None = None, author_contains: str | None = None,
                 is_sold: bool | None = None, limit: int | None = None) -> dict:
    """Search books by title/author substring and sold status. Returns at most `limit` books (default 20)."""
    f = validation.search_filters({k: v for k, v in {"title_contains": title_contains,
                                                      "author_contains": author_contains,
                                                      "is_sold": is_sold, "limit": limit}.items()
                                   if v is not None})
    params = {"limit": f["limit"]}
    if f["title_contains"]:
        params["title"] = f["title_contains"]
    if f["author_contains"]:
        params["author"] = f["author_contains"]
    if f["is_sold"] is not None:
        params["is_sold"] = str(f["is_sold"]).lower()
    return _call("search_books", "GET", "/books", params=params)


@mcp.tool()
def get_book(book_id: int) -> dict:
    """Get one book by its id."""
    return _call("get_book", "GET", f"/books/{int(book_id)}")


@mcp.tool()
def add_book(title: str, author: str = "") -> dict:
    """Add a new (unsold) book to the inventory."""
    body = {"title": validation.text(title, "title", required=True),
            "author": validation.text(author, "author") or ""}
    return _call("add_book", "POST", "/books", json=body)


@mcp.tool()
def update_book(book_id: int, title: str | None = None, author: str | None = None) -> dict:
    """Correct a book's title and/or author."""
    body = {}
    if title is not None:
        body["title"] = validation.text(title, "title", required=True)
    if author is not None:
        body["author"] = validation.text(author, "author") or ""
    if not body:
        raise ValueError("Give a new title and/or author")
    return _call("update_book", "PUT", f"/books/{int(book_id)}", json=body)


@mcp.tool()
def mark_sold(book_id: int, sold: bool = True) -> dict:
    """Mark a book as sold (or back to available with sold=false)."""
    return _call("mark_sold", "PUT", f"/books/{int(book_id)}", json={"is_sold": bool(sold)})


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
