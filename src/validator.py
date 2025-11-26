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

def normalize_course_structure(doc: dict) -> dict:
    """
    LLM の出力構造のゆがみを補正する。

    例:
    - participants が course["period"] の中に入ってしまっている場合、
      course["participants"] に移動させる。
    """
    courses = doc.get("courses", [])
    for course in courses:
        period = course.get("period") or {}
        # period配下に participants がいて、course直下にない場合は上に移動
        if "participants" in period and "participants" not in course:
            course["participants"] = period.pop("participants")

    return doc

def clean_optionalrq_status(doc: dict) -> dict:
    """
    optionalRQ の各要素から、スキーマに存在しない status フィールドを削除する。

    LLM は {"name": "...", "status": "RQ", "date": "...", "pax": 1} などを
    返してくることがあるが、EXTRACT_SCHEMA.json では status を定義していない
    ため、ここで取り除く。
    """
    courses = doc.get("courses", [])
    for course in courses:
        participants = course.get("participants", []) or []
        for p in participants:
            opt_list = p.get("optionalRQ", []) or []
            for op in opt_list:
                if isinstance(op, dict) and "status" in op:
                    op.pop("status", None)
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

    # 構造補正 → OP status 削除 → 数値フィールド補正
    doc = normalize_course_structure(doc)
    doc = clean_optionalrq_status(doc)
    doc = coerce_numeric_fields(doc)

    _validator.validate(doc)


def is_schema_valid(doc: dict) -> Tuple[bool, Optional[str]]:
    if not _schema or _validator is None:
        return True, None

    doc = normalize_course_structure(doc)
    doc = clean_optionalrq_status(doc)
    doc = coerce_numeric_fields(doc)

    try:
        _validator.validate(doc)
        return True, None
    except ValidationError as e:
        return False, str(e)
