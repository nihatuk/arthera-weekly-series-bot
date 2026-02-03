
import json
import os
from datetime import datetime, timezone
from .sources_google_news import fetch_google_news_items
from .sources_pubmed import fetch_pubmed_items
from .summarize_tr import summarize_tr
from .state_store import load_state, save_state, filter_new
from .emailer import send_email
from .utils import now_utc_iso

def build_series_markdown(series_title, items):
    lines = []
    lines.append(f"# {series_title}\n")
    lines.append("> Bu içerik otomatik derlenmiştir. Tıbbi öneri yerine geçmez; kişisel durumunuz için uzmana danışınız.\n")
    news = [i for i in items if i.get("kind") == "news"]
    papers = [i for i in items if i.get("kind") == "paper"]
    if news:
        lines.append("## 🗞️ Popüler Haberler & Yazılar (Google News)\n")
        for it in news[:20]:
            summ = summarize_tr(it.get("title", ""), it.get("snippet", ""), max_sentences=2)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa özet:** {summ}")
            lines.append(f"- **Kaynak:** {it.get('url','')}")
            if it.get("published"):
                lines.append(f"- **Tarih:** {it.get('published')}")
            lines.append("")
    if papers:
        lines.append("## 🔬 Bilimsel Yayınlar (PubMed)\n")
        for it in papers[:10]:
            summ = summarize_tr(it.get("title", ""), it.get("snippet", ""), max_sentences=1)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa not:** {summ}")
            lines.append(f"- **PubMed:** {it.get('url','')}")
            if it.get("published"):
                lines.append(f"- **Tarih:** {it.get('published')}")
            lines.append("")
    lines.append("---")
    lines.append(f"_Üretim zamanı (UTC): {now_utc_iso()}_")
    return "\n".join(lines)


def build_email_summary(series_results, today):
    lines = []
    lines.append(f"ArtheraClinic – Seri Derlemeleri ({today})")
    lines.append("=" * 45)
    lines.append("")

    if not series_results:
        lines.append("Bu çalıştırmada yeni içerik bulunamadı.")
        lines.append("")
        lines.append("GitHub çıktısı: out/email_summary/ klasöründe.")
        return "\n".join(lines)

    for r in series_results:
        lines.append(f"[{r['series_key']}] {r['series_title']}")
        lines.append(f"  • Yeni kaynak sayısı : {r['new_count']}")
        lines.append(f"  • Dosya yolu         : {r['file_path']}")
        lines.append("")
    lines.append("Not: Detay içerikler GitHub repo içinde .md dosyaları olarak saklanır.")
    return "\n".join(lines)

def safe_ts():
    return now_utc_iso().replace(":", "").replace("-", "")

def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Tarih (UTC bazlı)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # State (tekrar engelleme)
    state = load_state()
    state["last_run_utc"] = now_utc_iso()
    series_results = []
    for s in cfg["series"]:
        # 1) Topla
        g_items = fetch_google_news_items(s["google_news"])
        p_items = fetch_pubmed_items(s["pubmed"])
        combined = list({it["url"]: it for it in (g_items + p_items)}.values())
        # 2) Tekrar engelle
        fresh = filter_new(combined, state)
        if not fresh:
            print(f"[{s['key']}] Yeni içerik yok; dosya üretilmedi.")
            continue
        # 3) Seri başlığı + markdown üret
        series_title = f"{s['title_prefix']} — Derleme ({today})"
        md = build_series_markdown(series_title, fresh)
        # 4) Dosyaya yaz (GitHub repo içinde saklanacak)
        ts = safe_ts()
        file_path = f"out/{s['key']}/{today}_{ts}.md"
        write_text(file_path, md)
        series_results.append({
            "series_key": s["key"],
            "series_title": series_title,
            "new_count": len(fresh),
            "file_path": file_path
        })
        print(f"[{s['key']}] Yazıldı:", file_path)
    # 5) State kaydet
    save_state(state)

    # 6) Mail içeriğini üret (önce subject/body TANIMLA)
    subject = f"ArtheraClinic Seri Derlemeleri ({today})"
    body = build_email_summary(series_results, today)

    # 7) Mail atmadan önce summary dosyasını repo içine yaz
    summary_path = f"out/email_summary/{today}_{safe_ts()}.txt"
    write_text(summary_path, body)
    print("Email summary written:", summary_path)

    # 8) Mail gönder (başarısız olsa bile workflow düşmesin)
    try:
        send_email(subject, body)
        print("Email sent.")
    except Exception as e:
        print("Email failed, continuing without stopping workflow:", e)

if __name__ == "__main__":
    main()
