
import json
import os
from datetime import datetime, timezone

from .sources_google_news import fetch_google_news_items
from .sources_pubmed import fetch_pubmed_items
from .summarize_tr import summarize_tr
from .wp_publish import wp_create_post
from .wp_terms import get_or_create_category, get_or_create_tag
from .state_store import load_state, save_state, filter_new
from .emailer import send_email
from .utils import now_utc_iso


def build_markdown(series_title, items):
    lines = []
    lines.append(f"# {series_title}\n")
    lines.append(
        "> Bu içerik otomatik derlenmiştir. Tıbbi öneri yerine geçmez; kişisel durumunuz için uzmana danışınız.\n"
    )

    news = [i for i in items if i.get("kind") == "news"]
    papers = [i for i in items if i.get("kind") == "paper"]

    if news:
        lines.append("## 🗞️ Popüler Haberler & Yazılar\n")
        for it in news[:20]:
            summ = summarize_tr(it.get("title", ""), it.get("snippet", ""), max_sentences=2)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa özet:** {summ}")
            lines.append(f"- **Kaynak:** {it.get('url','')}\n")

    if papers:
        lines.append("## 🔬 Bilimsel Yayınlar (PubMed)\n")
        for it in papers[:10]:
            summ = summarize_tr(it.get("title", ""), it.get("snippet", ""), max_sentences=1)
            lines.append(f"### {it.get('title','')}")
            lines.append(f"- **Kısa not:** {summ}")
            lines.append(f"- **PubMed:** {it.get('url','')}\n")

    lines.append("---")
    lines.append(f"_Üretim zamanı (UTC): {now_utc_iso()}_")
    return "\n".join(lines)


def build_email_summary(created_posts):
    if not created_posts:
        return (
            "ArtheraClinic – Haftalık Seri Derlemeleri\n\n"
            "Bu hafta yeni içerik bulunamadı; taslak oluşturulmadı.\n"
        )

    lines = ["ArtheraClinic – Haftalık Seri Derlemeleri", ""]
    for p in created_posts:
        lines.append(f"- {p['series_title']}")
        lines.append(f"  Taslak ID: {p['id']}")
        lines.append(f"  Link: {p['link']}")
        lines.append(f"  Eklenen yeni kaynak sayısı: {p['new_count']}")
        lines.append("")
    return "\n".join(lines)


def write_summary_file(today, body):
    os.makedirs("out", exist_ok=True)
    # Dosya adında ':' gibi karakterlerden kaçınalım
    ts = now_utc_iso().replace(":", "").replace("-", "")
    path = f"out/email_summary_{today}_{ts}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
        f.write("\n")
    return path


def main():
    # 1) Config oku
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 2) Ortam değişkenleri (GitHub Secrets'tan gelir)
    wp_url = os.environ["WP_URL"]
    wp_user = os.environ["WP_USER"]
    wp_pass = os.environ["WP_APP_PASS"]

    # ✅ BUG FIX: today burada, main scope'unda tanımlı
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 3) State yükle (tekrar engelleme)
    state = load_state()
    state["last_run_utc"] = now_utc_iso()

    # 4) WP genel ayarları
    wp_cfg = cfg["wordpress"]
    create_terms = bool(wp_cfg.get("create_missing_terms", True))

    # Parent category (Haftalık Derlemeler)
    parent_name = wp_cfg.get("parent_category_name", "Haftalık Derlemeler")
    parent_id = get_or_create_category(
        wp_url, wp_user, wp_pass, parent_name, parent_id=None, create=create_terms
    )

    created_posts = []

    # 5) Seri bazlı üretim (Bel ağrısı / Skolyoz / Omuz)
    for s in cfg["series"]:
        # 5.1 Kaynakları çek
        g_items = fetch_google_news_items(s["google_news"])
        p_items = fetch_pubmed_items(s["pubmed"])

        # 5.2 Dedup (URL bazlı)
        combined = list({it["url"]: it for it in (g_items + p_items)}.values())

        # 5.3 Tekrar engelle (global)
        fresh = filter_new(combined, state)

        if not fresh:
            print(f"[{s['key']}] Yeni içerik yok; taslak oluşturulmadı.")
            continue

        # 5.4 Kategori oluştur/çek (seri kategorisi, parent altında)
        series_cat_id = get_or_create_category(
            wp_url, wp_user, wp_pass,
            s["category_name"],
            parent_id=parent_id,
            create=create_terms
        )

        # 5.5 Tag'leri oluştur/çek
        tag_ids = []
        for t in s.get("tag_names", []):
            tid = get_or_create_tag(wp_url, wp_user, wp_pass, t, create=create_terms)
            if tid:
                tag_ids.append(tid)

        # 5.6 Başlık + içerik
        title = f"{s['title_prefix']} — Haftalık Derleme ({today})"
        md = build_markdown(title, fresh)

        # 5.7 WordPress taslak post oluştur
        post = wp_create_post(
            wp_url=wp_url,
            username=wp_user,
            app_pass=wp_pass,
            title=title,
            content=md,
            status=wp_cfg.get("status", "draft"),
            categories=[series_cat_id] if series_cat_id else None,
            tags=tag_ids if tag_ids else None
        )

        created_posts.append({
            "series": s["key"],
            "series_title": title,
            "id": post.get("id"),
            "link": post.get("link"),
            "new_count": len(fresh)
        })

        print(f"[{s['key']}] Taslak oluşturuldu:", post.get("id"), post.get("link"))

    # 6) State kaydet (tekrarları hatırlamak için)
    save_state(state)

    # 7) Mail içeriğini üret
    subject = f"ArtheraClinic Haftalık Derlemeler ({today})"
    body = build_email_summary(created_posts)

    # 8) ✅ Mail atmadan önce repo içine dosya yaz
    saved_path = write_summary_file(today, body)
    print("Summary written to:", saved_path)

    # 9) Mail gönder
    send_email(subject, body)
    print("Email sent.")


if __name__ == "__main__":
    main()
``
