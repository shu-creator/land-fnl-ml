# src/llm_validator.py
# 目的: Step3b 意味検証を LLM に実施させる
# - スキーマは validator.py で形式検証済み
# - ここでは「内容／意味」の妥当性を LLM に再査読させる
#
# 出力:
# {
#   "ok": true/false,
#   "errors": [
#       {"code": "...", "message": "...", "suggestedPatch": {...}}
#   ],
#   "warnings": [...]
# }

from __future__ import annotations

from typing import Dict, Any
import json
from openai import OpenAI  # type: ignore


# モデル名は必要に応じて変更可
DEFAULT_MODEL = "gpt-5-mini"

client = OpenAI()


def build_validation_prompt(block: Dict[str, Any], extracted_json: Dict[str, Any]) -> str:
    """
    原文（行番号付き） + 抽出結果 JSON を LLM に渡し、
    内容が妥当かどうかレビューさせるためのプロンプトを組み立てる。
    """
    # 原文（行番号付き）
    lines_text = "\n".join(
        f"{i+1}: {ln}" for i, ln in enumerate(block.get("lines", []))
    )

    # JSON を pretty-print
    json_text = json.dumps(extracted_json, ensure_ascii=False, indent=2)

    return f"""
あなたは旅行会社の FNL 抽出結果の品質レビュアーです。

[入力1: 正規化済み原文（行番号付き）]
{lines_text}

[入力2: 抽出結果 JSON]
{json_text}

[レビュー観点]
- JSONは既に基本スキーマに適合しています。構造そのものを壊す必要はありません。
- 次の点を重点的に確認してください:
  1. 座席・並び席・保険・返金・金銭・旅券・JR・社内進行の情報が JSON に紛れ込んでいないか。
  2. 原文にハネムーン/入籍/記念日などの表現がある場合、celebration に反映されているか。
  3. 医療・アレルギー情報が、medical または meal_allergy に正しく割り当てられているか。
  4. 明らかに同じ内容の重複エントリがないか。

- 上記4点以外の観点については、新たなエラー・警告コードを追加しないでください。
- 特に、敬称（例: "MR.", "MS."）が nameEN に含まれていても問題ありません。その点については警告やエラーを出さないでください。

[出力形式]
以下の JSON オブジェクトのみ出力してください。

{{
  "ok": true or false,
  "errors": [
    {{
      "code": "ERR_...",
      "message": "人間が読んで理解できる説明",
      "suggestedPatch": {{ "修正すべき概要" }}
    }}
  ],
  "warnings": [
    {{
      "code": "WARN_...",
      "message": "軽微な注意点",
      "suggestedPatch": {{ "必要なら簡易コメント" }}
    }}
  ]
}}
""".strip()


def validate_semantic_with_llm(
    block: Dict[str, Any],
    extracted_json: Dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    LLM に意味検証を依頼し、レビュー結果を JSON として返す。
    """
    prompt = build_validation_prompt(block, extracted_json)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "あなたは抽出結果の品質レビュアーです。"
                    "必ず指定された JSON 形式で回答してください。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM semantic validation returned empty content")

    result = json.loads(content)
    return result


if __name__ == "__main__":
    # 動作確認用（APIキーが必要）
    block = {
        "courseNo": "ABC123",
        "period": {"start": "2025-01-01", "end": "2025-01-05"},
        "lines": [
            "コースNo: ABC123",
            "2025-01-01〜2025-01-05",
            "特別依頼: 9月に入籍予定のため、ハネムーンです。",
        ],
    }
    extracted = {
        "courses": [
            {
                "courseNo": "ABC123",
                "period": {"start": "2025-01-01", "end": "2025-01-05"},
                "participants": [],
            }
        ]
    }
    try:
        review = validate_semantic_with_llm(block, extracted)
        print(json.dumps(review, ensure_ascii=False, indent=2))
    except Exception as e:
        print("error:", repr(e))
