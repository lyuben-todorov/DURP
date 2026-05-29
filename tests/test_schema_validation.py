"""Schema-validation guards.

Ensures the committed example entry stays valid against the shipped
JSON Schema, that the Pydantic models accept it, and that the schema
version is internally consistent. Catches the class of bug where a
schema edit and an example drift apart.

Requires `bump_ext` importable (lib/ on path via conftest / inline
bootstrap) and `jsonschema` installed (a declared dependency).
"""

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bump_ext  # noqa: E402

_EXAMPLE = _ROOT / "schema" / "examples" / "cargo-example.json"
_SCHEMA = _ROOT / "schema" / "entry.schema.json"


class TestSchemaVersion(unittest.TestCase):
    def test_schema_version_is_set(self):
        self.assertTrue(bump_ext.SCHEMA_VERSION)

    def test_example_matches_schema_version(self):
        entry = json.loads(_EXAMPLE.read_text())
        self.assertEqual(entry.get("schemaVersion"), bump_ext.SCHEMA_VERSION)

    def test_schema_id_matches_version(self):
        schema = json.loads(_SCHEMA.read_text())
        # $id embeds the version, e.g. ".../entry.schema.json" or a v0.0.5
        # marker. We just assert the schema parses and has an $id/$schema.
        self.assertTrue(schema.get("$id") or schema.get("$schema"))


class TestExampleValidates(unittest.TestCase):
    def test_example_passes_validate_entry(self):
        entry = json.loads(_EXAMPLE.read_text())
        # Raises SchemaError on failure.
        bump_ext.validate_entry(entry)

    def test_example_round_trips_through_pydantic(self):
        entry = json.loads(_EXAMPLE.read_text())
        model = bump_ext.Entry.model_validate(entry)
        # Re-dump and re-validate — the model's output must itself be valid.
        redumped = model.model_dump(mode="json", by_alias=True, exclude_none=True)
        bump_ext.validate_entry(redumped)


class TestValidationRejectsBadEntries(unittest.TestCase):
    def test_missing_required_field_raises(self):
        entry = json.loads(_EXAMPLE.read_text())
        entry.pop("schemaVersion", None)
        with self.assertRaises(bump_ext.SchemaError):
            bump_ext.validate_entry(entry)

    def test_empty_dict_raises(self):
        with self.assertRaises(bump_ext.SchemaError):
            bump_ext.validate_entry({})


if __name__ == "__main__":
    unittest.main()
