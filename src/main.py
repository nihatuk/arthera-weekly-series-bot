
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .sources_google_news import fetch_google_news_items
from .sources_pubmed import fetch_pubmed_items
from .summarize_tr import summarize_tr
from .state_store import load_state, save_state, filter_new
from .emailer import send_email
from .utils import now_utc_iso


# --- Optional sources: medRxiv & Cochrane ---
try:
    from .sources_medrxiv import fetch_medrxiv_items  # kind="preprint"
except Exception:
    fetch_medrxiv_items = None

try:
    from .sources_cochrane import fetch_cochrane_items  # kind="review"
except Exception:
    fetch_cochrane_items = None


# ----------------------------
# Helpers: text & file outputs
# ----------------------------

def safe_ts() -> str:
    """UTC timestamp safe for filenames."""
    return now_utc_iso().replace(":", "").replace("-", "")


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        if not content.endswith("\n"):
            f.write("\n")


def normalize_url(u: str) -> str:
    return (u or "").strip()


def dedup_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for it in items:
        url = normalize_url(it.get("url", ""))
        if not url:
            continue
        dedup[url] = it
    return list(dedup.values())


def series_keywords(series_cfg: Dict[str, Any]) -> List[str]:
    """
    Create a lightweight keyword set for filtering global sources
    using series queries/terms.
    """
    kws: List[str] = []
    kws += series_cfg.get("google_news", {}).get("queries", [])
    kws += series_cfg.get("pubmed", {}).get("terms", [])
    # simple cleanup
    out = []
    for k in kws:
        if isinstance(k, str):
            kk = k.strip().strip('"').strip("'")
            if kk:
                out.append(kk)
    # de-dup while preserving order
    seen = set()
    uniq = []
    for k in out:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            uniq.append(k)
    return uniq


def keyword_match(item: Dict[str, Any], keywords: List[str]) -> bool:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    for k in keywords:
        if k.lower() in text:
            return True
    return False


def count_by_kind(items: List[Dict[str, Any]]) -> Dict[str, int]:
    c: Dict[str, int] = {}
    for it in items:
        k = it.get("kind", "other")
        c[k] = c.get(k, 0) + 1
    return c


# ----------------------------
# Output builders
# ----------------------------

def build_series_markdown(series_title: str, items: List[Dict[str, Any]]) -> str:
    """
    GitHub'da saklanacak .md dosyası için (Markdown kalabilir).
    Mailde Markdown istemediğin için, maili ayrı düz metin üretiyoruz.
    """
    lines: List[str] = []
    lines.append(f"# {series_title}\n")
    lines.append("> Bu içerik otomatik derlenmiştir. Tıbbi öneri yerine geçmez; kişisel durumunuz için uzmana danışınız.\n")

    # bucket by kind
    reviews   = [i for i in items if i.get("kind") == "review"]     # Cochrane
    papers    = [i for i in items if i.get("kind") == "paper"]      # PubMed
    preprints = [i for i in items if i.get("kind") == "preprint"]   # medRxiv
    news      = [i for i in items if i.get("kind") == "news"]       # Google News

    if reviews:
        lines.append("## 📚 Sistematik Derlemeler (Cochrane)\n")
        for it in reviews[:10]:
            summ = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=2)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa özet:** {summ}")
            lines.append(f"- **Kaynak:** {it.get('url','')}")
            if it.get("published"):
                lines.append(f"- **Tarih:** {it.get('published')}")
            lines.append("")

    if papers:
        lines.append("## 🔬 Bilimsel Yayınlar (PubMed)\n")
        for it in papers[:10]:
            summ = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=1)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa not:** {summ}")
            lines.append(f"- **Kaynak:** {it.get('url','')}")
            if it.get("published"):
                lines.append(f"- **Tarih:** {it.get('published')}")
            lines.append("")

    if preprints:
        lines.append("## 🧪 Ön Baskılar (medRxiv) — Hakem Değerlendirmesi Olmayabilir\n")
        for it in preprints[:10]:
            summ = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=1)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa not:** {summ}")
            lines.append(f"- **Kaynak:** {it.get('url','')}")
            if it.get("published"):
                lines.append(f"- **Tarih:** {it.get('published')}")
            lines.append("")

    if news:
        lines.append("## 🗞️ Popüler Haberler & Yazılar (Google News)\n")
        for it in news[:15]:
            summ = summarize_tr(it.get("title",""), it.get("snippet",""), max_sentences=2)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa özet:** {summ}")
            lines.append(f"- **Kaynak:** {it.get('url','')}")
            if it.get("published"):
                lines.append(f"- **Tarih:** {it.get('published')}")
            lines.append("")

    lines.append("---")
    lines.append(f"_Üretim zamanı (UTC): {now_utc_iso()}_")
    return "\n".join(lines)


