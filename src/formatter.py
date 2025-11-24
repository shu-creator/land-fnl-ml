# src/formatter.py
# 目的: 抽出済み JSON（EXTRACT_SCHEMA.json 準拠）を
#       FNL用テキストとして整形する (Step4)

from typing import Dict, Any, List


def _safe(v: Any) -> str:
    """None を空文字に変換する簡易ヘルパー。"""
    return "" if v is None else str(v)


def _join_nonempty(sep: str, parts: List[str]) -> str:
    """空文字を除外して結合."""
    return sep.join([p for p in parts if p])


def render_text(doc: Dict[str, Any]) -> str:
    """
    EXTRACT_SCHEMA.json に従う JSON を、人間向けテキストとして整形する。
    fields が空ならその行は出力しない。
    日付は EXTRACT_SCHEMA 側で検証されている前提。

    戻り値: FNL用テキスト（複数行）
    """
    out_lines: List[str] = []

    courses = doc.get("courses", [])
    if not courses:
        return ""

    for c in courses:
        # --------------------------------
        # ツアー基本情報
        # --------------------------------
        out_lines.append("ツアー情報:")
        period = c.get("period", {})
        out_lines.append(
            f"- コースNo: {c.get('courseNo','')} / 期間: "
            f"{_safe(period.get('start'))}–{_safe(period.get('end'))}"
        )
        out_lines.append("")

        # --------------------------------
        # 参加者ブロック
        # --------------------------------
        participants = c.get("participants", [])
        if participants:
            out_lines.append("参加者（該当のみ）:")

        for p in participants:
            # 見出し
            out_lines.append(
                f"{c.get('courseNo','')} No.{p.get('no','')} "
                f"{p.get('nameJP','')} / {p.get('nameEN','')}（問番:{p.get('inquiryNo','')}）"
            )

            # 参加形態 (L/O)
            jt = p.get("joinType") or {}
            meet = jt.get("meet") or {}
            flight = jt.get("flight") or {}
            transfer = jt.get("transfer") or ""

            if jt:
                seg = (
                    f"- 参加形態: L/O（"
                    f"合流:{_safe(meet.get('place'))}/{_safe(meet.get('datetime'))} "
                    f"送迎:{_safe(transfer)} "
                    f"個人便:{_safe(flight.get('arrive'))}/{_safe(flight.get('depart'))}"
                    f"）"
                )
                out_lines.append(seg)

            # ルーミング
            if p.get("roomingRQ"):
                out_lines.append(f"- ルーミング要望: {' / '.join(p['roomingRQ'])}")

            # OP
            if p.get("optionalRQ"):
                for op in p["optionalRQ"]:
                    date = op.get("date") or "不明"
                    pax = op.get("pax") or ""
                    out_lines.append(
                        f"- オプショナル: {op.get('name','')} / RQ / {date} / {pax}名"
                    )

            # ハネムーン・入籍・記念日など
            if p.get("celebration"):
                out_lines.append(f"- 特別依頼: {' / '.join(p['celebration'])}")

            # 食事・アレルギー
            if p.get("meal_allergy"):
                out_lines.append(f"- 食事・アレルギー: {p['meal_allergy']}")

            # 医療・介助
            if p.get("medical"):
                out_lines.append(f"- 医療・介助: {p['medical']}")

            # 航空会社関連
            al = p.get("airline") or {}
            al_fields = [
                ("meal", "機内食"),
                ("assist", "搭乗支援"),
                ("carryOn", "機内持込"),
                ("arrivalImpact", "到着影響"),
            ]
            if any(al.get(k) for k, _ in al_fields):
                out_lines.append("- 航空会社関連:")
                for k, label in al_fields:
                    if al.get(k):
                        out_lines.append(f"  - {label}: {al[k]}")

            # 日程・集合影響
            if p.get("scheduleImpact"):
                out_lines.append(f"- 日程・集合影響: {p['scheduleImpact']}")

            # バス座席/グループ
            if p.get("busSeating"):
                out_lines.append(f"- バス座席/グループ: {p['busSeating']}")

            # 装備サイズ
            gs = p.get("gearSizes") or {}
            segs = []
            if gs.get("top"):
                segs.append(f"服のサイズ{gs['top']}")
            if gs.get("bottom"):
                segs.append(f"ズボン{gs['bottom']}")
            if gs.get("shoes"):
                segs.append(f"靴{gs['shoes']}")
            if gs.get("height_cm"):
                segs.append(f"身長{gs['height_cm']}cm")
            if gs.get("weight_kg"):
                segs.append(f"体重{gs['weight_kg']}kg")

            if segs:
                out_lines.append("- 装備・レンタルサイズ: " + " ".join(segs))

            # 別問番同行GRP
            og_list = p.get("otherGroup") or []
            for og in og_list:
                room = ""
                if og.get("roomType"):
                    room = f" 同室={og['roomType']}"
                status = og.get("status") or ""
                out_lines.append(
                    f"- 別問番同行GRP: {og.get('name','')}/{og.get('inquiryNo','')}"
                    f"{room} {status}"
                )

            # 参加者ごとの空行
            out_lines.append("")

        # コースごとの区切り
        out_lines.append("")

    return "\n".join(out_lines).strip()
