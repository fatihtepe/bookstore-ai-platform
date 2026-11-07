"""Natural-language search: Claude turns a question into ONE structured
search_books call. The model never writes SQL; its arguments are validated
by the same rules as the REST API before any query runs.
"""
import os

import anthropic

from . import validation

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")

SEARCH_TOOL = {
    "name": "search_books",
    "description": (
        "Search the bookstore inventory. Use only the filters the user's question implies; "
        "omit a filter rather than guessing a value."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "title_contains": {"type": ["string", "null"], "description": "Case-insensitive substring of the title"},
            "author_contains": {"type": ["string", "null"], "description": "Case-insensitive substring of the author"},
            "is_sold": {"type": ["boolean", "null"], "description": "true = sold, false = available"},
            "limit": {"type": ["integer", "null"], "description": "Max results, 1-100"},
        },
        "required": ["title_contains", "author_contains", "is_sold", "limit"],
        "additionalProperties": False,
    },
}

SYSTEM = (
    "You translate bookstore inventory questions into a single search_books call. "
    "Always answer by calling search_books. If the question is not about finding books "
    "in the inventory, do not call the tool and reply with one sentence saying so."
)


class AskError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def question_to_filters(question: str, client=None) -> dict:
    """Return validated search filters for a natural-language question."""
    question = validation.text(question, "q", required=True)
    client = client or anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM,
        tools=[SEARCH_TOOL],
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": question}],
    )
    if response.stop_reason == "refusal":
        raise AskError("The model declined this question.")
    call = next((b for b in response.content if b.type == "tool_use" and b.name == "search_books"), None)
    if call is None:
        reply = next((b.text for b in response.content if b.type == "text"), "")
        raise AskError(reply or "The question could not be turned into a book search.")
    args = {k: v for k, v in dict(call.input).items() if v is not None}
    try:
        return validation.search_filters(args)
    except validation.ValidationError as e:
        raise AskError(f"Model produced invalid filters: {e}") from e
