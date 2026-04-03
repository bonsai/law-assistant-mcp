# -*- coding: utf-8 -*-
import os
import hashlib
import time
import httpx
from .cache import cache, TTL_SEARCH, TTL_LAW, TTL_REVISION

BASE = "https://laws.e-gov.go.jp/api/1"
TIMEOUT = int(os.environ.get("EGOV_TIMEOUT_MS", "20000")) / 1000


def _get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = httpx.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)


def search_laws(keyword):
    key = "search:" + keyword
    cached = cache.get(key)
    if cached:
        return cached
    data = _get(BASE + "/laws", params={"law_title": keyword})
    cache.set(key, data, TTL_SEARCH)
    return data


def get_law_data(law_id):
    key = "law:" + law_id
    cached = cache.get(key)
    if cached:
        return cached
    data = _get(BASE + "/lawdata/" + law_id)
    cache.set(key, data, TTL_LAW)
    return data


def get_law_hash(law_id):
    data = get_law_data(law_id)
    raw = str(data).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_revisions(law_id):
    key = "rev:" + law_id
    cached = cache.get(key)
    if cached:
        return cached
    try:
        data = _get(BASE + "/law_revisions/" + law_id)
        cache.set(key, data, TTL_REVISION)
        return data
    except Exception:
        return {}


def resolve_law_id(law_name):
    results = search_laws(law_name)
    laws = results.get("laws") or results.get("law_list") or []
    if not laws:
        return None
    exact = next((l for l in laws if l.get("law_title") == law_name), None)
    match = exact or laws[0]
    return match.get("law_id") or match.get("LawId")


def extract_article(xml_text, article_number):
    import re
    num = article_number.strip().lstrip("第").rstrip("条")
    pattern = r'<Article[^>]+Num="' + re.escape(num) + r'"[^>]*>(.*?)</Article>'
    m = re.search(pattern, xml_text, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = ' '.join(text.split())
    return text


def search_in_law(xml_text, keyword, max_results=5):
    import re
    results = []
    pattern = r'<Article[^>]+Num="([^"]+)"[^>]*>(.*?)</Article>'
    for m in re.finditer(pattern, xml_text, re.DOTALL):
        raw = m.group(2)
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = ' '.join(text.split())
        if keyword in text:
            results.append({"article": m.group(1), "text": text[:300]})
            if len(results) >= max_results:
                break
    return results


def get_full_text(law_id):
    data = get_law_data(law_id)
    xml = (data.get("law_full_text")
           or data.get("LawFullText")
           or data.get("law_text")
           or "")
    return xml
