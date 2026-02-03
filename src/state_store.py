
import json

STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"seen_urls": [], "last_run_utc": None}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def filter_new(items, state, max_keep=5000):
    seen = set(state.get("seen_urls", []))
    fresh = [it for it in items if it["url"] not in seen]
    for it in fresh:
        state.setdefault("seen_urls", []).append(it["url"])
    state["seen_urls"] = state["seen_urls"][-max_keep:]
    return fresh

