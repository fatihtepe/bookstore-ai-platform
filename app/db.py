"""Data layer. All queries go through SQLAlchemy Core with bound parameters,
so user input is never pasted into SQL text (fixes the original SQL injection).
"""
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, create_engine, delete, insert, select, update
from sqlalchemy.engine import Engine

metadata = MetaData()

books = Table(
    "books",
    metadata,
    Column("book_id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(100), nullable=False),
    Column("author", String(100), nullable=False, default=""),
    Column("is_sold", Boolean, nullable=False, default=False),
)

SEED = [
    {"title": "Where the Crawdads Sing", "author": "Delia Owens", "is_sold": True},
    {"title": "The Vanishing Half", "author": "Brit Bennett", "is_sold": False},
    {"title": "The Trial", "author": "Franz Kafka", "is_sold": False},
]


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, future=True)


def init_db(engine: Engine, seed: bool = True) -> None:
    """Create the table if missing. Unlike the original, never drops existing data."""
    metadata.create_all(engine)
    if seed:
        with engine.begin() as conn:
            if conn.execute(select(books.c.book_id).limit(1)).first() is None:
                conn.execute(insert(books), SEED)


def _row(row) -> dict:
    return {"book_id": row.book_id, "title": row.title, "author": row.author, "is_sold": bool(row.is_sold)}


class BookRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    def list(self, title_contains: str | None = None, author_contains: str | None = None,
             is_sold: bool | None = None, limit: int = 100) -> list[dict]:
        query = select(books).order_by(books.c.book_id).limit(limit)
        if title_contains:
            query = query.where(books.c.title.ilike(f"%{title_contains}%"))
        if author_contains:
            query = query.where(books.c.author.ilike(f"%{author_contains}%"))
        if is_sold is not None:
            query = query.where(books.c.is_sold == is_sold)
        with self.engine.connect() as conn:
            return [_row(r) for r in conn.execute(query)]

    def get(self, book_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(books).where(books.c.book_id == book_id)).first()
        return _row(row) if row else None

    def create(self, title: str, author: str = "") -> dict:
        with self.engine.begin() as conn:
            result = conn.execute(insert(books).values(title=title, author=author, is_sold=False))
            book_id = result.inserted_primary_key[0]
        return self.get(book_id)

    def update(self, book_id: int, **fields) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in ("title", "author", "is_sold")}
        if allowed:
            with self.engine.begin() as conn:
                conn.execute(update(books).where(books.c.book_id == book_id).values(**allowed))
        return self.get(book_id)

    def delete(self, book_id: int) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(delete(books).where(books.c.book_id == book_id)).rowcount > 0
