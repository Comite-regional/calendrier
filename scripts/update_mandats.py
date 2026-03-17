import csv
import os
import time
import requests
import datetime
from urllib.parse import quote, urlparse
from bs4 import BeautifulSoup

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "100"))      # sécurité
SLEEP = float(os.getenv("SLEEP_S", "0.3"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9"
}

TODAY = datetime.date.today()

def proxy_url(path):
    """Proxy pour listing ou détail"""
    if path.startswith("http"):
        path = urlparse(path).path
    return f"{PROXY}?target={quote(path)}"

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        return r.status_code, r.text
    except:
        return None, None

def get_new_competitions(existing_details):
    """Récupère UNIQUEMENT les nouveaux concours (pas déjà dans le CSV)"""
    new_details = []
    for page in range(1, MAX_PAGES + 1):
        print(f"📄 Scan page {page}...")
        url = f"{PROXY}?page={page}"
        status, html = fetch(url)
        if status != 200 or not html:
            print(f"   → fin des pages")
            break

        soup = BeautifulSoup(html, "html.parser")
        found_on_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/epreuve/" in href:
                # Normalise (gère /index.php/epreuve/ ou /epreuve/)
                full = "https://www.ffta.fr" + href.split("/epreuve/")[-1].split("?")[0]
                full = full.replace("/index.php", "")
                if full not in existing_details:
                    new_details.append(full)
                    found_on_page += 1

        if found_on_page == 0:
            print(f"   → plus de nouveaux concours")
            break

        time.sleep(SLEEP)

    print(f"✅ {len(new_details)} nouveaux concours trouvés")
    return new_details

def extract_mandat(detail_url):
    """Cherche le PDF mandat sur la page détail"""
    url = proxy_url(detail_url)
    status, html = fetch(url)
    if status != 200:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        if href.endswith(".pdf") and any(k in href or k in text for k in ["mandat", "resultat", "result", "inscription", "programme"]):
            if not href.startswith("http"):
                href = "https://www.ffta.fr" + href
            return href
    return ""

def main():
    # Chargement CSV
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Ensemble des Detail déjà connus
    existing_details = {row.get("Detail", "").strip() for row in rows if row.get("Detail")}

    # Récupération des NOUVEAUX concours uniquement
    new_competitions = get_new_competitions(existing_details)

    updated = 0
    for detail_url in new_competitions:
        print(f"🔍 Traitement {detail_url}")

        mandat = extract_mandat(detail_url)
        if not mandat:
            continue  # pas encore de mandat déposé

        # Matching avec le CSV (titre + date)
        matched = False
        for row in rows:
            if row.get("Detail") == detail_url:
                continue
            if row.get("Mandat"):
                continue

            csv_titre = row.get("Titre compétition", "").strip().lower()
            csv_date = row.get("Date debut", "").strip()

            # On récupère le titre de la page pour matcher
            _, html = fetch(proxy_url(detail_url))
            soup = BeautifulSoup(html, "html.parser")
            titre_page = soup.find("h1")
            titre_page = titre_page.get_text(strip=True).lower() if titre_page else ""

            if csv_titre in titre_page and csv_date in html:
                row["Detail"] = detail_url
                row["Mandat"] = mandat
                updated += 1
                print(f"   → Mandat ajouté : {mandat}")
                matched = True
                break

        time.sleep(SLEEP)

    # Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"🎉 FIN - {updated} nouveaux mandats ajoutés aujourd'hui")

if __name__ == "__main__":
    main()
