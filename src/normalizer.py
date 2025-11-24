# src/normalizer.py
# 目的: 正規化 + 行抽出 + コース単位ブロック化
# このモジュールは Step0 に相当し、Python ルールベースで前処理を行う。

import re
import unicodedata
from typing import List, Dict, Any


def z2h(s: str) -> str:
    """
    全角 → 半角 正規化 (NFKC)
    """
    return unicodedata.normalize("NFKC", s)


def normalize_lines(raw: str) -> List[str]:
    """
    正規化・空白調整・装飾削除を行い、きれいな行リストを返す。

    - 改行統一
    - 空白圧縮
    - 装飾線の削除
    - Page x/y 削除
    """
    s = z2h(raw)

    # 改行コード統一
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # 連続スペース圧縮・全角スペース除去
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\u3000+", " ", s)

    # 余計な連続改行は 2 個までにする
    s = re.sub(r"\n{3,}", "\n\n", s)

    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]

    cleaned: List[str] = []
    for ln in lines:
        # 装飾線（----、____、==== など）
        if re.fullmatch(r"[-_=]{4,}", ln):
            continue
        # ページ表記
        if re.search(r"Page \d+/\d+", ln, flags=re.I):
            continue

        cleaned.append(ln)

    return cleaned


def find_course_blocks(lines: List[str]) -> List[Dict[str, Any]]:
    """
    コース単位のブロックを抽出する。
    戻り値は、以下の構造のリスト。

    {
        "courseNo": str,
        "period": {"start": str, "end": str},
        "lines": [str, ...]
    }

    前提:
    - コースNo は「コースNo: XXX」「Course: XXX」にマッチ
    - 期間は YYYY-MM-DD〜YYYY-MM-DD にマッチ
    """
    blocks: List[Dict[str, Any]] = []
    cur = {
        "courseNo": "",
        "period": {"start": "", "end": ""},
        "lines": []
    }

    for ln in lines:
        # コース No 検出
        m_course = re.search(r"(コースNo|Course)[:：]?\s*([A-Za-z0-9\-]+)", ln)
        if m_course:
            # 既存ブロックがあれば確定
            if cur["lines"]:
                blocks.append(cur)
                cur = {
                    "courseNo": "",
                    "period": {"start": "", "end": ""},
                    "lines": []
                }

            cur["courseNo"] = m_course.group(2)

        # 期間検出（先に出てきてもよい）
        m_period = re.search(r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})", ln)
        if m_period:
            cur["period"] = {
                "start": m_period.group(1),
                "end": m_period.group(2)
            }

        # とりあえず全て行に保持
        cur["lines"].append(ln)

    # 最後のブロックを確定
    if cur["lines"]:
        blocks.append(cur)

    return blocks


if __name__ == "__main__":
    # 簡易動作確認用
    sample = """
    コースNo: ABC123
    2025-09-01〜2025-09-05
    参加者一覧
    ------
    氏名 太郎
    Page 1/3
    """

    lines = normalize_lines(sample)
    blocks = find_course_blocks(lines)
    print(lines)
    print(blocks)