def build_readable_email_text(today: str,
                              series_reports: List[Dict[str, Any]],
                              repo_note: str = "Detay içerikler GitHub repo içinde out/ klasöründe dosya olarak saklanır.") -> str:
    """
    Mail gövdesi: Markdown değil, okunabilir düz metin bülten.
    """
    lines: List[str] = []
    lines.append(f"ARTHERA CLINIC – SERI DERLEMELERI ({today})")
    lines.append("=" * 56)
    lines.append("")

    if not series_reports:
        lines.append("Bu çalıştırmada yeni içerik bulunamadı; seri dosyaları üretilmedi.")
        lines.append("")
        lines.append(repo_note)
        return "\n".join(lines)

    for r in series_reports:
        lines.append(f"SERİ: {r['series_title']}")
        lines.append("-" * 56)
        counts = r.get("counts", {})
        lines.append(f"Yeni kaynak sayısı : {r['new_count']}")
        lines.append(f"Dağılım            : "
                     f"Cochrane={counts.get('review',0)} | PubMed={counts.get('paper',0)} | "
                     f"medRxiv={counts.get('preprint',0)} | Haber={counts.get('news',0)}")
        lines.append(f"Dosya              : {r['file_path']}")
        lines.append("")

        # Her bölümden ilk birkaç başlık + link (mailde okunur)
        top = r.get("top_items", [])
        if top:
            lines.append("ÖNE ÇIKANLAR:")
            for it in top[:8]:
                # MD değil: basit metin
                title = it.get("title", "").strip()
                url = it.get("url", "").strip()
                label = it.get("label", "")
                lines.append(f"  • [{label}] {title}")
                if url:
                    lines.append(f"    {url}")
            lines.append("")

    lines.append(repo_note)
    return "\n".join(lines)


def pick_top_items_for_email(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mail için: en okunur / en değerli sıralama:
    1) Cochrane review
    2) PubMed paper
    3) medRxiv preprint
    4) Google News
    """
    order = {"review": 0, "paper": 1, "preprint": 2, "news": 3}
    labeled = []
    for it in items:
        kind = it.get("kind", "other")
        label = {
            "review": "COCHRANE",
            "paper": "PUBMED",
            "preprint": "MEDRXIV",
            "news": "HABER"
        }.get(kind, "DİĞER")
        labeled.append({
            "kind": kind,
            "label": label,
            "title": it.get("title", ""),
            "url": it.get("url", "")
        })
    labeled.sort(key=lambda x: order.get(x["kind"], 99))
    return labeled


# ----------------------------
# Main
# ----------------------------

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ts = safe_ts()

    # state for dedup across runs
    state = load_state()
    state["last_run_utc"] = now_utc_iso()

    # --- fetch global sources once (optional) ---
    global_cfg = cfg.get("global_sources", {})

    med_items: List[Dict[str, Any]] = []
    if fetch_medrxiv_items and global_cfg.get("medrxiv"):
        try:
            med_items = fetch_medrxiv_items(global_cfg.get("medrxiv", {}))
        except Exception as e:
            print("medRxiv fetch failed (skipping):", e)

    coch_items: List[Dict[str, Any]] = []
    if fetch_cochrane_items and global_cfg.get("cochrane"):
        try:
            coch_items = fetch_cochrane_items(global_cfg.get("cochrane", {}))
        except Exception as e:
            print("Cochrane fetch failed (skipping):", e)

    # series reports for email
    series_reports: List[Dict[str, Any]] = []

    for s in cfg.get("series", []):
        series_key = s.get("key", "series")
        series_title = f"{s.get('title_prefix','Seri')} — Derleme ({today})"

        # 1) Fetch series-specific sources
        g_items = []
        try:
            g_items = fetch_google_news_items(s.get("google_news", {}))
        except Exception as e:
            print(f"[{series_key}] Google News fetch failed (skipping):", e)

        p_items = []
        try:
            p_items = fetch_pubmed_items(s.get("pubmed", {}))
        except Exception as e:
            print(f"[{series_key}] PubMed fetch failed (skipping):", e)

        # 2) Filter global sources for this series by keywords
        kws = series_keywords(s)

        med_for_series = []
        if med_items and kws:
            med_for_series = [it for it in med_items if keyword_match(it, kws)]

        coch_for_series = []
        if coch_items and kws:
            coch_for_series = [it for it in coch_items if keyword_match(it, kws)]

        # 3) Combine + dedup + global dedup (state)
        combined = dedup_by_url(g_items + p_items + med_for_series + coch_for_series)
        fresh = filter_new(combined, state)

        if not fresh:
            print(f"[{series_key}] Yeni içerik yok; dosya üretilmedi.")
            continue

        # 4) Write series markdown to repo
        md = build_series_markdown(series_title, fresh)
        file_path = f"out/{series_key}/{today}_{ts}.md"
        write_text(file_path, md)
        print(f"[{series_key}] Yazıldı: {file_path}")

        # 5) Build report info for email
        counts = count_by_kind(fresh)
        top_items = pick_top_items_for_email(fresh)

        series_reports.append({
            "series_key": series_key,
            "series_title": series_title,
            "new_count": len(fresh),
            "counts": counts,
            "file_path": file_path,
            "top_items": top_items
        })

    # persist state even if email fails
    save_state(state)

    # Always write an email_summary txt to repo
    subject = f"ArtheraClinic Seri Derlemeleri ({today})"
    email_text = build_readable_email_text(today, series_reports)

    summary_path = f"out/email_summary/{today}_{safe_ts()}.txt"
    write_text(summary_path, email_text)
    print("Email summary written:", summary_path)

    # Send email (non-fatal)
    try:
        # Compatible with both 2-arg and 3-arg versions of send_email
        send_email(subject, email_text)
        print("Email sent.")
    except TypeError:
        # If your emailer.py supports (subject, text, html), fallback safely
        try:
            send_email(subject, email_text, None)
            print("Email sent.")
        except Exception as e:
            print("Email failed, continuing without stopping workflow:", e)
    except Exception as e:
        print("Email failed, continuing without stopping workflow:", e)


if __name__ == "__main__":
    main()
