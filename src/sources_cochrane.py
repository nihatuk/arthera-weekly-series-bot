
# src/sources_cochrane.py
import xml.etree.ElementTree as ET
import requests
from .utils import clean_text, stable_id

def fetch_cochrane_items(cfg):
    feeds = cfg.get("feeds", [])
    limit = int(cfg.get("max_items_per_feed", 30))
    items = []

    for url in feeds:
        items.extend(_parse_rss(url, source="Cochrane", limit=limit))

    dedup = {it["url"]: it for it in items if it.get("url")}
    return list(dedup.values())

def _parse_rss(url, source="Cochrane", limit=30):
    r = requests.get(url, timeout=30, headers={"User-Agent": "ArtheraSeriesBot/1.0"})
    r.raise_for_status()

    root = ET.fromstring(r.text)
    channel = root.find("channel")
    if channel is None:
        return []

    out = []
    for it in channel.findall("item")[:limit]:
        title = clean_text(it.findtext("title"))
        link = clean_text(it.findtext("link"))
        desc = clean_text(it.findtext("description"))
        pub = clean_text(it.findtext("pubDate"))

        if link:
            out.append({
                "id": stable_id(source, link, title),
                "source": source,
                "title": title,
                "url": link,
                "snippet": desc,
                "published": pub,
                "kind": "review"
            })
    return out

