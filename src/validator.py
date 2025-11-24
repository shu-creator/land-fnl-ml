# src/validator.py
# 目的: EXTRACT_SCHEMA.json による機械的なスキーマ検証 (Step3a)

import json
import pathlib
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

# このファイル (validator.py) から見たプロジェクトルートを特定
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "pack" / "EXTRACT_SCHEMA.json"

# スキーマは起動時に1回だけ読み込む
try:
    _schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    # pack/EXTRACT_SCHEMA.json がまだ未配置でも import できるようにしておく
    _schema = {}
    _validator = None  # type: ignore
else:
    _validator = Draft202012Validator(_schema)


def validate_schema(doc: dict) -> None:
    """
    抽出結果 JSON が EXTRACT_SCHEMA.json に適合しているか検証する。

    - 違反していれば jsonschema.ValidationError を投げる
    - pack/EXTRACT_SCHEMA.json が空 or 未定義の場合は、何もしない（スキップ）
    """
    if not _schema or _validator is None:
        # まだスキーマが未定義の段階ではスキップ
        return

    _validator.validate(doc)


def is_schema_valid(doc: dict) -> tuple[bool, str | None]:
    """
    スキーマに適合するかブール値で返すユーティリティ。

    戻り値:
        (True, None)  : スキーマOK
        (False, msg)  : エラーあり（msg に簡易メッセージ）
    """
    if not _schema or _validator is None:
        # スキーマ未設定なら常に True 扱い
        return True, None

    try:
        _validator.validate(doc)
        return True, None
    except ValidationError as e:
        return False, str(e)


if __name__ == "__main__":
    # 簡易テスト: pack/EXTRACT_SCHEMA.json があれば検証
    sample = {"courses": []}
    ok, msg = is_schema_valid(sample)
    print("valid:", ok)
    if msg:
        print("error:", msg)
