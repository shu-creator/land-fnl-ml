# src/validator.py
# 目的: EXTRACT_SCHEMA.json によるスキーマ検証 (Python 3.9 対応版)

import json
import pathlib
from typing import Any, Optional, Tuple

from jsonschema import Draft202012Validator, ValidationError

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "pack" / "EXTRACT_SCHEMA.json"

try:
    _schema: dict = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    _schema = {}
    _validator = None
else:
    _validator = Draft202012Validator(_schema)


def validate_schema(doc: dict) -> None:
    if not _schema or _validator is None:
        return
    _validator.validate(doc)


def is_schema_valid(doc: dict) -> Tuple[bool, Optional[str]]:
    if not _schema or _validator is None:
        return True, None
    try:
        _validator.validate(doc)
        return True, None
    except ValidationError as e:
        return False, str(e)
