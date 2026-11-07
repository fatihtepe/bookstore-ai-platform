from app import create_app


def test_health_and_ready(client):
    assert client.get("/healthz").json == {"status": "ok"}
    assert client.get("/readyz").json == {"status": "ready"}


def test_seed_and_list(client):
    books = client.get("/books").json["books"]
    assert [b["title"] for b in books] == ["Where the Crawdads Sing", "The Vanishing Half", "The Trial"]


def test_filters(client):
    assert [b["author"] for b in client.get("/books?author=kafka").json["books"]] == ["Franz Kafka"]
    assert all(not b["is_sold"] for b in client.get("/books?is_sold=false").json["books"])
    assert len(client.get("/books?limit=1").json["books"]) == 1


def test_crud_cycle(client):
    created = client.post("/books", json={"title": "Dune", "author": "Frank Herbert"})
    assert created.status_code == 201
    book_id = created.json["book"]["book_id"]
    assert client.get(f"/books/{book_id}").json["book"]["title"] == "Dune"
    updated = client.put(f"/books/{book_id}", json={"is_sold": True}).json["book"]
    assert updated["is_sold"] is True and updated["title"] == "Dune"
    assert client.delete(f"/books/{book_id}").json == {"deleted": True}
    assert client.get(f"/books/{book_id}").status_code == 404


def test_validation_errors(client):
    assert client.post("/books", json={}).status_code == 400
    assert client.post("/books", json={"title": "x" * 101}).status_code == 400
    assert client.put("/books/1", json={"is_sold": "yes"}).status_code == 400
    assert client.put("/books/999", json={"title": "x"}).status_code == 404


def test_sql_injection_is_stored_as_plain_text(client):
    evil = "x'); DROP TABLE books; --"
    book = client.post("/books", json={"title": evil, "author": "' OR '1'='1"}).json["book"]
    assert book["title"] == evil
    assert len(client.get("/books").json["books"]) == 4  # table still there, nothing leaked


def test_restart_keeps_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'persist.db'}"
    create_app(url).test_client().post("/books", json={"title": "Survives restarts"})
    titles = [b["title"] for b in create_app(url).test_client().get("/books").json["books"]]
    assert "Survives restarts" in titles and len(titles) == 4
