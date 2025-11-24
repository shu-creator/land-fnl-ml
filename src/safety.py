# src/safety.py
# 目的: 最終整形後のテキストに「禁則ワード」が混入していないか確認する
# LLM抽出前のプロンプトでも除外するが、二重バリアとしてPython側でも確認する

import re
from typing import List

# 禁則ワード一覧
# 必要に応じて pack/MASTER_PROMPT に合わせて増やして良い
NG_PATTERNS: List[str] = [
    r"座席",
    r"並び席",
    r"保険",
    r"返金",
    r"金銭",
    r"旅券",
    r"\bJR\b",
    r"社内進行",
]


def contains_ng_terms(text: str) -> bool:
    """
    テキスト中に禁則ワードが含まれている場合 True。
    """
    return any(re.search(pat, text) for pat in NG_PATTERNS)


def find_all_ng_terms(text: str) -> List[str]:
    """
    発見された禁則ワードをすべて返す（デバッグ用）。
    """
    hits = []
    for pat in NG_PATTERNS:
        m = re.search(pat, text)
        if m:
            hits.append(m.group(0))
    return hits


if __name__ == "__main__":
    # 動作確認用
    sample = "座席 窓側 希望 / 保険は不要"
    print(contains_ng_terms(sample))     # True
    print(find_all_ng_terms(sample))     # ['座席', '保険']
