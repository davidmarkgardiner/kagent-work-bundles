"""Fail-closed result shaping for data returned to an MCP client."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import json
import os
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ResultBudget:
    """Maximum result size the adapter may place in model context."""

    max_rows: int
    max_response_bytes: int
    max_cell_chars: int


def _bounded_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def budget_from_env() -> ResultBudget:
    """Load tunable limits while retaining non-bypassable hard ceilings."""
    return ResultBudget(
        max_rows=_bounded_env("MCP_MAX_ROWS", 50, 1, 100),
        max_response_bytes=_bounded_env(
            "MCP_MAX_RESPONSE_BYTES", 32_768, 4_096, 65_536
        ),
        max_cell_chars=_bounded_env("MCP_MAX_CELL_CHARS", 512, 64, 2_048),
    )


def _normalise_cell(value: object, max_chars: int) -> tuple[object, bool]:
    if value is None or isinstance(value, (bool, int, float)):
        return value, False
    if isinstance(value, bytes):
        return "<binary omitted>", True

    if isinstance(value, str):
        rendered = value
    else:
        try:
            rendered = json.dumps(value, default=str, separators=(",", ":"))
        except (TypeError, ValueError):
            rendered = str(value)

    if len(rendered) <= max_chars:
        return value if isinstance(value, str) else rendered, False
    return f"{rendered[:max_chars]}…", True


def bounded_result(
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
    budget: ResultBudget,
) -> dict[str, object]:
    """Return a JSON-safe envelope that never exceeds the configured budget.

    Callers should supply at most ``max_rows + 1`` rows. The extra row proves
    truncation and is never returned.
    """
    raw_rows = list(islice(rows, budget.max_rows + 1))
    row_limit_hit = len(raw_rows) > budget.max_rows
    cell_limit_hit = False
    shaped_rows: list[dict[str, object]] = []

    for raw_row in raw_rows[: budget.max_rows]:
        shaped_row: dict[str, object] = {}
        for column, value in zip(columns, raw_row, strict=True):
            shaped, truncated = _normalise_cell(value, budget.max_cell_chars)
            shaped_row[column] = shaped
            cell_limit_hit = cell_limit_hit or truncated
        shaped_rows.append(shaped_row)

    reasons: list[str] = []
    if row_limit_hit:
        reasons.append("row_limit")
    if cell_limit_hit:
        reasons.append("cell_limit")

    def envelope() -> dict[str, object]:
        return {
            "rows": shaped_rows,
            "returned_rows": len(shaped_rows),
            "truncated": bool(reasons),
            "truncation_reasons": reasons,
            "limits": {
                "max_rows": budget.max_rows,
                "max_response_bytes": budget.max_response_bytes,
                "max_cell_chars": budget.max_cell_chars,
            },
        }

    while len(json.dumps(envelope(), default=str).encode("utf-8")) > budget.max_response_bytes:
        if "byte_limit" not in reasons:
            reasons.append("byte_limit")
        if shaped_rows:
            shaped_rows.pop()
            continue
        raise ValueError("MCP_MAX_RESPONSE_BYTES is too small for result metadata")

    return envelope()
