
import re
import time
import hashlib
from urllib.parse import urlencode

def now_utc_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def stable_id(*parts: str) -> str:
    raw = "||".join([p or "" for p in parts])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def build_query_params(params: dict) -> str:
    return urlencode(params, safe=":+\"")

