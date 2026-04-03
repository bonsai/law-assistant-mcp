# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from core.egov_client import (
    get_law_hash, get_law_data, get_full_text,
    resolve_law_id, extract_article, search_in_law, search_laws
)
from core.claude_client import ask, summarize_amendment
from core.voice import ok, ng

# ── パス設定 ──────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
INDUSTRIES_FILE = BASE_DIR / "data" / "industries.json"
STATE_FILE      = BASE_DIR / "data" / "watch_state.json"
AMENDMENTS_FILE = BASE_DIR / "data" / "amendments.jsonl"

mcp = FastMCP("法律アシスタント")


# ── ヘルパー ──────────────────────────────────────────────────
def _industries():
    return json.loads(INDUSTRIES_FILE.read_text(encoding="utf-8"))


def _state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    # 初回: 全業種の法律を登録
    data = _industries()
    state = {}
    for ind_key, ind in data.items():
        for law in ind["laws"]:
            if law["id"] not in state:
                state[law["id"]] = {
                    "name":     law["name"],
                    "industry": ind_key,
                    "hash":     None,
                }
    _save_state(state)
    return state


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _save_amendment(record):
    AMENDMENTS_FILE.parent.mkdir(exist_ok=True)
    with open(AMENDMENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_amendments(n=5, industry=None):
    if not AMENDMENTS_FILE.exists():
        return []
    lines = AMENDMENTS_FILE.read_text(encoding="utf-8").strip().splitlines()
    results = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if industry and r.get("industry") != industry:
                continue
            results.append(r)
            if len(results) >= n:
                break
        except json.JSONDecodeError:
            pass
    return results


def _laws_for(industry=None):
    state = _state()
    if not industry:
        return list(state.items())
    return [(lid, info) for lid, info in state.items()
            if info.get("industry") == industry]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# グループ A: Q&A ツール
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
def ask_law(question: str, industry: str = "", law_name: str = "") -> str:
    """
    法律について自由に質問する。
    industry に transport / construction / food / entertainment /
    medical / labor / it / finance を指定すると関連法を自動参照。
    例: ask_law("深夜に酒類を提供するには何の届出が必要？", industry="food")
    """
    context = []
    law_names = []

    target_laws = []
    if law_name:
        target_laws = [{"name": law_name, "id": None}]
    elif industry:
        inds = _industries()
        target_laws = inds.get(industry, {}).get("laws", [])

    for law in target_laws[:3]:
        lid = law.get("id") or resolve_law_id(law["name"])
        if not lid:
            continue
        xml = get_full_text(lid)
        hits = search_in_law(xml, question[:20], max_results=2)
        for h in hits:
            context.append({"law": law["name"], "article": h["article"], "text": h["text"]})
        law_names.append(law["name"])

    return ask(question, context_articles=context, law_names=law_names or None)


@mcp.tool()
def is_legal(behavior: str, industry: str = "") -> str:
    """
    ある行為が法律違反かどうか判定する。
    例: is_legal("18歳未満をホール業務に雇用する", industry="entertainment")
    """
    q = (
        "「" + behavior + "」は日本の法律に違反しますか？"
        "「違反です」または「違反ではありません」で始めて、"
        "根拠の条文番号と罰則を簡潔に答えてください。"
    )
    context = []
    law_names = []
    if industry:
        inds = _industries()
        for law in inds.get(industry, {}).get("laws", [])[:3]:
            lid = law.get("id") or resolve_law_id(law["name"])
            if not lid:
                continue
            xml = get_full_text(lid)
            hits = search_in_law(xml, behavior[:15], max_results=2)
            for h in hits:
                context.append({"law": law["name"], "article": h["article"], "text": h["text"]})
            law_names.append(law["name"])

    return ask(q, context_articles=context, law_names=law_names or None)


@mcp.tool()
def get_penalty(violation: str, law_name: str = "", industry: str = "") -> str:
    """
    違反行為の罰則・罰金・行政処分を調べる。
    例: get_penalty("無免許運転", law_name="道路交通法")
         get_penalty("無許可営業", industry="food")
    """
    q = (
        "「" + violation + "」の罰則を教えてください。"
        "反則金・罰金の金額、懲役期間、免許取消などの行政処分を"
        "根拠条文とともに具体的に答えてください。"
    )
    names = [law_name] if law_name else []
    if industry and not law_name:
        inds = _industries()
        names = [l["name"] for l in inds.get(industry, {}).get("laws", [])[:3]]

    return ask(q, law_names=names or None)


@mcp.tool()
def get_article(law_name: str, article_number: str) -> str:
    """
    公式条文をそのまま取得（AI非介入・幻覚ゼロモード）。
    例: get_article("食品衛生法", "6")
         get_article("道路交通法", "65")
    """
    lid = resolve_law_id(law_name)
    if not lid:
        return ng(law_name, "法令ID")
    xml = get_full_text(lid)
    text = extract_article(xml, article_number)
    if not text:
        return law_name + " 第" + article_number + "条は見つかりませんでした。"
    # 公式条文はそのまま返す（voice整形しない）
    return "【" + law_name + " 第" + article_number + "条】" + text[:400]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# グループ B: 監視・通知ツール
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
def check_updates(industry: str = "") -> str:
    """
    法律の改正をチェックする。
    industry を省略すると全監視法律をチェック（時間がかかります）。
    例: check_updates(industry="food")  → 食品関連法だけチェック
         check_updates()                → 全法律チェック
    """
    targets = _laws_for(industry or None)
    state   = _state()
    updated = []
    failed  = []

    for law_id, info in targets:
        law_name = info.get("name", law_id)
        ind_key  = info.get("industry", "")
        try:
            current_hash = get_law_hash(law_id)
        except Exception:
            failed.append(law_name)
            continue

        prev_hash = info.get("hash")
        now = datetime.now().isoformat()

        if prev_hash is None:
            state[law_id]["hash"]         = current_hash
            state[law_id]["last_checked"] = now

        elif current_hash != prev_hash:
            try:
                data    = get_law_data(law_id)
                summary = summarize_amendment(law_name, data)
            except Exception:
                summary = "改正内容を確認してください。"

            _save_amendment({
                "detected_at": now,
                "law_name":    law_name,
                "law_id":      law_id,
                "industry":    ind_key,
                "summary":     summary,
            })
            state[law_id]["hash"]         = current_hash
            state[law_id]["last_changed"] = now
            updated.append(law_name + ": " + ok(summary, 50))

        else:
            state[law_id]["last_checked"] = now

    _save_state(state)

    if not updated and not failed:
        label = _industries().get(industry, {}).get("label", "全法律") if industry else "全法律"
        return label + "に改正は見つかりませんでした。"

    parts = []
    if updated:
        parts.append(str(len(updated)) + "件の法改正を検知しました。" + " ".join(updated))
    if failed:
        parts.append(str(len(failed)) + "件は取得できませんでした。")
    return " ".join(parts)


@mcp.tool()
def get_amendments(count: int = 3, industry: str = "") -> str:
    """
    過去に検知した法改正通知を取得する。
    例: get_amendments(count=5)
         get_amendments(industry="labor")
    """
    records = _load_amendments(count, industry or None)
    if not records:
        return "まだ改正通知はありません。check_updates で最新情報を確認してください。"

    ind_label = ""
    if industry:
        ind_label = _industries().get(industry, {}).get("label", industry) + "の"

    parts = ["直近" + str(len(records)) + "件の" + ind_label + "法改正をお伝えします。"]
    for r in records:
        date    = r.get("detected_at", "")[:10]
        name    = r.get("law_name", "不明")
        summary = ok(r.get("summary", ""), 60)
        parts.append(date + "に" + name + "が改正されました。" + summary)

    return " ".join(parts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# グループ C: 設定・管理ツール
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
def list_industries() -> str:
    """登録されている業種の一覧を返す。"""
    inds = _industries()
    items = [v["label"] + "(" + k + ")" for k, v in inds.items()]
    return "登録業種は" + str(len(items)) + "種類です。" + "、".join(items) + "。"


@mcp.tool()
def list_laws(industry: str = "") -> str:
    """
    監視中の法律一覧を返す。industry を指定するとその業種だけ表示。
    例: list_laws(industry="medical")
    """
    targets = _laws_for(industry or None)
    if not targets:
        return "監視中の法律はありません。"

    names = [info.get("name", lid) for lid, info in targets]
    label = ""
    if industry:
        label = _industries().get(industry, {}).get("label", industry) + "の"
    return label + "監視法律は" + str(len(names)) + "件です。" + "、".join(names) + "。"


@mcp.tool()
def add_law(law_name: str, industry: str = "other") -> str:
    """
    監視リストに新しい法律を追加する。
    例: add_law("景品表示法", industry="it")
         add_law("消防法", industry="construction")
    """
    try:
        results = search_laws(law_name)
        laws = results.get("laws") or results.get("law_list") or []
    except Exception:
        return "e-Govへの接続に失敗しました。後でもう一度お試しください。"

    if not laws:
        return "「" + law_name + "」はe-Govで見つかりませんでした。正式名称で試してください。"

    exact = next((l for l in laws if l.get("law_title") == law_name), None)
    match = exact or laws[0]
    law_id    = match.get("law_id") or match.get("LawId", "")
    found_name = match.get("law_title") or match.get("LawTitle", law_name)

    state = _state()
    if law_id in state:
        return "「" + found_name + "」はすでに監視リストに登録されています。"

    state[law_id] = {
        "name":     found_name,
        "industry": industry,
        "hash":     None,
        "added_at": datetime.now().isoformat(),
    }
    _save_state(state)
    return "「" + found_name + "」を" + industry + "業種として監視リストに追加しました。"


# ── 起動 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
