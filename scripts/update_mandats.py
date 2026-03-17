import csv
import os
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import datetime
import re

# Configuration via variables d'environnement (comme dans ton workflow)
CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY_BASE = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "6"))          # 2-4 pages suffisent généralement
SLEEP = float(os.getenv("SLEEP_S", "0.5"))

TODAY = datetime.date.today()

# Départements Pays de la Loire
PAYS_LOIRE_DEPS = {"44", "49", "53", "72", "85"}

# Mots-clés pour détecter un PDF pertinent
PDF_KEYWORDS = [
    "mandat", "resultat", "resultats", "result", "engagement",
    "inscription", "inscriptions", "programme", "convocation"
]

# Mots-clés pour identifier un concours Pays de la Loire dans le listing
PL_KEYWORDS = [
    "44", "49", "53", "72", "85",
    "loire atlantique", "maine et loire", "mayenne", "sarthe", "vendée",
    "pays de la loire", "cr12", "comite regional des pays de la loire",
    "nantes", "angers", "le mans", "laval", "la roche sur yon",
    "saumur", "cholet", "st nazaire", "fontenay le comte"
]

def proxy_url(path):
    """Transforme un path relatif en requête proxy"""
    if not path.startswith("/"):
        path = "/" + path
    return f"{PROXY_BASE}?target={quote(path)}"

def fetch(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"  → Erreur HTTP {r.status_code} sur {url}")
        return None
    except Exception as e:
        print(f"  → Exception fetch {url} : {e}")
        return None

def is_future(row):
    debut_str = row.get("Date debut", "").strip()
    if not debut_str:
        return False
    try:
        d, m, y = map(int, debut_str.split('/'))
        return datetime.date(y, m, d) >= TODAY
    except:
        return False

def extract_mandat_from_html(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        if href.endswith(".pdf"):
            if any(kw in href or kw in text for kw in PDF_KEYWORDS):
                if not href.startswith("http"):
                    href = "https://www.ffta.fr" + href
                return href
    return ""

def main():
    print(f"Script démarré - Date actuelle : {TODAY}")

    if not os.path.exists(CSV_PATH):
        print(f"ERREUR : {CSV_PATH} introuvable")
        return

    # Chargement CSV
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # 1. Scanner le listing national (sans params complexes)
    seen_urls = set()
    for page in range(1, MAX_PAGES + 1):
        listing_path = f"/competitions?page={page}"
        print(f"Scan listing page {page} : {listing_path}")
        html = fetch(proxy_url(listing_path))
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        added_this_page = 0

        # On cherche dans les conteneurs probables (à adapter si structure change)
        for container in soup.find_all(['li', 'div', 'article', 'tr', 'td']):
            a = container.find("a", href=True)
            if not a or "/epreuve/" not in a["href"]:
                continue

            line_text = container.get_text(" ", strip=True).lower()
            if not any(kw in line_text for kw in PL_KEYWORDS):
                continue

            detail_path = a["href"].split("/epreuve/")[-1].split("?")[0]
            detail_url = f"https://www.ffta.fr/epreuve/{detail_path}"
            detail_url = detail_url.replace("/index.php", "")

            if detail_url not in seen_urls:
                seen_urls.add(detail_url)
                added_this_page += 1

        print(f"  → {added_this_page} candidats Pays de la Loire détectés cette page")

        if added_this_page == 0 and page > 1:
            print("  → Arrêt : plus de nouveaux candidats")
            break

        time.sleep(SLEEP)

    print(f"Total URLs candidates Pays de la Loire : {len(seen_urls)}")

    # 2. Traiter chaque URL candidate
    for detail_url in seen_urls:
        print(f"Traitement {detail_url}")

        html = fetch(proxy_url(detail_url))
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text().lower()

        # Confirmation région (plus fiable)
        if not any(kw in page_text for kw in ["pays de la loire", "cr12", "comite regional des pays de la loire"]):
            print("  → Non Pays de la Loire → ignoré")
            continue

        mandat = extract_mandat_from_html(html)
        if not mandat:
            print("  → Aucun PDF pertinent trouvé")
            continue

        # Matching avec le CSV
        matched = False
        titre_page = ""
        h1 = soup.find("h1")
        if h1:
            titre_page = h1.get_text(strip=True).lower()

        date_mentions = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', page_text)

        for row in rows:
            if not is_future(row):
                continue

            csv_titre = row.get("Titre compétition", "").strip().lower()
            csv_date = row.get("Date debut", "").strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville") or "").strip().lower()

            score = 0
            if csv_titre and csv_titre in titre_page:
                score += 4
            if csv_date and csv_date in date_mentions:
                score += 3
            if csv_ville and csv_ville in page_text:
                score += 2

            if score >= 4 or row.get("Detail") == detail_url:
                if not row.get("Mandat"):
                    row["Detail"] = detail_url
                    row["Mandat"] = mandat
                    updated += 1
                    print(f"   → AJOUTÉ (score {score}) : {row.get('Titre compétition')} → {mandat}")
                    matched = True
                break

        if not matched:
            print("  → Pas de correspondance trouvée dans le CSV")

        time.sleep(SLEEP)

    # Sauvegarde si modifications
    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV mis à jour – {updated} mandats ajoutés")
    else:
        print("Aucun nouveau mandat ajouté aujourd'hui")

    print("Fin du script")

if __name__ == "__main__":
    main()
