import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from .sources_google_news import fetch_google_news_items
from .sources_pubmed import fetch_pubmed_items
from .summarize_tr import summarize_tr
from .state_store import load_state, save_state, filter_new
from .emailer import send_email
from .utils import now_utc_iso, clean_text

# Optional sources (now expected to exist if you added files)
try:
    from .sources_medrxiv import fetch_medrxiv_items
except Exception:
    fetch_medrxiv_items = None

try:
    from .sources_cochrane import fetch_cochrane_items
except Exception:
    fetch_cochrane_items = None


def safe_ts() -> str:
    return now_utc_iso().replace(":", "").replace("-", "")

def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        if not content.endswith("\n"):
            f.write("\n")

def dedup_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup = {}
    for it in items:
        url = (it.get("url") or "").strip()
        if url:
            dedup[url] = it
    return list(dedup.values())

def series_keywords(series_cfg: Dict[str, Any]) -> List[str]:
    kws = []
    kws += series_cfg.get("google_news", {}).get("queries", [])
    kws += series_cfg.get("pubmed", {}).get("terms", [])
    out = []
    for k in kws:
        if isinstance(k, str):
            kk = k.strip().strip('"').strip("'")
            if kk:
                out.append(kk)
    seen = set()
    uniq = []
    for k in out:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            uniq.append(k)
    return uniq

def keyword_match(item: Dict[str, Any], keywords: List[str]) -> bool:
    text = (item.get("title","") + " " + item.get("snippet","")).lower()
    return any(k.lower() in text for k in keywords if k)

def count_by_kind(items: List[Dict[str, Any]]) -> Dict[str, int]:
    c = {}
    for it in items:
        k = it.get("kind", "other")
        c[k] = c.get(k, 0) + 1
    return c

def is_likely_english(text: str) -> bool:
    t = clean_text(text)
    if any(ch in t for ch in "çğıöşüÇĞİÖŞÜ"):
        return False
    return True

TITLE_MAP = {
    "low back pain": "Bel ağrısı",
    "back pain": "Bel ağrısı",
    "lumbar": "Lomber (bel bölgesi)",
    "sciatica": "Siyatik",
    "shoulder": "Omuz",
    "rotator cuff": "Rotator manşet",
    "impingement": "Sıkışma (impingement)",
    "frozen shoulder": "Donuk omuz",
    "adhesive capsulitis": "Adeziv kapsülit (donuk omuz)",
    "scoliosis": "Skolyoz",
    "rehabilitation": "Rehabilitasyon",
    "physiotherapy": "Fizyoterapi",
    "physical therapy": "Fizik tedavi / Fizyoterapi",
    "exercise therapy": "Egzersiz tedavisi",
    "exercise": "Egzersiz",
    "manual therapy": "Manuel terapi",
    "systematic review": "Sistematik derleme",
    "meta-analysis": "Meta-analiz",
    "randomized": "Randomize",
    "trial": "Klinik çalışma",
    "telehealth": "Tele-sağlık",
    "virtual reality": "Sanal gerçeklik",
    "stroke": "İnme"
}

def translate_title_tr(title: str) -> str:
    t = " " + clean_text(title).lower() + " "
    for k in sorted(TITLE_MAP.keys(), key=len, reverse=True):
        if k in t:
            t = t.replace(k, TITLE_MAP[k].lower())
    t = clean_text(t)
    if not t:
        return ""
    return t[:1].upper() + t[1:]


