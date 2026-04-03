# -*- coding: utf-8 -*-
import os
import anthropic
from .voice import clean

_client = None

def _ai():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


VOICE_SYSTEM = (
    "あなたは日本の法律専門アドバイザーです。"
    "VoiceOSで音声読み上げされます。必ず以下を守ってください。"
    "マークダウン記号（**、##、-、*、#）を絶対に使わない。"
    "150文字以内の自然な話し言葉で答える。"
    "根拠条文を「第○条によると」の形で示す。"
    "罰則は「○万円以下の罰金」「○年以下の懲役」の形で具体的に示す。"
    "不明な点は「確認が必要です」と伝える。"
)


def ask(question, context_articles=None, law_names=None, max_tokens=350):
    system = VOICE_SYSTEM
    if law_names:
        system += "参照法律: " + "、".join(law_names) + "。"

    content = question
    if context_articles:
        snippets = "\n".join(
            "【" + a.get("law", "") + " 第" + a.get("article", "") + "条】" + a.get("text", "")[:200]
            for a in context_articles[:4]
        )
        content = "以下の条文を参考に答えてください。\n" + snippets + "\n\n質問: " + question

    resp = _ai().messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return clean(text)


def summarize_amendment(law_name, raw_data, max_tokens=200):
    prompt = (
        law_name + "のデータに変更がありました。"
        "改正の要点を70文字以内の話し言葉で要約してください。"
        "マークダウン不可。データ: " + str(raw_data)[:1200]
    )
    resp = _ai().messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "改正内容をご確認ください。")
    return clean(text, 100)
