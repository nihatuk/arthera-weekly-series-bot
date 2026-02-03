
import time
import requests
from .utils import stable_id, clean_text

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

def fetch_pubmed_items(cfg):
    retmax = int(cfg.get("retmax", 8))
    days = int(cfg.get("days", 30))
    terms = cfg.get("terms", [])

    query = " OR ".join([t if t.startswith("(") else f"({t})" for t in terms])
    pmids = _esearch(query, retmax=retmax, reldate=days)
    if not pmids:
        return []

    summaries = _esummary(pmids)
    items = []
    for s in summaries:
        title = clean_text(s.get("title", ""))
        url = f"https://pubmed.ncbi.nlm.nih.gov/{s.get('uid')}/"
        pubdate = clean_text(s.get("pubdate", ""))
        journal = clean_text(s.get("fulljournalname", ""))
        items.append({
            "id": stable_id("PubMed", url, title),
            "source": "PubMed",
            "title": title,
            "url": url,
            "snippet": clean_text(f"{journal}. {pubdate}"),
            "published": pubdate,
            "kind": "paper"
        })
    return items

def _esearch(term, retmax=10, reldate=30):
    url = BASE + "esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": retmax,
        "reldate": reldate,
        "datetype": "pdat",
        "sort": "date"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(0.35)
    return r.json().get("esearchresult", {}).get("idlist", [])

def _esummary(pmids):
    url = BASE + "esummary.fcgi"
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(0.35)
    data = r.json().get("result", {})
    uids = data.get("uids", [])
    return [data[uid] for uid in uids if uid in data]

