import csv
import os
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = 20          # largement suffisant (il n'y a que 2-3 pages utiles)
SLEEP = 0.3

def proxy_url(path):
    if path.startswith("http"):
        path = path.split("ffta.fr")[-1]
    return f"{PROXY}?target={quote(path)}"

def fetch(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        return r.status_code, r.text
    except:
        return None, None

def main():
    # Chargement CSV
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    existing_details = {row.get("Detail", "").strip() for row in rows if row.get("Detail")}

    new_competitions = []
    print("🔍 Recherche des NOUVEAUX concours...")

    for page in range(1, MAX_PAGES + 1):
        status, html = fetch(f"{PROXY}?page={page}")
        if status != 200 or not html:
            print(f"   Page {page} terminée")
            break

        soup = BeautifulSoup(html, "html.parser")
        found_new = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/epreuve/" in href:
                detail_url = "https://www.ffta.fr" + href.split("/epreuve/")[-1].split("?")[0]
                detail_url = detail_url.replace("/index.php", "")
                if detail_url not in existing_details and detail_url not in new_competitions:
                    new_competitions.append(detail_url)
                    found_new += 1

        if found_new == 0:
            print(f"   Plus de nouveaux concours (page {page})")
            break

    print(f"✅ {len(new_competitions)} nouveaux concours à traiter")

    updated = 0
    for detail_url in new_competitions:
        print(f"🔍 {detail_url}")

        # === UNE SEULE REQUÊTE par concours ===
        status, html = fetch(proxy_url(detail_url))
        if status != 200 or not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Titre pour le matching
        h1 = soup.find("h1")
        titre_page = h1.get_text(strip=True).lower() if h1 else ""

        # Recherche du PDF mandat
        mandat = ""
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            text = a.get_text(strip=True).lower()
            if href.endswith(".pdf") and any(word in href or word in text for word in ["mandat", "resultat", "result", "inscription", "programme"]):
                mandat = "https://www.ffta.fr" + href if not href.startswith("http") else href
                break

        if not mandat:
            continue

        # Matching simple et rapide (titre suffit largement)
        for row in rows:
            if row.get("Detail"):
                continue
            csv_titre = row.get("Titre compétition", "").strip().lower()
            if csv_titre and csv_titre in titre_page:
                row["Detail"] = detail_url
                row["Mandat"] = mandat
                updated += 1
                print(f"   → Mandat ajouté pour {row.get('Titre compétition')} ({row.get('Date debut')})")
                break

        time.sleep(SLEEP)

    # Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"🎉 {updated} nouveaux mandats ajoutés aujourd’hui")

if __name__ == "__main__":
    main()
