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
MAX_PAGES = int(os.getenv("MAX_PAGES", "8"))
SLEEP = float(os.getenv("SLEEP_S", "0.6"))

TODAY = datetime.date.today()

PAYS_LOIRE_DEPS = {"44", "49", "53", "72", "85"}

PL_KEYWORDS = [
    "44", "49", "53", "72", "85", "pays de la loire", "cr12",
    "carquefou", "fleche", "la fleche", "erdre", "beursault", "tae"
]

PDF_KEYWORDS = ["mandat", "resultat", "resultats", "engagement", "inscription", "programme", "convocation", "tae", "beursault", "extranet"]

def proxy_url(target_path):
    if not target_path.startswith("/"):
        target_path = "/" + target_path
    return f"{PROXY_BASE}?target={quote(target_path)}"

def fetch(target_path):
    url = proxy_url(target_path)
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        return r.text if r.status_code == 200 else None
    except:
        return None

def extract_mandat(html):
    if not html: return ""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        if href.endswith(".pdf") and any(kw in href or kw in text for kw in PDF_KEYWORDS):
            return href if href.startswith("http") else "https://www.ffta.fr" + href
    return ""

def is_future(row):
    debut = row.get("Date debut", "").strip()
    if not debut: return False
    try:
        d, m, y = map(int, debut.split('/'))
        return datetime.date(y, m, d) >= TODAY
    except:
        return False

def main():
    print(f"Script démarré – {TODAY}")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # 1. RE-VÉRIFICATION STRICTE des lignes déjà connues
    print("\nRe-vérification des lignes futures sans mandat...")
    for row in rows:
        if row.get("Mandat") or not row.get("Detail") or not is_future(row):
            continue

        detail_path = row["Detail"].replace("https://www.ffta.fr", "")
        print(f"  Re-check {detail_path} → {row.get('Titre compétition')}")
        html = fetch(detail_path)
        if html:
            mandat = extract_mandat(html)
            if mandat:
                row["Mandat"] = mandat
                updated += 1
                print(f"     → AJOUT via re-check : {mandat}")
        time.sleep(1.2)

    # 2. Scan listing
    seen_paths = set()
    for page in range(1, MAX_PAGES + 1):
        listing_path = f"/competitions?page={page}"
        html = fetch(listing_path)
        if not html: break

        soup = BeautifulSoup(html, "html.parser")
        for container in soup.find_all(['li', 'div', 'article', 'tr', 'td', 'p']):
            a = container.find("a", href=True)
            if not a or "/epreuve/" not in a["href"]: continue

            text = container.get_text(" ", strip=True).lower()
            if not any(kw in text for kw in PL_KEYWORDS): continue

            detail_path = a["href"].split("/epreuve/")[-1].split("?")[0]
            detail_path = f"/epreuve/{detail_path}".replace("/index.php", "")
            seen_paths.add(detail_path)

        time.sleep(SLEEP)

    print(f"Total candidats PL détectés : {len(seen_paths)}")

    # 3. Traitement très strict
    for detail_path in seen_paths:
        html = fetch(detail_path)
        if not html: continue

        soup = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text().lower()
        if not any(kw in full_text for kw in ["pays de la loire", "cr12"]): continue

        mandat = extract_mandat(html)
        if not mandat: continue

        h1 = soup.find("h1")
        titre_page = h1.get_text(strip=True).lower() if h1 else ""
        dates_found = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', full_text)

        for row in rows:
            if row.get("Mandat") or not is_future(row): continue

            csv_date = row.get("Date debut", "").strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville") or "").strip().lower()
            csv_code = row.get("Code structure", "").strip()
            csv_titre = row.get("Titre compétition", "").strip().lower()
            csv_discipline = row.get("Discipline", "").strip().lower()

            score = 0
            # DATE = obligatoire
            if csv_date and csv_date in dates_found:
                score += 4

            # VILLE
            if csv_ville and csv_ville in full_text:
                score += 2
            # CODE CLUB (très fort)
            if csv_code and csv_code in full_text:
                score += 3
            # DISCIPLINE / TITRE
            if csv_discipline and any(word in titre_page for word in csv_discipline.split()):
                score += 2
            if csv_titre and any(word in titre_page for word in csv_titre.split()):
                score += 2

            # SEUIL TRÈS STRICT
            if score >= 5 or row.get("Detail") == f"https://www.ffta.fr{detail_path}":
                row["Detail"] = f"https://www.ffta.fr{detail_path}"
                row["Mandat"] = mandat
                updated += 1
                print(f"   → AJOUT STRICT (score {score}) : {row.get('Titre compétition')} ({csv_date}) → {mandat}")
                break
            else:
                print(f"   → Refusé (score {score} trop bas) : {row.get('Titre compétition')}")

        time.sleep(SLEEP)

    # Sauvegarde
    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV sauvegardé – {updated} mandats ajoutés")
    else:
        print("\nAucun ajout cette fois")

    print("Fin du script")

if __name__ == "__main__":
    main()
