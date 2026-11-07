# bookstore-ai-platform

A Flask + MySQL bookstore API, rebuilt from a 2021 bootcamp project into a secured, containerized service on AWS, with an **MCP server** and **natural-language search** so AI agents can work with it safely.

Original project: [my-projects/ProjectO-003](https://github.com/fatihtepe/my-projects/tree/main/ProjectO-003-Dockerization-of-Bookstore-Web-API-Python-Flask-with-MySQL)

## What changed from the original

| Original (2021) | Now |
|---|---|
| SQL built with f-strings → **SQL injection** | SQLAlchemy Core with bound parameters; a test stores `'); DROP TABLE books; --` as plain text |
| Passwords hardcoded in code and compose | `.env` locally; generated passwords in **SSM Parameter Store** (SecureString) on AWS |
| Table dropped on every start | `create_all` + seed only when empty, run once by `python -m app.migrate` before the web workers start (avoids a CREATE TABLE race); a test proves data survives restarts |
| SSH open to `0.0.0.0/0`, hardcoded AMI, provider 3.60 | **No SSH** (SSM Session Manager), latest AL2023 via SSM, IMDSv2, encrypted gp3, HTTPS-only egress, AWS provider 5.x |
| Unpinned `python:alpine`, root user, broken `CMD` | Pinned multi-stage image, non-root user, gunicorn, `HEALTHCHECK` |
| MySQL 5.7, no health checks | MySQL 8.4, `/healthz` + `/readyz`, compose waits for a healthy DB |
| No tests, no CI | 18 pytest tests; CI runs ruff (incl. bandit rules), pytest, `terraform validate`, **Checkov**, **Trivy**, a container smoke test, then pushes to GHCR |

## AI features

### 1. MCP server (`mcp_server/server.py`)
Lets Claude Desktop, Claude Code or any MCP client manage the inventory through the REST API.

- Tools: `search_books`, `get_book`, `add_book`, `update_book`, `mark_sold`
- **Guardrails:** there is deliberately no delete tool, every call goes through the same validation as the API, and every call is written to an audit log.

Claude Desktop config (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "bookstore": {
      "command": "/path/to/bookstore-ai-platform/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/bookstore-ai-platform",
      "env": { "BOOKSTORE_API_URL": "http://localhost:8080" }
    }
  }
}
```
Then ask: *"Which Kafka books are still available? Mark The Trial as sold."*

### 2. Natural-language search (`GET /books/ask?q=...`)
```
GET /books/ask?q=unsold books by Kafka
→ {"filters": {"author_contains": "Kafka", "is_sold": false, ...}, "books": [...]}
```
Claude (`claude-opus-5-5`, low effort) turns the question into **one structured `search_books` call** (strict JSON schema). The model never writes SQL: its arguments are validated with the same rules as the API, and invalid or off-topic requests return 422. Optional: needs `ANTHROPIC_API_KEY`; without it the endpoint returns 503 and everything else works. Server-side refusal fallback is enabled (`fallbacks: "default"`).

## Run it

```sh
# Local, no Docker (SQLite)
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/flask --app "app:create_app()" run -p 8080     # dev server
# or, like production (2 workers):
DATABASE_URL=sqlite:///local.db .venv/bin/python -m app.migrate
AUTO_INIT_DB=false DATABASE_URL=sqlite:///local.db .venv/bin/gunicorn -b 127.0.0.1:8080 -w 2 "app:create_app()"

# Full stack with MySQL
cp .env.example .env   # set passwords
docker compose up --build
curl localhost:8080/books
curl -X POST localhost:8080/books -H 'Content-Type: application/json' -d '{"title":"Dune","author":"Frank Herbert"}'
```

## Deploy to AWS

```sh
cd infra/terraform
terraform init
terraform apply -var-file=example.tfvars     # api_image = the GHCR image CI pushes
# outputs: api_url, ssm_session_command (shell access without SSH)
```
Optional AI key: `aws ssm put-parameter --name /bookstore/anthropic_api_key --type SecureString --overwrite --value sk-...`

## Layout

```
app/            Flask app factory, data layer, validation, AI search
mcp_server/     MCP server (agent tools + audit log)
tests/          API, SQL injection, persistence, AI search (fake client), MCP tools
infra/terraform EC2 + SSM + IAM + security group, Checkov config
.github/        CI: lint → tests → terraform/checkov → build → trivy → smoke test → GHCR
```

## Honest limits / next steps

- Single EC2 instance with MySQL in a container: fine for dev, not HA. Next step: ECS Fargate + RDS.
- Terraform random passwords live in state; use an encrypted remote backend (S3 block is ready in `versions.tf`).
- The MCP server has no auth of its own; run it locally (stdio) or behind an authenticated gateway.
- AI search tests use a fake Claude client; a live check needs an API key. Without one, `/books/ask` returns 503 and the rest of the API works.
