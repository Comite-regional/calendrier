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
        if href.endswith(".pdf") and any(kw in href or kw in text for kw in ["mandat", "resultat", "engagement", "inscription", "programme", "convocation", "tae", "beursault", "extranet"]):
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
    print(f"Script démarré – {TODAY} - MODE ASSOUPLI MAIS SÛR")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # Re-vérification
    print("\nRe-vérification lignes futures sans mandat...")
    for row in rows:
        if row.get("Mandat") or not row.get("Detail") or not is_future(row):
            continue
        detail_path = row["Detail"].replace("https://www.ffta.fr", "")
        html = fetch(detail_path)
        if html:
            mandat = extract_mandat(html)
            if mandat:
                row["Mandat"] = mandat
                updated += 1
                print(f"   → Re-check OK : {mandat}")

    # Scan listing
    seen_paths = set()
    for page in range(1, MAX_PAGES + 1):
        html = fetch(f"/competitions?page={page}")
        if not html: break
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            if "/epreuve/" not in a["href"]: continue
            detail_path = a["href"].split("/epreuve/")[-1].split("?")[0]
            detail_path = f"/epreuve/{detail_path}".replace("/index.php", "")
            seen_paths.add(detail_path)
        time.sleep(SLEEP)

    # Traitement
    for detail_path in seen_paths:
        html = fetch(detail_path)
        if not html: continue

        soup = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text().lower()

        if not any(kw in full_text for kw in ["pays de la loire", "cr12"]):
            continue

        mandat = extract_mandat(html)
        if not mandat: continue

        h1 = soup.find("h1")
        titre_page = h1.get_text(strip=True).lower() if h1 else ""

        # Regex date très large
        dates_found = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s*(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s*\d{4}', full_text)

        for row in rows:
            if row.get("Mandat") or not is_future(row): continue

            csv_date = row.get("Date debut", "").strip()
            csv_code = row.get("Code structure", "").strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville") or "").strip().lower()
            csv_discipline = row.get("Discipline", "").strip().lower()

            score = 0
            if csv_date and any(csv_date in d or csv_date.replace('/', ' ') in d for d in dates_found): score += 5
            if csv_code and csv_code in full_text: score += 4
            if csv_ville and csv_ville in full_text: score += 2
            if csv_discipline and csv_discipline in titre_page: score += 2

            if score >= 8:
                row["Detail"] = f"https://www.ffta.fr{detail_path}"
                row["Mandat"] = mandat
                updated += 1
                print(f"   → AJOUT (score {score}) : {row.get('Titre compétition')} ({csv_date}) → {mandat}")
                break
            else:
                print(f"   → Refusé : {row.get('Titre compétition')} (score {score}, code={csv_code in full_text}, date={any(csv_date in d for d in dates_found)})")

        time.sleep(SLEEP)

    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV sauvegardé – {updated} ajouts")
    else:
        print("\nAucun ajout – les pages n'ont pas matché sur code club + date")

    print("Fin")

if __name__ == "__main__":
    main()
