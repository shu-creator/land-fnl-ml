# src/llm_extractor.py
# 目的: 1コース分のブロックから LLM を使って抽出 JSON を生成する (Step2)
#
# 方針:
# - 抽出ロジック・禁則ワードなどの指示はすべて
#   pack/MASTER_PROMPT_v2-rev_20250915.txt に集約する。
# - このモジュールは「入力データをどう渡すか」に専念し、
#   プロンプト本文は極力 MASTER_PROMPT に任せる。

from __future__ import annotations

from typing import Dict, Any
import json
import pathlib

from openai import OpenAI  # type: ignore

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
MASTER_PROMPT_PATH = BASE_DIR / "pack" / "MASTER_PROMPT_v2-rev_20250915.txt"

# モデル名（必要に応じて変更）
DEFAULT_MODEL = "gpt-5.1-mini"

client = OpenAI()


def load_master_prompt() -> str:
    """
    マスタープロンプトファイルを読み込む。

    pack/MASTER_PROMPT_v2-rev_20250915.txt が存在しない場合は例外を投げる。
    （本番運用では必須ファイルとする）
    """
    if not MASTER_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"MASTER_PROMPT not found: {MASTER_PROMPT_PATH}"
        )
    return MASTER_PROMPT_PATH.read_text(encoding="utf-8")


def build_prompt_for_course(block: Dict[str, Any]) -> str:
    """
    MASTER_PROMPT の末尾に、コースメタ情報と原文をセクションとして付ける。

    [COURSE_META]
    [SOURCE_TEXT]

    といったタグで区切ることで、MASTER_PROMPT 側で
    「どこからどこまでが入力か」を明示しやすくする。
    """
    master = load_master_prompt()

    course_no = block.get("courseNo", "")
    period = block.get("period") or {}
    period_start = period.get("start", "")
    period_end = period.get("end", "")

    # メタ情報セクション
    meta_section = (
        "[COURSE_META]\n"
        f"コースNo: {course_no}\n"
        f"期間: {period_start}〜{period_end}\n"
    )

    # 行番号付き原文セクション
    lines = block.get("lines", [])
    lines_text = "\n".join(f"{i + 1}: {ln}" for i, ln in enumerate(lines))
    source_section = "[SOURCE_TEXT]\n" + lines_text + "\n"

    # MASTER_PROMPT の後ろに入力ブロックを連結
    prompt = (
        master.rstrip()
        + "\n\n"
        + meta_section
        + "\n"
        + source_section
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
        実際の検証は validator.validate_schema で行う。
    """
    prompt = build_prompt_for_course(block)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "あなたは旅行会社のFNL作成を支援する抽出エンジンです。"
                    "EXTRACT_SCHEMA.json に従った JSON オブジェクトのみを返してください。"
                    "トップレベルは {\"courses\": [...]} という構造にし、"
                    "余計な文章や説明文は一切出力してはいけません。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM 抽出結果が空です")

    data = json.loads(content)
    return data


if __name__ == "__main__":
    # 簡易動作テスト用（APIキー必須）
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
        print("extract_with_llm error:", repr(e))
