import csv
import os
import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import datetime

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = 5           # 2-3 suffisent largement
SLEEP = 0.4

TODAY = datetime.date.today()

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

def is_future(row):
    debut = row.get("Date debut", "").strip()
    if not debut:
        return False
    try:
        d, m, y = map(int, debut.split('/'))
        return datetime.date(y, m, d) >= TODAY
    except:
        return False

def is_pays_loire(row):
    dep = row.get("Departement", "").strip()
    region = row.get("Code region", "").strip()
    ville = (row.get("Ville compétition", "") or row.get("Ville", "")).lower()
    if region == "CR12" or dep in ["44", "49", "53", "72", "85"]:
        return True
    # fallback texte
    if any(x in ville for x in ["nantes", "angers", "le mans", "laval", "la roche", "saumur", "cholet"]):
        return True
    return False

def main():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0
    print("🔍 Focus sur concours futurs Pays de la Loire")

    # 1. Collecter les URLs déjà connues (pour éviter re-traitement)
    known_details = {row["Detail"] for row in rows if row.get("Detail")}

    # 2. Scanner le listing national mais filtrer très tôt
    new_or_to_check = []
    for page in range(1, MAX_PAGES + 1):
        status, html = fetch(f"{PROXY}?page={page}")
        if status != 200 or not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            if "/epreuve/" not in a["href"]:
                continue
            detail_url = "https://www.ffta.fr" + a["href"].split("/epreuve/")[-1].split("?")[0]
            detail_url = detail_url.replace("/index.php", "")

            # Filtre texte rapide sur la ligne
            parent_text = (a.find_parent().get_text(" ", strip=True) or "").lower()
            if not any(k in parent_text for k in ["44", "49", "53", "72", "85", "pays de la loire", "maine et loire", "vendée", "sarthe", "mayenne", "loire atlantique"]):
                continue

            new_or_to_check.append(detail_url)

    print(f"   → {len(new_or_to_check)} candidats Pays de la Loire détectés")

    # 3. Traiter (nouveaux + anciens sans mandat)
    for detail_url in set(new_or_to_check):
        if detail_url in known_details:
            # Re-vérif si mandat manquant
            for row in rows:
                if row.get("Detail") == detail_url and not row.get("Mandat") and is_future(row):
                    # proceed to fetch
                    break
            else:
                continue  # déjà OK

        print(f"   Vérification {detail_url}")

        status, html = fetch(proxy_url(detail_url))
        if status != 200 or not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Confirmer région dans détail (fiable)
        text_all = soup.get_text().lower()
        if not any(r in text_all for r in ["pays de la loire", "cr12", "comite regional des pays de la loire"]):
            continue

        # Extraire PDF
        mandat = ""
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            txt = a_tag.get_text(strip=True).lower()
            if href.endswith(".pdf") and any(w in href or w in txt for w in ["mandat", "resultat", "result", "inscript", "programme"]):
                mandat = "https://www.ffta.fr" + href if not href.startswith("http") else href
                break

        if not mandat:
            continue

        # Associer à la/les ligne(s) correspondante(s)
        matched = False
        for row in rows:
            if not is_future(row) or not is_pays_loire(row):
                continue
            if row.get("Mandat"):
                continue

            csv_titre = row.get("Titre compétition", "").strip().lower()
            titre_page = (soup.find("h1") or {}).get_text(strip=True).lower() if soup.find("h1") else ""

            if csv_titre in titre_page or row.get("Detail") == detail_url:
                row["Detail"] = detail_url
                row["Mandat"] = mandat
                updated += 1
                print(f"   → Mandat ajouté : {mandat} pour {row.get('Titre compétition')}")
                matched = True

        time.sleep(SLEEP)

    # Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"🎯 {updated} mandats ajoutés ou mis à jour (Pays de la Loire uniquement)")

if __name__ == "__main__":
    main()
