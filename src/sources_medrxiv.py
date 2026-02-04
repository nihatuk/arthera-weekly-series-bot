# src/sources_medrxiv.py
import xml.etree.ElementTree as ET
import requests
from .utils import clean_text, stable_id

def fetch_medrxiv_items(cfg):
    feeds = cfg.get("feeds", [])
    limit = int(cfg.get("max_items_per_feed", 30))
    items = []

    for url in feeds:
        try:
            items.extend(_parse_atom(url, source="medRxiv", limit=limit))
        except Exception as e:
            # bir feed bozulsa diğerleri devam etsin
            print("medRxiv feed parse failed:", url, e)

    # URL bazlı dedup
    dedup = {it["url"]: it for it in items if it.get("url")}
    return list(dedup.values())

def _parse_atom(url, source="medRxiv", limit=30):
    r = requests.get(url, timeout=30, headers={"User-Agent": "ArtheraSeriesBot/1.0"})
    r.raise_for_status()

    root = ET.fromstring(r.text)

    # Atom feed: entry'ler namespace'li olabilir, wildcard ile yakala
    entries = root.findall(".//{*}entry")
    if not entries:
        # Bazı feed'ler RSS dönebilir, fallback:
        return _parse_rss_fallback(root, source=source, limit=limit)

    out = []
    for e in entries[:limit]:
        title = clean_text((e.findtext("{*}title") or "").strip())

        # link: rel=alternate tercih et
        link = ""
        for link_el in e.findall("{*}link"):
            href = link_el.attrib.get("href", "")
            rel = link_el.attrib.get("rel", "")
            if rel == "alternate" and href:
                link = href
                break
            if not link and href:
                link = href
        link = clean_text(link)

        # summary/content
        summary = clean_text(e.findtext("{*}summary") or "")
        if not summary:
            # bazen content içinde html olur
            summary = clean_text(e.findtext("{*}content") or "")

        published = clean_text(e.findtext("{*}published") or e.findtext("{*}updated") or "")

        if link:
            out.append({
                "id": stable_id(source, link, title),
                "source": source,
                "title": title,
                "url": link,
                "snippet": summary,
                "published": published,
                "kind": "preprint"
            })

    return out

def _parse_rss_fallback(root, source="medRxiv", limit=30):
    channel = root.find(".//channel")
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
                "kind": "preprint"
            })
    return out
