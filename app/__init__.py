"""Bookstore API: Flask app factory, REST routes, health and AI search."""
import logging
import os

import anthropic
from flask import Flask, jsonify, request
from sqlalchemy import text as sql_text

from . import ask as ask_module
from . import validation
from .db import BookRepo, init_db, make_engine

log = logging.getLogger("bookstore")


def create_app(database_url: str | None = None, ai_client=None) -> Flask:
    app = Flask(__name__)
    engine = make_engine(database_url or os.environ.get("DATABASE_URL", "sqlite:///bookstore.db"))
    init_db(engine, seed=os.environ.get("SEED_DATA", "true").lower() == "true")
    repo = BookRepo(engine)
    app.extensions["repo"] = repo

    @app.errorhandler(validation.ValidationError)
    def bad_input(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def not_allowed(_):
        return jsonify(error="Method not allowed"), 405

    @app.get("/")
    def home():
        return jsonify(service="bookstore-api", docs="/books, /books/<id>, /books/ask?q=, /healthz, /readyz")

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/readyz")
    def readyz():
        try:
            with engine.connect() as conn:
                conn.execute(sql_text("SELECT 1"))
        except Exception:  # noqa: BLE001 - any DB failure means not ready
            log.exception("readiness check failed")
            return jsonify(status="db-unavailable"), 503
        return jsonify(status="ready")

    @app.get("/books")
    def list_books():
        args = request.args
        is_sold = args.get("is_sold")
        filters = validation.search_filters({
            k: v for k, v in {
                "title_contains": args.get("title"),
                "author_contains": args.get("author"),
                "is_sold": None if is_sold is None else is_sold.lower() == "true",
                "limit": int(args["limit"]) if args.get("limit", "").isdigit() else None,
            }.items() if v is not None
        })
        return jsonify(books=repo.list(**filters))

    @app.get("/books/<int:book_id>")
    def get_book(book_id):
        book = repo.get(book_id)
        return (jsonify(book=book), 200) if book else not_found(None)

    @app.post("/books")
    def add_book():
        data = request.get_json(silent=True) or {}
        title = validation.text(data.get("title"), "title", required=True)
        author = validation.text(data.get("author"), "author") or ""
        return jsonify(book=repo.create(title, author)), 201

    @app.put("/books/<int:book_id>")
    def update_book(book_id):
        if repo.get(book_id) is None:
            return not_found(None)
        data = request.get_json(silent=True)
        if not data:
            raise validation.ValidationError("JSON body required")
        fields = {}
        if "title" in data:
            fields["title"] = validation.text(data["title"], "title", required=True)
        if "author" in data:
            fields["author"] = validation.text(data["author"], "author") or ""
        if "is_sold" in data:
            fields["is_sold"] = validation.flag(data["is_sold"], "is_sold")
        return jsonify(book=repo.update(book_id, **fields))

    @app.delete("/books/<int:book_id>")
    def delete_book(book_id):
        return jsonify(deleted=True) if repo.delete(book_id) else not_found(None)

    @app.get("/books/ask")
    def ask_books():
        try:
            filters = ask_module.question_to_filters(request.args.get("q"), client=ai_client)
        except ask_module.AskError as e:
            return jsonify(error=str(e)), e.status
        except anthropic.AuthenticationError:
            return jsonify(error="AI search is not configured (no Anthropic credentials)"), 503
        except anthropic.RateLimitError:
            return jsonify(error="AI search is busy, try again shortly"), 429
        except anthropic.APIConnectionError:
            return jsonify(error="AI search is unreachable"), 503
        except anthropic.APIStatusError:
            log.exception("Claude API error")
            return jsonify(error="AI search failed"), 502
        log.info("ask: q=%r filters=%s", request.args.get("q"), filters)
        return jsonify(filters=filters, books=repo.list(**filters))

    return app
