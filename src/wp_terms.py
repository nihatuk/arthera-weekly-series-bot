
import base64
import requests

def _headers(user, app_pass):
    token = base64.b64encode(f"{user}:{app_pass}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}

def get_or_create_category(wp_url, user, app_pass, name, parent_id=None, create=True):
    api = wp_url.rstrip("/") + "/wp-json/wp/v2/categories"
    h = _headers(user, app_pass)

    r = requests.get(api, params={"search": name, "per_page": 100}, headers=h, timeout=30)
    r.raise_for_status()
    for item in r.json():
        if item.get("name", "").strip().lower() == name.strip().lower():
            return item["id"]

    if not create:
        return None

    payload = {"name": name}
    if parent_id:
        payload["parent"] = parent_id

    r2 = requests.post(api, json=payload, headers=h, timeout=30)
    if r2.status_code not in (200, 201):
        raise RuntimeError(f"Category create failed: {r2.status_code} {r2.text}")
    return r2.json()["id"]

def get_or_create_tag(wp_url, user, app_pass, name, create=True):
    api = wp_url.rstrip("/") + "/wp-json/wp/v2/tags"
    h = _headers(user, app_pass)

    r = requests.get(api, params={"search": name, "per_page": 100}, headers=h, timeout=30)
    r.raise_for_status()
    for item in r.json():
        if item.get("name", "").strip().lower() == name.strip().lower():
            return item["id"]

    if not create:
        return None

    r2 = requests.post(api, json={"name": name}, headers=h, timeout=30)
    if r2.status_code not in (200, 201):
        raise RuntimeError(f"Tag create failed: {r2.status_code} {r2.text}")
    return r2.json()["id"]

