# src/validator.py
# 目的: EXTRACT_SCHEMA.json によるスキーマ検証 (Python 3.9 対応版)

import json
import pathlib
from typing import Any, Optional, Tuple

def coerce_numeric_fields(doc: dict) -> dict:
    """
    LLM が文字列で返しがちな数値フィールドを、可能なら int に変換する。
    - participants[].no
    - participants[].optionalRQ[].pax
    """
    courses = doc.get("courses", [])
    for course in courses:
        participants = course.get("participants", [])
        for p in participants:
            # no: "01" → 1
            no = p.get("no")
            if isinstance(no, str) and no.isdigit():
                p["no"] = int(no)

            # optionalRQ[].pax: "2" → 2
            for op in p.get("optionalRQ", []) or []:
                pax = op.get("pax")
                if isinstance(pax, str) and pax.isdigit():
                    op["pax"] = int(pax)

    return doc

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

    doc = coerce_numeric_fields(doc)
    
    _validator.validate(doc)


def is_schema_valid(doc: dict) -> Tuple[bool, Optional[str]]:
    if not _schema or _validator is None:
        return True, None

    doc = coerce_numeric_fields(doc)
    
    try:
        _validator.validate(doc)
        return True, None
    except ValidationError as e:
        return False, str(e)
