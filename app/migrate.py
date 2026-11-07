"""Create the schema (and seed an empty table) once, before the web workers start.

Run:  python -m app.migrate
Doing this inside each gunicorn worker races on a fresh database (two workers
both issue CREATE TABLE), so the container runs it as a separate step.
"""
import os

from .db import init_db, make_engine


def main() -> None:
    engine = make_engine(os.environ.get("DATABASE_URL", "sqlite:///bookstore.db"))
    init_db(engine, seed=os.environ.get("SEED_DATA", "true").lower() == "true")
    engine.dispose()
    print("database ready")


if __name__ == "__main__":
    main()
