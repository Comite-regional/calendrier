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
PDF_KEYWORDS = ["mandat", "resultat", "resultats", "result", "engagement", "inscription", "inscriptions", "programme", "convocation"]

def proxy_url(path_or_full):
    """Transforme n'importe quelle URL FFTA en requête proxy"""
    if path_or_full.startswith("http"):
        path = path_or_full.split("ffta.fr")[-1]
    else:
        path = path_or_full
    return f"{PROXY_BASE}?target={quote(path)}"

def fetch(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20)
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

def is_pays_loire(row):
    dep = row.get("Departement", "").strip()
    if dep in PAYS_LOIRE_DEPS:
        return True
    ville = (row.get("Ville compétition") or row.get("Ville") or "").lower()
    return any(kw in ville for kw in ["nantes", "angers", "le mans", "laval", "roche sur yon", "saumur", "cholet", "st nazaire"])

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

    # Chargement CSV
    if not os.path.exists(CSV_PATH):
        print(f"ERREUR : {CSV_PATH} introuvable")
        return

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # URL de base filtrée Pays de la Loire (année 2026)
    base_listing = (
        "/competitions?search=&start=2026-03-17&end=2027-03-17"
        "&dep%5B0%5D=44&dep%5B1%5D=49&dep%5B2%5D=53&dep%5B3%5D=72&dep%5B4%5D=85"
        "&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC"
    )

    # 1. Collecter les URLs de détail depuis le listing filtré
    seen_urls = set()
    for page in range(1, MAX_PAGES + 1):
        listing_url = f"{base_listing}&page={page}"
        print(f"Scan listing page {page} : {listing_url}")
        html = fetch(proxy_url(listing_url))
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        added_this_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/epreuve/" not in href:
                continue
            detail_path = href.split("/epreuve/")[-1].split("?")[0]
            detail_url = f"https://www.ffta.fr/epreuve/{detail_path}"
            detail_url = detail_url.replace("/index.php", "")
            if detail_url not in seen_urls:
                seen_urls.add(detail_url)
                added_this_page += 1

        print(f"  → {added_this_page} URLs extraites cette page")

        if added_this_page == 0:
            break
        time.sleep(SLEEP)

    print(f"Total URLs Pays de la Loire détectées : {len(seen_urls)}")

    # 2. Traiter chaque URL (nouveaux + anciens sans mandat)
    for detail_url in seen_urls:
        print(f"Traitement {detail_url}")

        html = fetch(proxy_url(detail_url))
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text().lower()

        # Confirmation rapide région (optionnel mais utile)
        if not any(kw in page_text for kw in ["pays de la loire", "cr12", "comite regional des pays de la loire"]):
            print("  → Non Pays de la Loire → skip")
            continue

        mandat = extract_mandat_from_html(html)
        if not mandat:
            print("  → Aucun PDF mandat trouvé")
            continue

        # Matching avec lignes CSV
        matched = False
        titre_page = ""
        h1 = soup.find("h1")
        if h1:
            titre_page = h1.get_text(strip=True).lower()

        date_mentions = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', page_text)

        for row in rows:
            if not is_future(row) or not is_pays_loire(row):
                continue
            if row.get("Mandat"):
                continue  # déjà rempli

            csv_titre = row.get("Titre compétition", "").strip().lower()
            csv_date_debut = row.get("Date debut", "").strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville", "")).strip().lower()

            score = 0
            if csv_titre and csv_titre in titre_page:
                score += 4
            if csv_date_debut and csv_date_debut in date_mentions:
                score += 3
            if csv_ville and csv_ville in page_text:
                score += 2

            if score >= 4 or (row.get("Detail") == detail_url):
                row["Detail"] = detail_url
                row["Mandat"] = mandat
                updated += 1
                print(f"   → AJOUTÉ (score {score}) : {row.get('Titre compétition')} → {mandat}")
                matched = True
                break

        if not matched:
            print("  → Pas de matching trouvé dans le CSV")

        time.sleep(SLEEP)

    # Sauvegarde
    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV sauvegardé - {updated} mandats ajoutés")
    else:
        print("Aucun nouveau mandat ajouté aujourd'hui")

    print("Fin du script")

if __name__ == "__main__":
    main()
