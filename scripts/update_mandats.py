import csv
import os
import time
import requests
from urllib.parse import quote, urlparse
from bs4 import BeautifulSoup

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "60"))
SLEEP = float(os.getenv("SLEEP_S", "0.4"))

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "fr-FR,fr;q=0.9"
}

def proxy_detail(url):
    parsed = urlparse(url)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    return f"{PROXY}?target={quote(path)}"

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r.status_code, r.text
    except Exception:
        return None, None

def get_listing(page):
    url = f"{PROXY}?page={page}"
    status, html = fetch(url)

    if status != 200:
        print(f"WARN page={page} status={status}")
        return []

    soup = BeautifulSoup(html, "html.parser")

    competitions = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/epreuve/" in href:
            competitions.append("https://www.ffta.fr" + href)

    return list(set(competitions))

def extract_mandat(detail_url):
    url = proxy_detail(detail_url)

    status, html = fetch(url)

    if status != 200:
        print(f"WARN detail status={status} url={detail_url}")
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        if href.lower().endswith(".pdf") and any(kw in href.lower() or kw in text for kw in ["mandat", "resultat", "resultats", "engagement", "inscription", "programme", "convocation", "tae", "beursault", "extranet"]):
            return href if href.startswith("http") else "https://www.ffta.fr" + href

    return ""

def load_csv():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader), reader.fieldnames

def save_csv(rows, fieldnames):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

def main():
    rows, fieldnames = load_csv()

    updated = 0

    for page in range(MAX_PAGES):
        print(f"PAGE {page}")

        competitions = get_listing(page)

        if not competitions:
            break

        for detail in competitions:
            mandat = extract_mandat(detail)

            if not mandat:
                continue

            for row in rows:
                if row.get("Detail") == detail and not row.get("Mandat"):
                    row["Mandat"] = mandat
                    updated += 1
                    print(f"AJOUT : {row.get('Titre compétition')} ({row.get('Date debut')}) → {mandat}")

        time.sleep(SLEEP)

    save_csv(rows, fieldnames)

    print("Mandats ajoutés :", updated)

if __name__ == "__main__":
    main()