def build_series_markdown(series_title: str, items: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append(f"# {series_title}\n")
    lines.append("> Bu içerik otomatik derlenmiştir. Tıbbi öneri yerine geçmez; kişisel durumunuz için uzmana danışınız.\n")

    reviews   = [i for i in items if i.get("kind") == "review"]
    papers    = [i for i in items if i.get("kind") == "paper"]
    preprints = [i for i in items if i.get("kind") == "preprint"]
    news      = [i for i in items if i.get("kind") == "news"]

    if reviews:
        lines.append("## 📚 Sistematik Derlemeler (Cochrane)\n")
        for it in reviews[:10]:
            tr_sum = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=2)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Türkçe özet:** {tr_sum}")
            lines.append(f"- **Kaynak:** {it.get('url','')}\n")

    if papers:
        lines.append("## 🔬 Hakemli Makaleler (PubMed)\n")
        for it in papers[:10]:
            tr_sum = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=1)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Türkçe özet:** {tr_sum}")
            lines.append(f"- **Kaynak:** {it.get('url','')}\n")

    if preprints:
        lines.append("## 🧪 Ön Baskılar (medRxiv) — Hakem Değerlendirmesi Olmayabilir\n")
        for it in preprints[:10]:
            tr_sum = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=1)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Türkçe özet:** {tr_sum}")
            lines.append(f"- **Kaynak:** {it.get('url','')}\n")

    if news:
        lines.append("## 🗞️ Haberler & Yazılar (Google News)\n")
        for it in news[:15]:
            tr_sum = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=2)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Özet:** {tr_sum}")
            lines.append(f"- **Kaynak:** {it.get('url','')}\n")

    lines.append("---")
    lines.append(f"_Üretim zamanı (UTC): {now_utc_iso()}_")
    return "\n".join(lines)


