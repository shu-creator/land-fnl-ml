# src/llm_extractor.py
# 目的: 1コース分のブロックから LLM を使って抽出 JSON を生成する (Step2)
#
# 前提:
# - OpenAI公式Pythonライブラリ(openai>=1.0) を使用
# - 環境変数 OPENAI_API_KEY が設定されていること
# - pack/MASTER_PROMPT_v2-rev_20250915.txt にマスタープロンプトを保存しておく

from __future__ import annotations

from typing import Dict, Any
import json
import pathlib

from openai import OpenAI  # type: ignore


BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
MASTER_PROMPT_PATH = BASE_DIR / "pack" / "MASTER_PROMPT_v2-rev_20250915.txt"

# モデル名は環境に合わせて変更可能
DEFAULT_MODEL = "gpt-5.1-mini"

# OpenAI クライアント (APIキーは環境変数から読む)
client = OpenAI()


def load_master_prompt() -> str:
    """
    マスタープロンプトファイルを読み込む。

    ファイルがない場合は、簡易なデフォルト文言を返す。
    """
    if MASTER_PROMPT_PATH.exists():
        return MASTER_PROMPT_PATH.read_text(encoding="utf-8")

    # まだ準備できていない段階用の簡易プロンプト
    return (
        "あなたは旅行会社のFNL用情報抽出エンジンです。"
        "入力となる日程表テキストから、参加者ごとの重要情報だけを抽出し、"
        "EXTRACT_SCHEMA.json に従った JSON を返してください。"
    )


def build_prompt_for_course(block: Dict[str, Any]) -> str:
    """
    マスタープロンプト + コースメタ情報 + 行番号付き原文 を結合して
    1コース分の user プロンプトを組み立てる。
    """
    master = load_master_prompt()

    meta = (
        f"コースNo: {block.get('courseNo','')}\n"
        f"期間: {block.get('period',{}).get('start','')}〜"
        f"{block.get('period',{}).get('end','')}"
    )

    lines_text = "\n".join(
        f"{i + 1}: {ln}" for i, ln in enumerate(block.get("lines", []))
    )

    # 禁則ワードの明示（プロンプト側）
    ng_note = (
        "座席・並び席・保険・返金・金銭・旅券・JR・社内進行に関する情報は、"
        "JSON出力に含めないでください。必要であれば internal_notes のような"
        "フィールドにではなく、完全に無視してください。"
    )

    prompt = (
        master
        + "\n\n【このコースの基本情報】\n"
        + meta
        + "\n\n【このコースの原文（行番号付き）】\n"
        + lines_text
        + "\n\n【出力要件】\n"
        "・EXTRACT_SCHEMA.json に従った JSON オブジェクトのみを返してください。\n"
        "・トップレベルは {\"courses\": [...]} という構造にしてください。\n"
        "・このブロックは1コース分なので courses 配列には1件だけ入れてください。\n"
        "・行番号を参考にして、どの行からどのフィールドを埋めたか一貫性を保ってください。\n"
        + ng_note
    )

    return prompt


def extract_with_llm(
    block: Dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    1コース分のブロックから LLM による抽出 JSON を生成する。

    戻り値:
        EXTRACT_SCHEMA.json 準拠を期待した dict。
        (ただし実際の検証は validator.validate_schema で行う)
    """
    prompt = build_prompt_for_course(block)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "あなたは旅行会社のFNL作成を支援する抽出エンジンです。"
                    "必ず EXTRACT_SCHEMA.json に従った JSON オブジェクトのみを返してください。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    # 念のため content をJSONとしてパース
    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM 抽出結果が空です")

    data = json.loads(content)
    return data


if __name__ == "__main__":
    # 簡易動作テスト用 (APIキーがある環境でのみ)
    sample_block = {
        "courseNo": "ABC123",
        "period": {"start": "2025-09-01", "end": "2025-09-05"},
        "lines": [
            "コースNo: ABC123",
            "2025-09-01〜2025-09-05",
            "特別依頼: 9月に入籍予定です。ハネムーンなので記念日の演出をお願いします。",
        ],
    }
    try:
        res = extract_with_llm(sample_block)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    except Exception as e:
        # APIキー未設定などで落ちる場合があるので print に留める
        print("extract_with_llm error:", repr(e))
