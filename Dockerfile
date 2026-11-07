# Multi-stage, pinned, non-root image (the original used unpinned python:alpine,
# ran as root and pointed CMD at a file that didn't exist).
FROM python:3.12.16-slim-trixie AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12.16-slim-trixie
LABEL org.opencontainers.image.source=https://github.com/fatihtepe/bookstore-ai-platform \
      org.opencontainers.image.description="Bookstore API with MCP server and AI search"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AUTO_INIT_DB=false
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app
COPY --from=build /install /usr/local
WORKDIR /app
COPY app/ app/
COPY mcp_server/ mcp_server/
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"
# Schema/seed once, then hand PID 1 to gunicorn
CMD ["sh", "-c", "python -m app.migrate && exec gunicorn --bind 0.0.0.0:8080 --workers 2 --access-logfile - 'app:create_app()'"]
