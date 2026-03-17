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
MAX_PAGES = int(os.getenv("MAX_PAGES", "6"))
SLEEP = float(os.getenv("SLEEP_S", "0.5"))

TODAY = datetime.date.today()

PAYS_LOIRE_DEPS = {"44", "49", "53", "72", "85"}
PL_KEYWORDS = [
    "44", "49", "53", "72", "85",
    "loire atlantique", "maine et loire", "mayenne", "sarthe", "vendée",
    "pays de la loire", "cr12", "comite regional des pays de la loire",
    "nantes", "angers", "le mans", "laval", "la roche sur yon",
    "saumur", "cholet", "st nazaire", "fontenay le comte"
]

PDF_KEYWORDS = ["mandat", "resultat", "resultats", "result", "engagement", "inscription", "inscriptions", "programme", "convocation"]

def proxy_url(target_path):
    """target_path doit être relatif : /competitions?page=1 ou /epreuve/23539"""
    if not target_path.startswith("/"):
        target_path = "/" + target_path
    return f"{PROXY_BASE}?target={quote(target_path)}"

def fetch(target_path):
    url = proxy_url(target_path)
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"Erreur HTTP {r.status_code} sur target={target_path}")
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

def main():
    print(f"Script démarré - {TODAY}")

    if not os.path.exists(CSV_PATH):
        print(f"ERREUR : CSV introuvable ({CSV_PATH})")
        return

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # Scan listing paginé
    seen_urls = set()
    for page in range(1, MAX_PAGES + 1):
        listing_path = f"/competitions?page={page}"
        print(f"Scan {listing_path}")
        html = fetch(listing_path)
        if not html:
            print(f"Échec page {page}")
            break

        soup = BeautifulSoup(html, "html.parser")
        added = 0

        for container in soup.find_all(['li', 'div', 'article', 'tr', 'td']):
            a = container.find("a", href=True)
            if not a or "/epreuve/" not in a["href"]:
                continue

            text = container.get_text(" ", strip=True).lower()
            if not any(kw in text for kw in PL_KEYWORDS):
                continue

            detail_path = a["href"].split("/epreuve/")[-1].split("?")[0]
            detail_path = f"/epreuve/{detail_path}".replace("/index.php", "")
            if detail_path not in seen_urls:
                seen_urls.add(detail_path)
                added += 1

        print(f"  → {added} candidats cette page")

        if added == 0 and page > 1:
            break
        time.sleep(SLEEP)

    print(f"Total candidats PL : {len(seen_urls)}")

    # Traitement détails
    for detail_path in seen_urls:
        print(f" → Détail {detail_path}")
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

        for row in rows:
            if row.get("Mandat"):
                continue
            if not row.get("Date debut"):
                continue

            try:
                d, m, y = map(int, row["Date debut"].split('/'))
                if datetime.date(y, m, d) < TODAY:
                    continue
            except:
                continue

            csv_titre = row["Titre compétition"].strip().lower()
            csv_date = row["Date debut"].strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville") or "").strip().lower()

            score = 0
            if csv_titre in titre_page:
                score += 4
            if csv_date in dates_found:
                score += 3
            if csv_ville in full_text:
                score += 2

            if score >= 4 or row.get("Detail") == f"https://www.ffta.fr{detail_path}":
                row["Detail"] = f"https://www.ffta.fr{detail_path}"
                row["Mandat"] = mandat
                updated += 1
                print(f"   → AJOUT : {row['Titre compétition']} ({csv_date}) → {mandat} (score {score})")
                break

        time.sleep(SLEEP)

    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV sauvegardé - {updated} ajouts")
    else:
        print("Aucun ajout")

    print("Fin")

if __name__ == "__main__":
    main()
