import csv
import os
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import datetime

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY_BASE = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = 6
SLEEP = 0.7

TODAY = datetime.date.today()

def proxy_url(path):
    if not path.startswith("/"): path = "/" + path
    return f"{PROXY_BASE}?target={quote(path)}"

def fetch(path):
    try:
        r = requests.get(proxy_url(path), headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        return r.text if r.status_code == 200 else None
    except:
        return None

def extract_mandat(html):
    if not html: return ""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            text = a.get_text(strip=True).lower()
            if any(word in href.lower() or word in text for word in ["mandat", "engagement", "inscription", "programme", "convocation"]):
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
    print(f"Démarrage - {TODAY} - MODE STRICT")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0

    # Re-vérification des lignes déjà connues
    print("Re-vérification des lignes futures sans mandat...")
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

    # Scan listing (pages 1 à MAX_PAGES)
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

    # Traitement très strict
    for detail_path in seen_paths:
        html = fetch(detail_path)
        if not html: continue

        soup = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text().lower()

        # Région obligatoire
        if "pays de la loire" not in full_text and "cr12" not in full_text:
            continue

        mandat = extract_mandat(html)
        if not mandat: continue

        h1 = soup.find("h1")
        titre_page = h1.get_text(strip=True).lower() if h1 else ""

        dates_found = set(re.findall(r'\d{1,2}/\d{1,2}/\d{4}', full_text))

        for row in rows:
            if row.get("Mandat") or not is_future(row): continue

            csv_date = row.get("Date debut", "").strip()
            csv_ville = (row.get("Ville compétition") or row.get("Ville") or "").strip().lower()
            csv_code = row.get("Code structure", "").strip()
            csv_discipline = row.get("Discipline", "").strip().lower()

            score = 0
            if csv_date and csv_date in dates_found: score += 5
            if csv_code and csv_code in full_text: score += 4
            if csv_ville and csv_ville in full_text: score += 3
            if csv_discipline and csv_discipline in titre_page: score += 2

            if score >= 9:
                row["Detail"] = f"https://www.ffta.fr{detail_path}"
                row["Mandat"] = mandat
                updated += 1
                print(f"   → AJOUT (score {score}) : {row.get('Titre compétition')} ({csv_date}) → {mandat}")
                break

    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV sauvegardé – {updated} ajouts")
    else:
        print("\nAucun ajout – vérifiez les logs")

    print("Fin")

if __name__ == "__main__":
    main()
