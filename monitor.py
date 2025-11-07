import os, json, time, requests, xml.etree.ElementTree as ET
from html import unescape
import re

SITEMAP_INDEX = "https://www.chromehearts.com/sitemap_index.xml"
STATE_FILE = "known_urls.json"

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TO    = os.getenv("LINE_USER_ID")

def fetch_text(url, timeout=20):
    r = requests.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def fetch_xml_root(url):
    return ET.fromstring(fetch_text(url))

def sitemap_urls(index_root):
    ns = {"sm":"http://www.sitemaps.org/schemas/sitemap/0.9"}
    for loc in index_root.findall(".//sm:sitemap/sm:loc", ns):
        yield loc.text.strip()

def urls_in_sitemap(sitemap_url):
    ns = {"sm":"http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = fetch_xml_root(sitemap_url)
    for loc in root.findall(".//sm:url/sm:loc", ns):
        yield loc.text.strip()

def load_state():
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_state(urls):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(urls)), f, ensure_ascii=False, indent=2)

def send_line(text):
    if not (LINE_TOKEN and LINE_TO):
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type":"application/json",
               "Authorization": f"Bearer {LINE_TOKEN}"}
    body = {"to": LINE_TO, "messages": [{"type":"text","text": text}]}
    requests.post(url, headers=headers, data=json.dumps(body), timeout=15)

def extract_title(html):
    m = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if not m:
        m = re.search(r"<title>(.*?)</title>", html, re.I|re.S)
    if not m:
        return None
    title = unescape(m.group(1)).strip()
    return re.sub(r"\s+", " ", title)[:80]

def main():
    known = load_state()

    # 初回は既存URLを学習だけして「通知しない」安全モード
    first_run = len(known) == 0

    index = fetch_xml_root(SITEMAP_INDEX)
    targets = [sm for sm in sitemap_urls(index)
               if any(k in sm.lower() for k in ["product", "products", "sitemap"])]

    current = set()
    for sm in targets:
        try:
            for u in urls_in_sitemap(sm):
                if "/product" in u.lower() or "/products/" in u.lower() or u.lower().endswith(".html"):
                    current.add(u)
        except Exception:
            continue

    new_urls = sorted(list(current - known))
    save_state(current or known)

    if first_run or not new_urls:
        return  # 初回は通知せず終了／変化なし

    previews = []
    for u in new_urls[:3]:
        try:
            title = extract_title(fetch_text(u, timeout=12))
            previews.append(f"- {title}\n{u}" if title else f"- {u}")
            time.sleep(0.5)
        except Exception:
            previews.append(f"- {u}")

    remain = len(new_urls) - len(previews)
    header = "🎉 Chrome Hearts 公式に新商品URLを検知"
    footer = f"\n…ほか {remain} 件" if remain > 0 else ""
    send_line(header + "\n" + "\n".join(previews) + footer)

if __name__ == "__main__":
    main()
