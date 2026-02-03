
import re
from collections import Counter
from .utils import clean_text

TR_STOP = set("""
ve veya ile ama fakat çünkü için gibi daha çok az en mı mi mu mü ya da
bir bu şu o ki olarak ise değil üzerinde arasında kadar
""".split())

def summarize_tr(title: str, snippet: str, max_sentences: int = 2) -> str:
    text = clean_text(f"{title}. {snippet}")
    sents = re.split(r"(?<=[.!?])\s+", text)
    sents = [s.strip() for s in sents if len(s.strip()) > 30]
    if not sents:
        return clean_text(snippet)[:240]

    words = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+", text.lower())
    words = [w for w in words if w not in TR_STOP and len(w) > 2]
    freq = Counter(words)

    def score(sent):
        ws = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+", sent.lower())
        return sum(freq.get(w, 0) for w in ws)

    ranked = sorted(sents, key=score, reverse=True)
    return " ".join(ranked[:max_sentences])

