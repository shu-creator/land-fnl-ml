# src/validator.py
# 目的: EXTRACT_SCHEMA.json によるスキーマ検証 (Python 3.9 対応版)

import json
import pathlib
from typing import Any, Optional, Tuple

from jsonschema import Draft202012Validator, ValidationError

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "pack" / "EXTRACT_SCHEMA.json"


def coerce_numeric_fields(doc: dict) -> dict:
    """
    LLM が文字列で返しがちな数値フィールドを、可能なら int に変換する。
    - participants[].no
    - participants[].optionalRQ[].pax
    """
    courses = doc.get("courses", [])
    for course in courses:
        participants = course.get("participants", []) or []
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

    - participants が course["period"] の中に入ってしまっている場合、
      course["participants"] に移動させる。
    - course 配下に periodFrom / periodTo / periodStart / periodEnd /
      startDate / endDate がある場合、
      period: {"start": ..., "end": ...} に正規化する。
    """
    courses = doc.get("courses", [])
    for course in courses:
        # 1) period 配下に participants がいるパターンを補正（念のため）
        period = course.get("period")
        if isinstance(period, dict) and "participants" in period and "participants" not in course:
            course["participants"] = period.pop("participants")

        # 2) period の別名をまとめて拾う
        # 優先順位: 既に period がある場合はそれを優先し、足りない方だけ補完する
        period_obj = course.get("period") or {}
        start_val = period_obj.get("start")
        end_val = period_obj.get("end")

        # いろいろな別名から start / end を拾う
        alias_pairs = [
            ("periodFrom", "periodTo"),
            ("periodStart", "periodEnd"),
            ("startDate", "endDate"),
        ]

        for start_key, end_key in alias_pairs:
            s = course.get(start_key)
            e = course.get(end_key)
            if s and not start_val:
                start_val = s
            if e and not end_val:
                end_val = e
            # 使った別名は消しておく
            if start_key in course:
                course.pop(start_key, None)
            if end_key in course:
                course.pop(end_key, None)

        # 何かしら start / end が取れていれば period をセット
        if start_val or end_val:
            course["period"] = {
                "start": start_val or "",
                "end": end_val or "",
            }

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


def normalize_text_fields(doc: dict) -> dict:
    ...
    courses = doc.get("courses", [])
    for course in courses:
        participants = course.get("participants", []) or []
        for p in participants:
            # participant直下の文字列フィールド
            if "meal_allergy" in p:
                p["meal_allergy"] = to_str(p.get("meal_allergy"))
            if "medical" in p:
                p["medical"] = to_str(p.get("medical"))
            if "scheduleImpact" in p:
                p["scheduleImpact"] = to_str(p.get("scheduleImpact"))

            # airline オブジェクト
            al = p.get("airline")
            if isinstance(al, dict):
                # LLM 側のキーを schema のキーにマッピング
                # assistance / support → assist
                # baggage / luggage → carryOn
                # impact → arrivalImpact
                key_map = {
                    "assistance": "assist",
                    "support": "assist",
                    "baggage": "carryOn",
                    "luggage": "carryOn",
                    "impact": "arrivalImpact",
                }
                for src, dst in key_map.items():
                    if src in al and dst not in al:
                        al[dst] = al.pop(src)
                    else:
                        # src があって dst もある場合や、不要な場合は消す
                        al.pop(src, None)

                # allowed 以外のキーは削除しつつ、値を string に統一
                allowed = {"meal", "assist", "carryOn", "arrivalImpact"}
                for key in list(al.keys()):
                    if key in allowed:
                        al[key] = to_str(al.get(key))
                    else:
                        al.pop(key, None)

    return doc

# スキーマの読み込みとバリデータ初期化
try:
    _schema: dict = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    _schema = {}
    _validator = None
else:
    _validator = Draft202012Validator(_schema)


def validate_schema(doc: dict) -> None:
    """
    EXTRACT_SCHEMA.json による機械的な検証を行う。
    スキーマが未ロード（_schema が空）の場合は何もしない。
    """
    if not _schema or _validator is None:
        return

    # 構造補正 → OP status 削除 → 文字列フィールド正規化 → 数値フィールド補正
    doc = normalize_course_structure(doc)
    doc = clean_optionalrq_status(doc)
    doc = normalize_text_fields(doc)
    doc = coerce_numeric_fields(doc)

    _validator.validate(doc)


def is_schema_valid(doc: dict) -> Tuple[bool, Optional[str]]:
    """
    スキーマに適合するかをチェックし、(bool, エラーメッセージ) を返す。
    スキーマ未設定時は (True, None) を返す。
    """
    if not _schema or _validator is None:
        return True, None

    doc = normalize_course_structure(doc)
    doc = clean_optionalrq_status(doc)
    doc = normalize_text_fields(doc)
    doc = coerce_numeric_fields(doc)

    try:
        _validator.validate(doc)
        return True, None
    except ValidationError as e:
        return False, str(e)
