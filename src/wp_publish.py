
import base64
import requests

def wp_create_post(wp_url, username, app_pass, title, content, status="draft", categories=None, tags=None):
    api = wp_url.rstrip("/") + "/wp-json/wp/v2/posts"
    token = base64.b64encode(f"{username}:{app_pass}".encode("utf-8")).decode("utf-8")
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    payload = {"title": title, "content": content, "status": status}
    if categories:
        payload["categories"] = categories
    if tags:
        payload["tags"] = tags

    r = requests.post(api, json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"WP post create failed: {r.status_code} {r.text}")
    return r.json()