def build_turkish_email(today: str, series_reports: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append(f"ARTHERA CLINIC – FİZYOTERAPİ GÜNDEM ÖZETİ ({today})")
    lines.append("=" * 72)
    lines.append("")
    lines.append("Bu e-posta otomatik derlenmiştir. Tıbbi öneri yerine geçmez.")
    lines.append("Kişisel durumunuz için fizyoterapistinize/hekiminize danışınız.")
    lines.append("")

    if not series_reports:
        lines.append("Bu çalıştırmada yeni içerik bulunamadı; seri dosyaları üretilmedi.")
        lines.append("")
        lines.append("Not: Detay içerikler GitHub repo içinde out/ klasöründe dosya olarak saklanır.")
        return "\n".join(lines)

    total_counts = {"review": 0, "paper": 0, "preprint": 0, "news": 0}
    for r in series_reports:
        c = r.get("counts", {})
        for k in total_counts:
            total_counts[k] += int(c.get(k, 0))

    lines.append("GENEL ÖZET (Bu çalıştırma)")
    lines.append("-" * 72)
    lines.append(f"• Cochrane (Sistematik Derleme): {total_counts['review']}")
    lines.append(f"• PubMed (Hakemli Makale):      {total_counts['paper']}")
    lines.append(f"• medRxiv (Ön Baskı/Preprint):  {total_counts['preprint']}")
    lines.append(f"• Haber & Blog (Google News):   {total_counts['news']}")
    lines.append("")
    lines.append("NOTLAR")
    lines.append("-" * 72)
    lines.append("• Cochrane sistematik derlemeler genelde yüksek kanıt düzeyi sağlar.")
    lines.append("• medRxiv içerikleri ön baskıdır; hakem değerlendirmesinden geçmemiş olabilir.")
    lines.append("• Detay içerikler GitHub repo içinde out/ klasöründe dosya olarak saklanır.")
    lines.append("")

    for r in series_reports:
        lines.append("=" * 72)
        lines.append(r["series_title"].upper())
        lines.append("=" * 72)
        lines.append(f"Yeni kaynak sayısı: {r['new_count']}")
        c = r.get("counts", {})
        lines.append(f"Dağılım: Cochrane={c.get('review',0)} | PubMed={c.get('paper',0)} | medRxiv={c.get('preprint',0)} | Haber={c.get('news',0)}")
        lines.append(f"GitHub dosyası: {r['file_path']}")
        lines.append("")

        buckets = r.get("buckets", {})

        def emit_section(title_tr, kind_key, max_n=3, extra_note=None):
            items = buckets.get(kind_key, [])
            if not items:
                return
            lines.append(title_tr)
            lines.append("-" * 72)
            if extra_note:
                lines.append(extra_note)
            for it in items[:max_n]:
                orig_title = clean_text(it.get("title",""))
                url = clean_text(it.get("url",""))
                snippet = clean_text(it.get("snippet",""))

                if kind_key in ("paper", "review", "preprint") or is_likely_english(orig_title):
                    tr_title = translate_title_tr(orig_title)
                    tr_sum = summarize_tr(orig_title, snippet, max_sentences=2)
                    lines.append(f"Orijinal Başlık: {orig_title}")
                    lines.append(f"Türkçe Başlık : {tr_title}")
                    lines.append(f"Türkçe Özet   : {tr_sum}")
                else:
                    tr_sum = summarize_tr(orig_title, snippet, max_sentences=2)
                    lines.append(f"Başlık: {orig_title}")
                    lines.append(f"Özet  : {tr_sum}")

                if url:
                    lines.append(f"Bağlantı: {url}")
                lines.append("")
            lines.append("")

        emit_section("A) COCHRANE – Sistematik Derlemeler", "review", max_n=2)
        emit_section("B) PUBMED – Hakemli Makaleler", "paper", max_n=3)
        emit_section("C) MEDRXIV – Ön Baskılar (Hakem Değerlendirmesi Olmayabilir)", "preprint", max_n=2,
                     extra_note="Uyarı: Ön baskılar klinik uygulamayı yönlendirmek için tek başına kullanılmamalıdır.")
        emit_section("D) HABER / BLOG – Gündem", "news", max_n=3)

    return "\n".join(lines)


def main():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ts = safe_ts()

    state = load_state()
    state["last_run_utc"] = now_utc_iso()

    # Global sources
    global_cfg = cfg.get("global_sources", {})

    med_items = []
    if fetch_medrxiv_items and global_cfg.get("medrxiv"):
        med_items = fetch_medrxiv_items(global_cfg.get("medrxiv", {}))
    print(f"[GLOBAL] medRxiv çekilen kayıt: {len(med_items)}")

    coch_items = []
    if fetch_cochrane_items and global_cfg.get("cochrane"):
        coch_items = fetch_cochrane_items(global_cfg.get("cochrane", {}))
    print(f"[GLOBAL] Cochrane çekilen kayıt: {len(coch_items)}")

    series_reports = []

    for s in cfg.get("series", []):
        series_key = s.get("key", "series")
        series_title = f"{s.get('title_prefix','Seri')} — Derleme ({today})"

        g_items = fetch_google_news_items(s.get("google_news", {}))
        p_items = fetch_pubmed_items(s.get("pubmed", {}))

        kws = series_keywords(s)

        med_for_series = [it for it in med_items if keyword_match(it, kws)] if (med_items and kws) else []
        coch_for_series = [it for it in coch_items if keyword_match(it, kws)] if (coch_items and kws) else []

        combined = dedup_by_url(g_items + p_items + med_for_series + coch_for_series)
        fresh = filter_new(combined, state)

        if not fresh:
            print(f"[{series_key}] Yeni içerik yok; dosya üretilmedi.")
            continue

        md = build_series_markdown(series_title, fresh)
        file_path = f"out/{series_key}/{today}_{ts}.md"
        write_text(file_path, md)
        print(f"[{series_key}] Yazıldı: {file_path}")

        buckets = {
            "review":   [i for i in fresh if i.get("kind") == "review"],
            "paper":    [i for i in fresh if i.get("kind") == "paper"],
            "preprint": [i for i in fresh if i.get("kind") == "preprint"],
            "news":     [i for i in fresh if i.get("kind") == "news"],
        }
        counts = count_by_kind(fresh)

        series_reports.append({
            "series_key": series_key,
            "series_title": series_title,
            "new_count": len(fresh),
            "counts": counts,
            "file_path": file_path,
            "buckets": buckets
        })

    save_state(state)

    subject = f"ArtheraClinic – Fizyoterapi Gündem Özeti ({today})"
    mail_text = build_turkish_email(today, series_reports)

    summary_path = f"out/email_summary/{today}_{safe_ts()}.txt"
    write_text(summary_path, mail_text)
    print("Email summary written:", summary_path)

    try:
        send_email(subject, mail_text)
        print("Email sent.")
    except Exception as e:
        print("Email failed, continuing without stopping workflow:", e)


if __name__ == "__main__":
    main()
