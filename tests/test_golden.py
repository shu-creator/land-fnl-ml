# tests/test_golden.py
# 目的: FNL抽出パイプラインの簡易ゴールデンテスト
# 注意: LLM 呼び出しを含むため、CI 用にはモック化が必要

import pathlib
from src.pipeline import process_text

BASE = pathlib.Path(__file__).resolve().parents[1]

def test_basic_pipeline_runs():
    """
    空に近い入力でも pipeline が例外を出さずに動くか確認するテスト。
    LLM 抽出が実行されるため、OPENAI_API_KEY が必要。
    """
    raw = """
    コースNo: TEST123
    2025-10-01〜2025-10-05
    参加者 太郎
    特別依頼: 11月に入籍予定のためハネムーン
    """

    output = process_text(raw)
    assert isinstance(output, str)
    assert "ツアー情報" in output  # 整形が動いている
