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
あなたは FNL抽出結果の品質レビュアーです。

目的:
抽出結果JSONが「海外催行に必要な情報のみ」になっているかを確認し、
必要に応じて ERR / WARN を返します。
schema 構造はすでに Python で検証済みのため変更不要です。

[入力1: 正規化済み原文（行番号付き）]
{lines_text}

[入力2: 抽出結果 JSON]
{json_text}

[レビューのレイヤー]

レイヤー0（致命的NG・必ずERR）
- 禁則ワード（座席・並び席・金銭・返金・保険・旅券・JR・社内進行）が JSON に含まれていないか。
- 国内移動（JR等）の情報が scheduleImpact 等に残っていないか。
- optionalRQ / roomingRQ / airline / gearSizes に schema未定義の追加フィールドが紛れ込んでいないか。

レイヤー1（現地運用の主要項目）
- celebration:
  原文にハネムーン、結婚記念日、入籍予定があれば反映されているか。
- medical / meal_allergy / airline.meal:
  原文にアレルギー・持病・乗り物酔い等がある場合、対応フィールドに入っているか。
  単なる持参薬案内だけが medical に入っていないか。
- optionalRQ:
  原文に OP の RQ があるのに optionalRQ に無い／HKを採用している等は ERR。
- roomingRQ:
  RQ 以外（履歴・確定）が混ざっていないか。
- airline:
  飲食／搭乗支援／持込配慮／到着影響のみが入っているか。
  座席指定が紛れ込んでいないか。
- scheduleImpact:
  現地集合などに関する重要情報は入っているか。
  ※国内移動（JR等）はエラー。
- 「不明」の使い方:
  不明は date のみ許容。それ以外にあれば ERR。

レイヤー2（品質向上のためのWARN）
- joinType（合流／送迎／個人便）が必要なのに空。
- gearSizes が必要なのに空。
- otherGroup が必要なのに空。
- 明らかな重複がある。

[指示]

- 上記レイヤー以外の観点で、新しい ERR/WARN を追加してはいけません。
- 判断が迷う場合は WARN 側に倒してください。
- 出力は次の JSON 形式のみ:

{{
  "ok": true/false,
  "errors": [
    {{"code":"ERR_xxx", "message":"...", "suggestedPatch": {{...}}}}
  ],
  "warnings": [
    {{"code":"WARN_xxx", "message":"...", "suggestedPatch": {{...}}}}
  ]
}}
""".strip()


def validate_semantic_with_llm(
    block: Dict[str, Any],
    extracted_json: Dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """
    LLM に意味検証を依頼し、レビュー結果を返す。
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
