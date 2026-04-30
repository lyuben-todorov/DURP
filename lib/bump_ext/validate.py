"""JSON Schema validation for entries.

Used by EntryWriter and by CI to validate on-disk entries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class SchemaError(Exception):
    pass


_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "entry.schema.json"
_validator: Draft202012Validator | None = None


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        with _SCHEMA_PATH.open() as f:
            schema = json.load(f)
        _validator = Draft202012Validator(schema)
    return _validator


def validate_entry(entry: dict[str, Any]) -> None:
    errors = sorted(_get_validator().iter_errors(entry), key=lambda e: e.path)
    if errors:
        msgs = [f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors]
        raise SchemaError("Entry failed schema validation:\n  " + "\n  ".join(msgs))
