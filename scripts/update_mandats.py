import csv
import os
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import datetime
import re

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY_BASE = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "8"))  # augmenté pour couvrir plus
SLEEP = float(os.getenv("SLEEP_S", "0.6"))

TODAY = datetime.date.today()

PAYS_LOIRE_DEPS = {"44", "49", "53", "72", "85"}

# Mots-clés élargis pour détecter PL dans le listing
PL_KEYWORDS = [
    "44", "49", "53", "72", "85",
    "loire atlantique", "maine et loire", "mayenne", "sarthe", "vendée",
    "pays de la loire", "cr12", "comite regional des pays de la loire",
    "nantes", "angers", "le mans", "laval", "la roche sur yon",
    "saumur", "cholet", "st nazaire", "fontenay le comte",
    "carquefou", "fleche", "la fleche", "fleche pictave", "erdre",
    "beursault", "tae", "championnat departemental", "concours"
]

PDF_KEYWORDS = [
    "mandat", "resultat", "resultats", "result", "engagement",
    "inscription", "inscriptions", "programme", "convocation",
    "tae", "beursault", "exterieur"
]

def proxy_url(target_path):
    if not target_path.startswith("/"):
        target_path = "/" + target_path
    return f"{PROXY_BASE}?target={quote(target_path)}"

def fetch(target_path):
    url = proxy_url(target_path)
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"Erreur {r.status_code} sur {target_path}")
        return None
    except Exception as e:
        print(f"Exception sur {target_path} : {e}")
        return None

def extract_mandat(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        if href.endswith(".pdf") and any(kw in href or kw in text for kw in PDF_KEYWORDS):
            if not href.startswith("http"):
                href = "https://www.ffta.fr" + href
            return href
    return ""

def is_future(row):
    debut = row.get("Date debut", "").strip()
    if not debut:
        return False
    try:
        d, m, y = map(int, debut.split('/'))
        return datetime.date(y, m, d) >= TODAY
    except:
        return False

def main():
    print(f"Script démarré – {TODAY}")

    if not os.path.exists(CSV_PATH):
        print(f"ERREUR : {CSV_PATH} introuvable")
        return

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # ────────────────────────────────────────────────
    # 1. Re-vérification systématique des lignes déjà connues sans mandat
    # ────────────────────────────────────────────────
    print("\nRe-vérification des lignes futures sans mandat...")
    for row in rows:
        if row.get("Mandat") or not row.get("Detail"):
            continue
        if not is_future(row):
            continue

        detail_url = row["Detail"]
        detail_path = detail_url.replace("https://www.ffta.fr", "")
        if not detail_path.startswith("/epreuve/"):
            continue

        print(f"  Re-check {detail_path} → {row.get('Titre compétition')}")
        html = fetch(detail_path)
        if html:
            mandat = extract_mandat(html)
            if mandat:
                row["Mandat"] = mandat
                updated += 1
                print(f"     → AJOUT via re-check : {mandat}")
        time.sleep(1.2)

    # ────────────────────────────────────────────────
    # 2. Scan du listing (pages paginées)
    # ────────────────────────────────────────────────
    seen_paths = set()
    for page in range(1, MAX_PAGES + 1):
        listing_path = f"/competitions?page={page}"
        print(f"\nScan page {page} : {listing_path}")
        html = fetch(listing_path)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        added = 0

        for container in soup.find_all(['li', 'div', 'article', 'tr', 'td', 'p']):
            a = container.find("a", href=True)
            if not a or "/epreuve/" not in a["href"]:
                continue

            text = container.get_text(" ", strip=True).lower()
            if not any(kw in text for kw in PL_KEYWORDS):
                continue

            detail_path = a["href"].split("/epreuve/")[-1].split("?")[0]
            detail_path = f"/epreuve/{detail_path}".replace("/index.php", "")
            if detail_path not in seen_paths:
                seen_paths.add(detail_path)
                added += 1

        print(f"  → {added} candidats détectés cette page")

        if added == 0 and page > 1:
            break
        time.sleep(SLEEP)

    print(f"\nTotal candidats PL détectés : {len(seen_paths)}")

    # ────────────────────────────────────────────────
    # 3. Traitement des pages détail
    # ────────────────────────────────────────────────
    for detail_path in seen_paths:
        print(f"\n → Détail {detail_path}")
        html = fetch(detail_path)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text().lower()

        if not any(kw in full_text for kw in ["pays de la loire", "cr12", "comite regional des pays de la loire"]):
            continue

        mandat = extract_mandat(html)
        if not mandat:
            continue

        h1 = soup.find("h1")
        titre_page = h1.get_text(strip=True).lower() if h1 else ""

        dates_found = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', full_text)

        matched = False
        for row in rows:
            if row.get("Mandat"):
                continue
            if not is_future(row):
                continue

            csv_titre = row.get("Titre compétition", "").strip().lower()
            csv_date = row.get("Date debut", "").strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville") or "").strip().lower()
            csv_code = row.get("Code structure", "").strip()

            score = 0
            # Matching très tolérant
            if csv_titre and any(word in titre_page for word in csv_titre.split()):
                score += 3
            if csv_date and csv_date in dates_found:
                score += 3
            if csv_ville and csv_ville in full_text:
                score += 2
            if csv_code and csv_code in full_text:
                score += 2

            if score >= 2 or row.get("Detail") == f"https://www.ffta.fr{detail_path}":
                row["Detail"] = f"https://www.ffta.fr{detail_path}"
                row["Mandat"] = mandat
                updated += 1
                print(f"   → AJOUT (score {score}) : {row.get('Titre compétition')} ({csv_date}) → {mandat}")
                matched = True
                break

        if not matched:
            print("   → Pas de match trouvé dans le CSV")

        time.sleep(SLEEP)

    # Sauvegarde
    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV sauvegardé – {updated} ajouts")
    else:
        print("\nAucun ajout cette fois")

    print("Fin du script")

if __name__ == "__main__":
    main()
