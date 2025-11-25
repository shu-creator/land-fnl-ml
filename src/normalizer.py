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

    ポイント:
    - 「コースNo が検出されていないブロック」は blocks に追加しない。
      → 冒頭のヘッダだけの BLOCK-1 などを作らない。
    """
    blocks: List[Dict[str, Any]] = []

    # 現在構築中のブロック
    cur: Dict[str, Any] = {
        "courseNo": "",
        "period": {"start": "", "end": ""},
        "lines": [],
    }

    for ln in lines:
        # コース No 検出
        m_course = re.search(r"(コースNo|Course)[:：]?\s*([A-Za-z0-9\-]+)", ln)
        if m_course:
            # 直前のブロックに courseNo が入っていれば、1コースとして確定させる
            if cur["courseNo"]:
                blocks.append(cur)

            # 新しいブロックを開始
            cur = {
                "courseNo": m_course.group(2),
                "period": {"start": "", "end": ""},
                "lines": [],
            }

        # 期間検出（例: 2025-09-01〜2025-09-05）
        m_period = re.search(r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})", ln)
        if m_period and cur["courseNo"]:
            cur["period"] = {
                "start": m_period.group(1),
                "end": m_period.group(2),
            }

        # 現在のブロックに行を追加
        # （まだ courseNo が見つかっていないヘッダ行は捨てる）
        if cur["courseNo"]:
            cur["lines"].append(ln)

    # ループ終了後、最後のブロックに courseNo があれば追加
    if cur["courseNo"] and cur["lines"]:
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
