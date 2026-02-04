
import re
from collections import Counter
from .utils import clean_text

TR_STOP = set("""
ve veya ile ama fakat çünkü için gibi daha çok az en mı mi mu mü ya da
bir bu şu o ki olarak ise değil üzerinde arasında kadar
""".split())

EN_STOP = set("""
the a an and or but because for with without in on at from to of by as
is are was were be been being this that these those it its into than
""".split())

# Basit ücretsiz sözlük (zamanla genişletebilirsin)
GLOSSARY = {
    "low back pain": "bel ağrısı",
    "back pain": "bel ağrısı",
    "lumbar": "lomber (bel bölgesi)",
    "sciatica": "siyatik",
    "shoulder": "omuz",
    "rotator cuff": "rotator manşet",
    "impingement": "sıkışma (impingement)",
    "frozen shoulder": "donuk omuz",
    "adhesive capsulitis": "adeziv kapsülit (donuk omuz)",
    "scoliosis": "skolyoz",
    "rehabilitation": "rehabilitasyon",
    "physiotherapy": "fizyoterapi",
    "physical therapy": "fizik tedavi / fizyoterapi",
    "exercise": "egzersiz",
    "exercise therapy": "egzersiz tedavisi",
    "manual therapy": "manuel terapi",
    "stroke": "inme",
    "falls prevention": "düşme önleme",
    "pain": "ağrı",
    "function": "fonksiyon",
    "outcome": "sonuç",
    "trial": "klinik çalışma",
    "randomized": "randomize",
    "systematic review": "sistematik derleme",
    "meta-analysis": "meta-analiz",
    "telehealth": "tele-sağlık / uzaktan sağlık",
    "virtual reality": "sanal gerçeklik",
}

def _has_turkish_chars(text: str) -> bool:
    return any(ch in text for ch in "çğıöşüÇĞİÖŞÜ")

def _extract_keywords(text: str, lang: str = "en", topk: int = 6):
    text = clean_text(text).lower()
    words = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+", text)
    if lang == "tr":
        words = [w for w in words if w not in TR_STOP and len(w) > 2]
    else:
        words = [w for w in words if w not in EN_STOP and len(w) > 2]
    freq = Counter(words)
    return [w for w, _ in freq.most_common(topk)]

def _translate_phrase_simple(text: str) -> str:
    """
    Tam çeviri değil; sık geçen klinik kalıpları Türkçe karşılıklarına mapler.
    """
    t = " " + clean_text(text).lower() + " "
    # Uzun kalıpları önce değiştir
    for k in sorted(GLOSSARY.keys(), key=len, reverse=True):
        if k in t:
            t = t.replace(k, GLOSSARY[k])
    return clean_text(t)

def summarize_tr(title: str, snippet: str, max_sentences: int = 2) -> str:
    """
    - Türkçe metinse: extractive özet
    - Değilse: ücretsiz TR şablon + sözlük tabanlı 'anlamsal' özet
    """
    title = clean_text(title or "")
    snippet = clean_text(snippet or "")
    full = clean_text(f"{title}. {snippet}")

    if _has_turkish_chars(full):
        # --- Basit extractive (Türkçe) ---
        sents = re.split(r"(?<=[.!?])\s+", full)
        sents = [s.strip() for s in sents if len(s.strip()) > 30]
        if not sents:
            return snippet[:240]

        words = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+", full.lower())
        words = [w for w in words if w not in TR_STOP and len(w) > 2]
        freq = Counter(words)

        def score(sent):
            ws = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+", sent.lower())
            return sum(freq.get(w, 0) for w in ws)

        ranked = sorted(sents, key=score, reverse=True)
        return " ".join(ranked[:max_sentences])

    # --- Yabancı içerik (EN ağırlıklı) → Türkçe şablonlu özet ---
    tr_title_hint = _translate_phrase_simple(title)
    tr_snip_hint = _translate_phrase_simple(snippet)

    # Anahtar kelime çıkar + Türkçeleştir
    kws = _extract_keywords(full, lang="en", topk=6)
    kw_line = ", ".join([_translate_phrase_simple(k) for k in kws])

    # Şablonlu kısa özet
    # Amaç: mailde okunabilir, Türkçe, klinik neutral.
    parts = []
    if tr_title_hint:
        parts.append(f"Bu içerik {tr_title_hint} konusuna odaklanıyor.")
    if tr_snip_hint:
        parts.append(f"Öne çıkan başlıklar: {tr_snip_hint[:220]}.")
    if kw_line:
        parts.append(f"Anahtar kavramlar: {kw_line}.")
    return " ".join(parts).strip()
