import csv, os, time, requests, unicodedata
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# URL de recherche forcée sur les 5 départements des Pays de la Loire
# Les paramètres dep[0] à dep[4] sont les filtres officiels de la FFTA pour 44,49,53,72,85
SEARCH_URL = "/competitions?search=&start=2025-09-01&end=2026-08-31&dep%5B0%5D=44&dep%5B1%5D=49&dep%5B2%5D=53&dep%5B3%5D=72&dep%5B4%5D=85&discipline=All&sort_by=start"

def normalize(s):
    if not s: return ""
    return unicodedata.normalize("NFD", str(s).lower().strip()).encode("ascii", "ignore").decode("utf-8")

def main():
    if not os.path.exists(CSV_PATH): return print(f"❌ Fichier {CSV_PATH} introuvable.")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames
    if "Mandat" not in fields: fields.append("Mandat")

    # 1. Collecter tous les liens de détails dans les Pays de la Loire
    detail_links = []
    for page in range(6): # 6 pages couvrent largement la saison PDL
        target = f"{SEARCH_URL}&page={page}"
        print(f"📡 Scan de la liste PDL (Page {page})...", end="\r")
        try:
            r = requests.get(f"{PROXY}?target={quote(target)}", timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a['href']
                if "/competition/" in href or "/epreuve/" in href:
                    detail_links.append(urljoin("/", href))
        except: continue

    links = list(set(detail_links))
    print(f"\n✅ {len(links)} épreuves identifiées en Pays de la Loire.")

    # 2. Ouvrir chaque fiche pour vérification et extraction du mandat
    updated = 0
    for link in links:
        print(f"🔎 Analyse détaillée : {link}      ", end="\r")
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            page_content = normalize(detail_soup.get_text(" "))

            # Trouver le mandat
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                if "mandat" in a.get_text().lower() or ".pdf" in a['href'].lower():
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            if not mandat_url: continue

            # Comparaison avec le Code Structure du CSV
            for row in rows:
                if len(str(row.get("Mandat", ""))) > 10: continue
                
                code_club = str(row.get("Code structure", "")).strip()
                # Si le code club est présent dans la page de détail, c'est un match parfait
                if code_club and code_club in page_content:
                    row["Mandat"] = mandat_url
                    print(f"\n✨ Match trouvé : {row['Ville']} ({code_club})")
                    updated += 1
                    break
        except: continue
        time.sleep(0.2)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats ajoutés au fichier {CSV_PATH}.")

if __name__ == "__main__":
    main()
