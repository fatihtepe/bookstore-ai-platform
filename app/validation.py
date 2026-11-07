"""Input validation shared by the REST API, the MCP server and the AI endpoint."""

MAX_LEN = 100


class ValidationError(ValueError):
    pass


def text(value, field: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValidationError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{field} is required")
    if len(value) > MAX_LEN:
        raise ValidationError(f"{field} must be at most {MAX_LEN} characters")
    return value


def flag(value, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be true or false")
    return value


def limit(value, default: int = 20, maximum: int = 100) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ValidationError(f"limit must be an integer between 1 and {maximum}")
    return value


def search_filters(data: dict) -> dict:
    """Validate the search filters used by GET /books, the MCP search tool and /books/ask."""
    unknown = set(data) - {"title_contains", "author_contains", "is_sold", "limit"}
    if unknown:
        raise ValidationError(f"unknown filter(s): {sorted(unknown)}")
    return {
        "title_contains": text(data.get("title_contains"), "title_contains"),
        "author_contains": text(data.get("author_contains"), "author_contains"),
        "is_sold": flag(data.get("is_sold"), "is_sold"),
        "limit": limit(data.get("limit")),
    }
