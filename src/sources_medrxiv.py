# src/sources_medrxiv.py
import xml.etree.ElementTree as ET
import requests
from .utils import clean_text, stable_id

def fetch_medrxiv_items(cfg):
    feeds = cfg.get("feeds", [])
    limit = int(cfg.get("max_items_per_feed", 30))
    items = []

    for url in feeds:
        items.extend(_parse_atom_or_rss(url, source="medRxiv", limit=limit))

    # URL bazlı dedup
    dedup = {it["url"]: it for it in items if it.get("url")}
    return list(dedup.values())

def _parse_atom_or_rss(url, source="medRxiv", limit=30):
    r = requests.get(url, timeout=30, headers={"User-Agent": "ArtheraSeriesBot/1.0"})
    r.raise_for_status()

    root = ET.fromstring(r.text)

    # Atom: <feed><entry>...
    entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    if entries:
        out = []
        for e in entries[:limit]:
            title = clean_text(e.findtext("{http://www.w3.org/2005/Atom}title"))
            link_el = e.find("{http://www.w3.org/2005/Atom}link")
            link = clean_text(link_el.attrib.get("href") if link_el is not None else "")
            summary = clean_text(e.findtext("{http://www.w3.org/2005/Atom}summary"))
            published = clean_text(e.findtext("{http://www.w3.org/2005/Atom}published") or e.findtext("{http://www.w3.org/2005/Atom}updated"))

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

    # RSS: <rss><channel><item>...
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
                "kind": "preprint"
            })
    return out

