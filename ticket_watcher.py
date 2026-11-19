"""
Ticket release watcher: Avengers: Doomsday in Chennai.
Polls showtime endpoints, detects NEW sessions, alerts via Telegram.

Setup:
  pip install requests
  export TG_TOKEN="123:abc"      # from @BotFather
  export TG_CHAT_ID="987654321"  # message your bot, then open
                                 # https://api.telegram.org/bot<TOKEN>/getUpdates
Run:
  python ticket_watcher.py --demo   # tests Telegram only
  python ticket_watcher.py          # starts watching
"""
import json, os, random, sys, time
import requests

MOVIE = "avengers"  # lowercase substring matched against titles
SCREEN_KEYWORDS = []  # e.g. ["audi 3", "luxe", "imax"]; empty = any screen

# One entry per theatre. Fill url/headers/body from browser DevTools:
#   open the PVR INOX site -> pick the theatre -> Network tab (Fetch/XHR)
#   -> find the request that returns showtimes -> right click -> Copy as cURL.
WATCHES = [
    {
        "name": "Phoenix Marketcity Velachery (PVR)",
        "method": "POST",
        "url": "PASTE_SHOWTIME_URL_HERE",
        "headers": {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        "body": {},  # paste the JSON payload (theatre id, city, date)
    },
    {
        "name": "Marina Mall OMR (INOX)",
        "method": "POST",
        "url": "PASTE_SHOWTIME_URL_HERE",
        "headers": {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        "body": {},
    },
    {
        "name": "Palazzo Vadapalani (PVR)",
        "method": "POST",
        "url": "PASTE_SHOWTIME_URL_HERE",
        "headers": {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        "body": {},
    },
]

POLL_SECONDS = (60, 120)  # random interval range, keeps traffic low
STATE_FILE = "seen_sessions.json"
TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")


def notify(text):
    print("[ALERT]", text)
    if not (TG_TOKEN and TG_CHAT_ID):
        print("(Telegram not configured)")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text}, timeout=15,
        )
    except requests.RequestException as e:
        print("Telegram error:", e)


def walk(node):
    """Yield every dict in a nested JSON structure."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def extract_sessions(data):
    """
    Schema-agnostic first pass: find the smallest dicts that mention the movie,
    and treat each as a session. Replace with exact parsing once you've seen
    the real response (e.g. data['movies'][i]['sessions']).
    Returns {session_key: raw_text}.
    """
    found = {}
    for d in walk(data):
        flat = json.dumps(d, sort_keys=True).lower()
        if MOVIE in flat and len(flat) < 3000:
            if SCREEN_KEYWORDS and not any(k in flat for k in SCREEN_KEYWORDS):
                continue
            found[flat] = flat
    return found


def fetch(watch):
    r = requests.request(
        watch["method"], watch["url"], headers=watch["headers"],
        json=watch["body"] if watch["method"] == "POST" else None,
        params=None if watch["method"] == "POST" else watch["body"], timeout=20,
    )
    if r.status_code in (403, 429):
        raise RuntimeError(f"Blocked ({r.status_code}). Slow down or use Playwright.")
    r.raise_for_status()
    return r.json()


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def check(watch, state):
    if "PASTE_" in watch["url"]:
        return
    sessions = extract_sessions(fetch(watch))
    seen = set(state.get(watch["name"], []))
    new = [k for k in sessions if k not in seen]
    first_run = watch["name"] not in state
    if new and not first_run:
        notify(
            f"🎬 Tickets open: Avengers: Doomsday\n{watch['name']}\n"
            f"{len(new)} new show(s) detected. Book now!"
        )
    elif new and first_run:
        notify(f"👀 Already listed at {watch['name']} ({len(new)} shows).")
    state[watch["name"]] = list(seen | set(sessions))


def main():
    if "--demo" in sys.argv:
        notify("✅ Watcher test: Telegram works.")
        return
    state = load_state()
    if "--once" in sys.argv:
        for w in WATCHES:
            try:
                check(w, state)
            except Exception as e:
                print(f"{w['name']}: {e}")
        save_state(state)
        return
    while True:
        for w in WATCHES:
            try:
                check(w, state)
                save_state(state)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] {w['name']}: {e}")
        time.sleep(random.uniform(*POLL_SECONDS))


if __name__ == "__main__":
    main()
