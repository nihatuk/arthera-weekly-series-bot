
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
    lines.append("> Bu içerik otomatik derlenmiştir. Tıbbi öneri yerine geçmez; kişisel durumunuz için uzmana danışınız.\n")

    news = [i for i in items if i["kind"] == "news"]
    papers = [i for i in items if i["kind"] == "paper"]

    if news:
        lines.append("## 🗞️ Popüler Haberler & Yazılar\n")
        for it in news[:20]:
            summ = summarize_tr(it["title"], it["snippet"], max_sentences=2)
            lines.append(f"### {it['title']}")
            lines.append(f"- **Kısa özet:** {summ}")
            lines.append(f"- **Kaynak:** {it['url']}\n")

    if papers:
        lines.append("## 🔬 Bilimsel Yayınlar (PubMed)\n")
        for it in papers[:10]:
            summ = summarize_tr(it["title"], it["snippet"], max_sentences=1)
            lines.append(f"### {it['title']}")
            lines.append(f"- **Kısa not:** {summ}")
            lines.append(f"- **PubMed:** {it['url']}\n")

    lines.append("---")
    lines.append(f"_Üretim zamanı (UTC): {now_utc_iso()}_")
    return "\n".join(lines)

def build_email_summary(created_posts):
    if not created_posts:
        return "Bu hafta yeni içerik bulunamadı; taslak oluşturulmadı."

    lines = ["ArtheraClinic – Haftalık Seri Derlemeleri", ""]
    for p in created_posts:
        lines.append(f"- {p['series_title']}")
        lines.append(f"  Taslak ID: {p['id']}")
        lines.append(f"  Link: {p['link']}")
        lines.append(f"  Eklenen yeni kaynak sayısı: {p['new_count']}")
        lines.append("")
    return "\n".join(lines)

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    wp_url = os.environ["WP_URL"]
    wp_user = os.environ["WP_USER"]
    wp_pass = os.environ["WP_APP_PASS"]

    state = load_state()
    state["last_run_utc"] = now_utc_iso()

    wp_cfg = cfg["wordpress"]
    create_terms = bool(wp_cfg.get("create_missing_terms", True))

    # Parent category
    parent_name = wp_cfg.get("parent_category_name", "Haftalık Derlemeler")
    parent_id = get_or_create_category(wp_url, wp_user, wp_pass, parent_name, parent_id=None, create=create_terms)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    created_posts = []

    for s in cfg["series"]:
        g_items = fetch_google_news_items(s["google_news"])
        p_items = fetch_pubmed_items(s["pubmed"])
        items = list({it["url"]: it for it in (g_items + p_items)}.values())

        fresh = filter_new(items, state)
        if not fresh:
            print(f"[{s['key']}] Yeni içerik yok; taslak oluşturulmadı.")
            continue

        series_cat_id = get_or_create_category(
            wp_url, wp_user, wp_pass,
            s["category_name"],
            parent_id=parent_id,
            create=create_terms
        )

        tag_ids = []
        for t in s.get("tag_names", []):
            tid = get_or_create_tag(wp_url, wp_user, wp_pass, t, create=create_terms)
            if tid:
                tag_ids.append(tid)

        title = f"{s['title_prefix']} — Haftalık Derleme ({today})"
        md = build_markdown(title, fresh)

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

    save_state(state)

    # E-posta at (taslakların linkleriyle)
    subject = f"ArtheraClinic Haftalık Derlemeler ({today})"
    body = build_email_summary(created_posts)
    send_email(subject, body)
    print("Email sent.")

if __name__ == "__main__":
    main()

