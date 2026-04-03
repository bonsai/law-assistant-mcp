# -*- coding: utf-8 -*-
import re

def clean(text, limit=150):
    t = re.sub(r'[#*_`>\-]{1,3}\s?', '', text)
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > limit:
        cut = t[:limit]
        last = max(cut.rfind('。'), cut.rfind('、'), cut.rfind(' '))
        t = cut[:last + 1] if last > limit // 2 else cut + '。'
    return t


def ok(text):
    return clean(text, 150)


def ng(law_name, what):
    return law_name + 'の' + what + 'については情報を取得できませんでした。'
