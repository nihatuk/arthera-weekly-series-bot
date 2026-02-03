
import xml.etree.ElementTree as ET
import requests
from urllib.parse import quote_plus
from .utils import clean_text, stable_id

BASE = "https://news.google.com/rss/search"

def fetch_google_news_items(cfg):
    hl, gl, ceid = cfg["hl"], cfg["gl"], cfg["ceid"]
    days = int(cfg.get("days", 7))
    max_items = int(cfg.get("max_items", 25))
    queries = list(cfg.get("queries", []))
    site_filters = list(cfg.get("site_filters", []))

    all_items = []

    for q in queries:
        rss_url = f"{BASE}?q={quote_plus(q + f' when:{days}d')}&hl={hl}&gl={gl}&ceid={ceid}"
        all_items.extend(_parse_rss(rss_url, source="Google News", limit=max_items))

    for domain in site_filters:
        for q in queries[:3]:
            qq = f"site:{domain} {q} when:{days}d"
            rss_url = f"{BASE}?q={quote_plus(qq)}&hl={hl}&gl={gl}&ceid={ceid}"
            all_items.extend(_parse_rss(rss_url, source=f"Google News (site:{domain})", limit=max_items//2))

    dedup = {}
    for it in all_items:
        dedup[it["url"]] = it
    return list(dedup.values())

def _parse_rss(url, source, limit=20):
    r = requests.get(url, timeout=30, headers={"User-Agent": "ArtheraDigestBot/2.0"})
    r.raise_for_status()
    root = ET.fromstring(r.text)
    channel = root.find("channel")
    if channel is None:
        return []

    items = []
    for item in channel.findall("item")[:limit]:
        title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        desc = clean_text(item.findtext("description"))
        pub = clean_text(item.findtext("pubDate"))
        if not link:
            continue

        items.append({
            "id": stable_id(source, link, title),
            "source": source,
            "title": title,
            "url": link,
            "snippet": desc,
            "published": pub,
            "kind": "news"
        })
    return items

