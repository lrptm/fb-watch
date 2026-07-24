import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from xml.sax.saxutils import escape as xml_escape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "seen.json")
RSS_FILE = os.path.join(SCRIPT_DIR, "fb_feed.xml")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"seen": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def fetch_catalog():
    url = "https://a.4cdn.org/v/catalog.json"
    req = Request(url, headers={"User-Agent": "FBWatch/1.0 (github.com/lrptm/fb-watch)"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
            return json.loads(data)
    except Exception as e:
        print(f"Failed to fetch catalog: {e}")
        return []

KEYWORDS = [
    "football", "soccer",
    "fifa", "ea fc", "efootball", "madden",
    "football manager", "fm26", "fm25", "fm24",
    "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
    "champions league", "europa league", "conference league",
    "world cup", "euros", "copa america", "nations league",
    "que miras bobo", "argentina", "spain",
    "messi", "ronaldo", "mbappe", "haaland", "neymar",
    "bellingham", "vinicius", "salah", "de bruyne",
    "manchester city", "manchester united", "chelsea", "liverpool",
    "tottenham", "newcastle", "west ham", "aston villa",
    "barcelona", "real madrid", "atletico", "bayern munich", "psg",
    "inter milan", "ac milan", "juventus", "napoli",
    "transfer", "transfer window", "signing",
    "penalty", "offside", "relegation",
    "el clasico", "der klassiker", "north london derby",
    "mls", "nfl", "super bowl",
    "copa libertadores", "afc champions league",
]

def is_football_thread(thread):
    com = thread.get("com", "").lower()
    sub = thread.get("sub", "").lower()
    text = com + " " + sub
    return any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in KEYWORDS)

def check_board():
    state = load_state()
    seen = set(state.get("seen", []))
    catalog = fetch_catalog()
    new_threads = []

    for page in catalog:
        for thread in page.get("threads", []):
            no = thread.get("no", 0)
            if no in seen:
                continue
            if is_football_thread(thread):
                sub = thread.get("sub", "(no subject)")
                com = thread.get("com", "")
                seen.add(no)
                new_threads.append({
                    "id": no,
                    "title": sub[:200] if sub else "(no subject)",
                    "url": f"https://boards.4chan.org/v/thread/{no}/",
                    "time": int(thread.get("time", time.time())),
                    "preview": com[:500] if com else "",
                })

    if new_threads:
        save_state({"seen": list(seen)})
    generate_rss(new_threads)
    return new_threads

def generate_rss(new_threads):
    existing = ""
    if os.path.exists(RSS_FILE):
        with open(RSS_FILE, "r") as f:
            existing = f.read()

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []

    for t in new_threads:
        pub_date = datetime.fromtimestamp(t["time"], tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        desc = xml_escape(t["preview"][:500]) if t["preview"] else "New football thread"
        items.append(f"""    <item>
      <title>{xml_escape(t["title"])}</title>
      <link>{xml_escape(t["url"])}</link>
      <guid isPermaLink="true">{xml_escape(t["url"])}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{desc}</description>
    </item>""")

    if not new_threads:
        if existing:
            return
        items.append("""    <item>
      <title>No threads yet</title>
      <link>https://boards.4chan.org/sp/</link>
      <guid>fb-watch-start</guid>
      <pubDate>{now}</pubDate>
      <description>No football threads found yet. The feed will update when a new thread is detected.</description>
    </item>""".replace("{now}", now))

    all_items = "\n".join(items)
    repo_url = "https://raw.githubusercontent.com/lrptm/fb-watch/main/fb_feed.xml"

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Football Threads on /v/</title>
      <link>https://boards.4chan.org/v/</link>
      <description>New football/soccer threads on 4chan's /v/ board, checked every 15 minutes</description>
    <language>en-us</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{repo_url}" rel="self" type="application/rss+xml"/>
{all_items}
  </channel>
</rss>"""

    with open(RSS_FILE, "w") as f:
        f.write(feed)

if __name__ == "__main__":
    try:
        new = check_board()
        if new:
            print(f"Found {len(new)} new football thread(s):")
            for t in new:
                print(f"  {t['title']} - {t['url']}")
        else:
            print("No new football threads found.")
    except Exception as e:
        print(f"Error: {e}")
