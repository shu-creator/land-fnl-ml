# src/pipeline.py
# 目的: 全ステップ（Step0〜Step4）をまとめて実行するパイプライン (CLI エントリポイント)
#
# フロー:
#   入力テキスト
#     → 正規化 (normalize_lines)
#     → コース単位ブロック化 (find_course_blocks)
#     → LLM抽出 (extract_with_llm)
#     → スキーマ検証 (validate_schema)
#     → 意味検証 (validate_semantic_with_llm)
#     → 整形テキスト化 (render_text)
#     → 禁則ワードチェック (contains_ng_terms)
#
# 使い方:
#   python3 -m src.pipeline input.txt

from __future__ import annotations

import sys
import pathlib
from typing import Any, Dict, List

from .normalizer import normalize_lines, find_course_blocks
from .llm_extractor import extract_with_llm
from .validator import validate_schema
from .llm_validator import validate_semantic_with_llm
from .formatter import render_text
from .safety import contains_ng_terms, find_all_ng_terms


def _print_review_report(all_reviews: List[Dict[str, Any]]) -> None:
    """
    人間が読むためのレビュー結果を stderr にまとめて出力する。

    仕様:
    - パイプライン本体の出力(stdout)には混ぜない
    - コース単位に errors / warnings を一覧表示
    """
    if not all_reviews:
        return

    sys.stderr.write("\n=== Semantic Review Report (for human check) ===\n")
    for item in all_reviews:
        course_no = item.get("courseNo", "UNKNOWN")
        review = item.get("review", {}) or {}
        ok = review.get("ok", True)
        errors = review.get("errors") or []
        warnings = review.get("warnings") or []

        sys.stderr.write(f"\n[Course: {course_no}] ok = {ok}\n")

        if errors:
            sys.stderr.write("  Errors:\n")
            for e in errors:
                code = e.get("code", "")
                msg = e.get("message", "")
                sys.stderr.write(f"    - {code}: {msg}\n")

        if warnings:
            sys.stderr.write("  Warnings:\n")
            for w in warnings:
                code = w.get("code", "")
                msg = w.get("message", "")
                sys.stderr.write(f"    - {code}: {msg}\n")


def process_text(raw: str) -> str:
    """
    生テキスト文字列から FNL 用の最終テキストを生成するメイン処理。
    エラーがあれば例外を投げる。
    """
    # Step0: 正規化
    lines = normalize_lines(raw)

    # Step0: コース単位ブロック化
    blocks = find_course_blocks(lines)

    all_courses: List[Dict[str, Any]] = []
    all_reviews: List[Dict[str, Any]] = []

    # 各コースブロックごとに抽出〜検証
    for idx, block in enumerate(blocks):
        course_no = block.get("courseNo") or f"BLOCK-{idx+1}"

        # Step2: LLM抽出
        extracted = extract_with_llm(block)

        # Step3a: 構造検証 (jsonschema)
        try:
            validate_schema(extracted)
        except Exception as e:
            # コース単位でどこが壊れているか分かるようにする
            raise RuntimeError(
                f"Schema validation failed for course {course_no}: {e}"
            ) from e

        # Step3b: 意味検証 (LLMレビュー)
        try:
            review = validate_semantic_with_llm(block, extracted)
        except Exception as e:
            # 意味検証自体ができなかった場合は致命的とみなして例外
            raise RuntimeError(
                f"Semantic validation call failed for course {course_no}: {e}"
            ) from e

        # レビュー結果を集約（後で人間が読む用）
        all_reviews.append(
            {
                "courseNo": course_no,
                "review": review,
            }
        )

        # ok=False の場合は警告のみ（処理は継続）
        if not review.get("ok", True):
            sys.stderr.write(
                f"[WARN] Semantic validation not OK for course {course_no}:\n"
            )
            sys.stderr.write(f"  errors: {review.get('errors')}\n")
            sys.stderr.write(f"  warnings: {review.get('warnings')}\n")

        # courses 配列を統合
        course_list = extracted.get("courses", [])
        all_courses.extend(course_list)

    # Step4: 整形 (テキストレンダリング)
    payload = {"courses": all_courses}
    text = render_text(payload)

    # 最終 Step: 禁則ワードチェック（二重バリア）
    if contains_ng_terms(text):
        hits = find_all_ng_terms(text)
        raise SystemExit(
            "NGワード（座席・保険・金銭など）が出力に含まれています。"
            f" 該当: {', '.join(set(hits))}"
        )

    # レビュー結果を stderr にまとめて表示（本文とは分離）
    _print_review_report(all_reviews)

    return text


def main() -> None:
    """
    CLI エントリポイント。
    usage:
        python -m src.pipeline input.txt
    """
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m src.pipeline <input.txt>")

    path = pathlib.Path(sys.argv[1])
    if not path.exists():
        raise SystemExit(f"input file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    result = process_text(raw)
    print(result)


if __name__ == "__main__":
    main()
